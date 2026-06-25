# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": { "name": "synapse_pyspark" },
# META   "dependencies": {}
# META }

# CELL ********************

# nb_util_gold — gold dim/fact build engine (%run by nb_gold_orchestrator, which provides
# the gold-lakehouse Spark context). Adapted from the accelerator's Dimension/FactProcessor,
# Fabric-flavoured: surrogate keys via row_number()+max_sk (no IDENTITY), config as args.
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from delta.tables import DeltaTable

CTRL = {"dl_iscurrent", "dl_recordstartdateutc", "dl_recordenddateutc", "dl_rowhash", "dl_transform_id"}


def _split(obj):
    s, t = obj.split(".", 1)
    return s, t


def _rowhash(df, cols):
    return F.sha2(F.concat_ws("||", *[F.coalesce(F.col(c).cast("string"), F.lit("")) for c in cols]), 256)


def build_dimension(gold_object, source_view, scd_type, surrogate_key, business_keys,
                    non_historized_columns=None, transform_id=None):
    """Build/merge a gold dimension from a transformed view. SCD type 1 or 2.
    surrogate_key is generated here; business_keys (natural keys) drive change detection."""
    schema, _ = _split(gold_object)
    scd_type = int(scd_type)
    nks = [k.strip() for k in business_keys.split(",") if k.strip()]
    nonhist = {c.strip() for c in (non_historized_columns or "").split(",") if c.strip()}
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {schema}")

    src = spark.table(source_view)
    attr_cols = [c for c in src.columns if c != surrogate_key and c not in CTRL]
    hash_cols = sorted([c for c in attr_cols if c not in nonhist], key=str.lower)
    new = (src.select(*attr_cols)
              .withColumn("dl_rowhash", _rowhash(src, hash_cols))
              .withColumn("dl_transform_id", F.lit(transform_id).cast("int")))

    # initial create + load
    if not spark.catalog.tableExists(gold_object):
        w = Window.orderBy(*[F.col(k) for k in nks])
        out = (new.withColumn(surrogate_key, F.row_number().over(w).cast("long"))
                  .withColumn("dl_iscurrent", F.lit(True))
                  .withColumn("dl_recordstartdateutc", F.current_timestamp())
                  .withColumn("dl_recordenddateutc", F.lit(None).cast("timestamp")))
        out.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(gold_object)
        return {"object": gold_object, "action": "created", "rows": out.count(), "scd": scd_type}

    tgt = DeltaTable.forName(spark, gold_object)
    cur = tgt.toDF().filter("dl_iscurrent = true").select(*nks, F.col("dl_rowhash").alias("_cur_hash"))
    j = new.alias("n").join(cur.alias("c"),
                            on=[F.col(f"n.{k}").eqNullSafe(F.col(f"c.{k}")) for k in nks], how="left")
    changed = j.filter(F.col("c._cur_hash").isNull() | (F.col("n.dl_rowhash") != F.col("c._cur_hash"))).select("n.*")
    n_changed = changed.count()
    if n_changed == 0:
        return {"object": gold_object, "action": "no-change", "rows": 0, "scd": scd_type}

    chg_keys = changed.select(*nks).distinct()
    match = " AND ".join([f"t.{k} <=> s.{k}" for k in nks]) + " AND t.dl_iscurrent = true"
    if scd_type == 2:
        # expire the current version of changed keys (history retained)
        (tgt.alias("t").merge(chg_keys.alias("s"), match)
            .whenMatchedUpdate(set={"dl_iscurrent": "false", "dl_recordenddateutc": "current_timestamp()"})
            .execute())
    else:
        # SCD1: drop the old current version (no history) before inserting the new one
        (tgt.alias("t").merge(chg_keys.alias("s"), match).whenMatchedDelete().execute())

    max_sk = spark.table(gold_object).agg(F.max(surrogate_key)).collect()[0][0] or 0
    w = Window.orderBy(*[F.col(k) for k in nks])
    ins = (changed.withColumn(surrogate_key, (F.row_number().over(w) + F.lit(max_sk)).cast("long"))
                  .withColumn("dl_iscurrent", F.lit(True))
                  .withColumn("dl_recordstartdateutc", F.current_timestamp())
                  .withColumn("dl_recordenddateutc", F.lit(None).cast("timestamp")))
    ins.write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable(gold_object)
    return {"object": gold_object, "action": "merged", "rows": n_changed, "scd": scd_type}


def build_fact(gold_object, source_view, fact_type, business_keys=None,
               watermark_column=None, last_n_days=None, transform_id=None):
    """Build a gold fact from a transformed view. Type 1 = full rebuild; Type 2 = rolling window.
    Dimension surrogate-key resolution is expected to be done IN the source view."""
    schema, _ = _split(gold_object)
    fact_type = int(fact_type)
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    tid = "NULL" if transform_id is None else str(int(transform_id))

    if fact_type == 1 or not spark.catalog.tableExists(gold_object):
        spark.sql(f"""
            CREATE OR REPLACE TABLE {gold_object} AS
            SELECT *, current_timestamp() AS dl_insertdateutc, CAST({tid} AS INT) AS dl_transform_id
            FROM {source_view}
        """)
        action = "rebuilt"
    else:
        win = int(last_n_days)
        spark.sql(f"""
            INSERT INTO {gold_object}
              REPLACE WHERE {watermark_column} >= dateadd(day, -{win}, current_timestamp())
            SELECT *, current_timestamp() AS dl_insertdateutc, CAST({tid} AS INT) AS dl_transform_id
            FROM {source_view}
            WHERE {watermark_column} >= dateadd(day, -{win}, current_timestamp())
        """)
        action = "rolling"

    dupes = 0
    if business_keys:
        nks = [k.strip() for k in business_keys.split(",") if k.strip()]
        dupes = spark.table(source_view).groupBy(*nks).count().filter("count > 1").count()
    return {"object": gold_object, "action": action, "rows": spark.table(gold_object).count(), "grain_dupes": dupes}

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
