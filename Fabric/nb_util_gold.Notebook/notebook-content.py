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

CTRL = {"dl_iscurrent", "dl_isdeleted", "dl_recordstartdateutc", "dl_recordenddateutc",
        "dl_rowhash", "dl_transform_id"}


def _split(obj):
    s, t = obj.split(".", 1)
    return s, t


def _rowhash(df, cols):
    return F.sha2(F.concat_ws("||", *[F.coalesce(F.col(c).cast("string"), F.lit("")) for c in cols]), 256)


def build_dimension(gold_object, source_table, scd_type, surrogate_key, business_keys,
                    non_historized_columns=None, load_mode="incremental", transform_id=None):
    """Build/merge a gold dimension from a materialized stg table.
    scd_type 1|2; load_mode 'incremental'|'full'. surrogate_key is generated here;
    business_keys (natural keys) drive change detection.
    In 'full' mode the source is a COMPLETE snapshot, so business keys present in the
    dimension but absent from the source are treated as deletes — soft-expired
    (dl_iscurrent=false, dl_isdeleted=true, dl_recordenddateutc set). 'incremental' mode
    NEVER deletes (the source is partial)."""
    schema, _ = _split(gold_object)
    scd_type = int(scd_type)
    full = (load_mode == "full")
    nks = [k.strip() for k in business_keys.split(",") if k.strip()]
    nonhist = {c.strip() for c in (non_historized_columns or "").split(",") if c.strip()}
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {schema}")

    src = spark.table(source_table)
    attr_cols = [c for c in src.columns if c != surrogate_key and c not in CTRL]
    hash_cols = sorted([c for c in attr_cols if c not in nonhist], key=str.lower)
    new = (src.select(*attr_cols)
              .withColumn("dl_rowhash", _rowhash(src, hash_cols))
              .withColumn("dl_transform_id", F.lit(transform_id).cast("int")))

    def _stamp(df, sk_expr):
        return (df.withColumn(surrogate_key, sk_expr)
                  .withColumn("dl_iscurrent", F.lit(True))
                  .withColumn("dl_isdeleted", F.lit(False))
                  .withColumn("dl_recordstartdateutc", F.current_timestamp())
                  .withColumn("dl_recordenddateutc", F.lit(None).cast("timestamp")))

    # initial create + load
    if not spark.catalog.tableExists(gold_object):
        w = Window.orderBy(*[F.col(k) for k in nks])
        out = _stamp(new, F.row_number().over(w).cast("long"))
        out.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(gold_object)
        return {"object": gold_object, "action": "created", "rows": out.count(),
                "deleted": 0, "scd": scd_type, "mode": load_mode}

    # older dimensions predate dl_isdeleted — add it before any merge references it
    if "dl_isdeleted" not in spark.table(gold_object).columns:
        spark.sql(f"ALTER TABLE {gold_object} ADD COLUMNS (dl_isdeleted boolean)")
        spark.sql(f"UPDATE {gold_object} SET dl_isdeleted = false WHERE dl_isdeleted IS NULL")

    tgt = DeltaTable.forName(spark, gold_object)
    cur = tgt.toDF().filter("dl_iscurrent = true").select(*nks, F.col("dl_rowhash").alias("_cur_hash"))
    j = new.alias("n").join(cur.alias("c"),
                            on=[F.col(f"n.{k}").eqNullSafe(F.col(f"c.{k}")) for k in nks], how="left")
    changed = j.filter(F.col("c._cur_hash").isNull() | (F.col("n.dl_rowhash") != F.col("c._cur_hash"))).select("n.*")
    n_changed = changed.count()

    if n_changed > 0:
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
        ins = _stamp(changed, (F.row_number().over(w) + F.lit(max_sk)).cast("long"))
        ins.write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable(gold_object)

    # full-load delete handling: current keys absent from the (complete) source -> soft-expire.
    # Same tombstone for SCD1 and SCD2; downstream already filters on dl_iscurrent.
    n_deleted = 0
    if full:
        src_keys = new.select(*nks).distinct()
        cur_keys = (DeltaTable.forName(spark, gold_object).toDF()
                    .filter("dl_iscurrent = true").select(*nks))
        deleted = cur_keys.join(src_keys, on=nks, how="left_anti")
        n_deleted = deleted.count()
        if n_deleted > 0:
            match = " AND ".join([f"t.{k} <=> s.{k}" for k in nks]) + " AND t.dl_iscurrent = true"
            (tgt.alias("t").merge(deleted.alias("s"), match)
                .whenMatchedUpdate(set={"dl_iscurrent": "false", "dl_isdeleted": "true",
                                        "dl_recordenddateutc": "current_timestamp()"})
                .execute())

    action = "merged" if (n_changed or n_deleted) else "no-change"
    return {"object": gold_object, "action": action, "rows": n_changed,
            "deleted": n_deleted, "scd": scd_type, "mode": load_mode}


def build_fact(gold_object, source_table, mode, business_keys=None,
               watermark_column=None, last_n_days=None, transform_id=None):
    """Build a gold fact from a materialized stg table. mode (derived from table_type):
        'reload'  : full drop+rebuild from source each run (rows absent from source vanish).
        'upsert'  : MERGE on business_keys — update matched, insert new.
        'append'  : insert only source rows whose business_keys are new (never update/delete).
    watermark_column + last_n_days optionally window the SOURCE for upsert/append (limits the
    comparison set). Dimension surrogate-key resolution is expected to be done IN the source.
    """
    schema, _ = _split(gold_object)
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    tid = "NULL" if transform_id is None else str(int(transform_id))

    # first-ever load OR a full reload → (re)create from source
    if mode == "reload" or not spark.catalog.tableExists(gold_object):
        spark.sql(f"""
            CREATE OR REPLACE TABLE {gold_object} AS
            SELECT *, current_timestamp() AS dl_insertdateutc, CAST({tid} AS INT) AS dl_transform_id
            FROM {source_table}
        """)
        action = "reloaded" if mode == "reload" else "created"
    else:
        nks = [k.strip() for k in (business_keys or "").split(",") if k.strip()]
        if not nks:
            raise Exception(f"fact mode '{mode}' on {gold_object} requires business_keys")
        staged = spark.table(source_table)
        if watermark_column and last_n_days:
            staged = staged.filter(
                F.col(watermark_column) >= F.expr(f"dateadd(day, -{int(last_n_days)}, current_timestamp())"))
        staged = (staged.withColumn("dl_insertdateutc", F.current_timestamp())
                        .withColumn("dl_transform_id", F.lit(transform_id).cast("int")))
        cond = " AND ".join([f"t.{k} <=> s.{k}" for k in nks])
        mrg = DeltaTable.forName(spark, gold_object).alias("t").merge(staged.alias("s"), cond)
        if mode == "upsert":
            mrg.whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()
            action = "upserted"
        elif mode == "append":
            mrg.whenNotMatchedInsertAll().execute()  # insert new business keys only
            action = "appended"
        else:
            raise Exception(f"unknown fact mode '{mode}' for {gold_object}")

    # grain check on the source (business_keys should be unique per build)
    dupes = 0
    if business_keys:
        nks = [k.strip() for k in business_keys.split(",") if k.strip()]
        dupes = spark.table(source_table).groupBy(*nks).count().filter("count > 1").count()
    return {"object": gold_object, "action": action, "rows": spark.table(gold_object).count(), "grain_dupes": dupes}

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
