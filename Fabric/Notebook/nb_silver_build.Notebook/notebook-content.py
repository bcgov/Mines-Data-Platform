# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": { "name": "synapse_pyspark" },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "a0190e0e-c2f5-4740-ab90-a2f29b6e6991",
# META       "default_lakehouse_name": "lh_silver",
# META       "default_lakehouse_workspace_id": "8f380f88-5ce5-48d1-9fa5-fbbfbe2685a0",
# META       "known_lakehouses": [ { "id": "a0190e0e-c2f5-4740-ab90-a2f29b6e6991" } ]
# META     },
# META     "warehouse": {
# META       "default_warehouse": "dad1e7ab-adc2-bd51-408b-33e59ed9a608",
# META       "known_warehouses": [ { "id": "dad1e7ab-adc2-bd51-408b-33e59ed9a608", "type": "Datawarehouse" } ]
# META     }
# META   }
# META }

# CELL ********************

# nb_silver_build — REGISTRY-DRIVEN Bronze -> Silver across all active objects.
# Drives off app.object_registry (built by nb_silver_registry from app.pipeline_control +
# bronze schemas). Per object: standardize names, cleanse, load_type-aware dedup, not-null PK
# DQ (bad rows quarantined), drop bronze lineage, write silver.<table> (current cleansed view)
# + silver.v_<table>. Failures -> centralized app.error_log (layer='silver').
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import StructType, StructField, StringType, LongType
from datetime import datetime
import uuid
import traceback

WORKSPACE_ID = "8f380f88-5ce5-48d1-9fa5-fbbfbe2685a0"
BRONZE_LH_ID = "8cd34a44-500a-47d9-aa2d-5ad0c2149858"
WAREHOUSE = "mines-data-platform-fabwh1"
SILVER_SCHEMA = "silver"
QUARANTINE_SCHEMA = "quarantine"
SUMMARY_TABLE = "silver.load_summary"

# bronze lineage/control columns — used for dedup, then dropped from silver
CTRL_COLS = {"dl_load_id", "bronze_file_name", "bronze_file_timestamp", "bronze_load_date",
             "dl_load_ts", "dl_rowhash"}

spark.conf.set("spark.databricks.delta.schema.autoMerge.enabled", "true")
# Source data contains pre-1900 timestamps (e.g. permit_amendment) — rebase on write/read.
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite", "LEGACY")
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "LEGACY")
spark.conf.set("spark.sql.parquet.int96RebaseModeInWrite", "LEGACY")
spark.conf.set("spark.sql.parquet.int96RebaseModeInRead", "LEGACY")


def log_error(layer, run_id, entity, error_message, stack_trace=None, target_table=None,
              error_code=None, error_context=None, log_id=None, pipeline_name=None):
    """Write one row to the centralized warehouse app.error_log via the synapsesql connector."""
    try:
        from com.microsoft.spark.fabric import Constants  # noqa: F401 — registers the .synapsesql writer
        from pyspark.sql.types import StructType, StructField, StringType, LongType, IntegerType
        sch = StructType([
            StructField("error_id", StringType()), StructField("layer", StringType()),
            StructField("log_id", LongType()), StructField("pipeline_name", StringType()),
            StructField("run_id", StringType()), StructField("entity", StringType()),
            StructField("target_table", StringType()), StructField("error_message", StringType()),
            StructField("error_code", StringType()), StructField("error_context", StringType()),
            StructField("stack_trace", StringType()),
        ])
        row = (str(uuid.uuid4()), layer, log_id, pipeline_name, run_id, entity, target_table,
               (error_message or "(no message)")[:8000], error_code, error_context,
               (stack_trace[:8000] if stack_trace else None))
        edf = (spark.createDataFrame([row], sch)
               .withColumn("created_date", F.current_timestamp())
               .withColumn("error_number", F.lit(None).cast(IntegerType()))
               .withColumn("error_severity", F.lit(None).cast(IntegerType()))
               .withColumn("error_state", F.lit(None).cast(IntegerType()))
               .withColumn("error_procedure", F.lit(None).cast(StringType()))
               .withColumn("error_line", F.lit(None).cast(IntegerType())))
        edf.write.mode("append").synapsesql(f"{WAREHOUSE}.app.error_log")
    except Exception as e:
        print(f"log_error failed (non-fatal): {e}")


def bronze_path(table):
    return f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com/{BRONZE_LH_ID}/Tables/bronze/{table}/"


def normalize(name):
    return name.lower().replace(" ", "_").replace("-", "_").replace(".", "_")


def process(obj):
    t = obj["bronze_table"]
    pk = obj.get("primary_key")
    load_type = (obj.get("load_type") or "FULL").upper()
    pk_cols = [c.strip() for c in (pk or "").split(",") if c.strip()]  # true PK, possibly composite

    df = spark.read.format("delta").load(bronze_path(t))
    bronze_rows = df.count()

    # 1. standardize column names
    for c in df.columns:
        nc = normalize(c)
        if nc != c:
            df = df.withColumnRenamed(c, nc)

    # 2. cleanse: trim strings, empty -> null
    string_cols = [f.name for f in df.schema.fields if isinstance(f.dataType, StringType)]
    for c in string_cols:
        df = df.withColumn(c, F.trim(F.col(c)))
    if string_cols:
        df = df.replace("", None, subset=string_cols)

    pk_ok = bool(pk_cols) and all(c in df.columns for c in pk_cols)

    # 3. dedup to the current view, load_type-aware:
    #    INCREMENTAL + true PK -> latest row per (composite) PK by load ts; FULL -> latest full
    #    snapshot (append-only bronze accumulates repeated copies); else -> exact-row distinct.
    if load_type == "INCREMENTAL" and pk_ok and "dl_load_ts" in df.columns:
        w = Window.partitionBy(*[F.col(c) for c in pk_cols]).orderBy(F.col("dl_load_ts").desc())
        df = df.withColumn("_rn", F.row_number().over(w)).filter(F.col("_rn") == 1).drop("_rn")
    elif load_type == "FULL" and "bronze_file_timestamp" in df.columns:
        latest = df.agg(F.max("bronze_file_timestamp")).collect()[0][0]
        if latest is not None:
            df = df.filter(F.col("bronze_file_timestamp") == F.lit(latest))
        df = df.dropDuplicates()
    else:
        df = df.dropDuplicates()

    # 4. DQ: not-null on every PK column -> valid vs quarantine (only when a PK is known)
    if pk_ok:
        cond = None
        for c in pk_cols:
            cond = F.col(c).isNotNull() if cond is None else (cond & F.col(c).isNotNull())
        valid_df = df.filter(cond)
        invalid_df = df.filter(~cond)
        quarantined = invalid_df.count()
    else:
        valid_df, invalid_df, quarantined = df, None, 0

    # 5. drop bronze lineage, stamp silver_load_ts, write current cleansed silver table
    drop_cols = [c for c in CTRL_COLS if c in valid_df.columns]
    valid_df = valid_df.drop(*drop_cols).withColumn("silver_load_ts", F.current_timestamp())
    (valid_df.write.format("delta").mode("overwrite")
        .option("overwriteSchema", "true").saveAsTable(f"{SILVER_SCHEMA}.{t}"))
    silver_rows = valid_df.count()

    # 6. quarantine failing rows
    if quarantined > 0:
        q_df = (invalid_df
                .withColumn("dq_rule", F.lit("not_null"))
                .withColumn("dq_reason", F.lit(f"null primary_key: {pk}"))
                .withColumn("run_id", F.lit(RUN_ID))
                .withColumn("quarantine_ts", F.current_timestamp()))
        (q_df.write.format("delta").mode("append")
            .option("mergeSchema", "true").saveAsTable(f"{QUARANTINE_SCHEMA}.{t}"))

    # 7. current-state view
    spark.sql(f"CREATE OR REPLACE VIEW {SILVER_SCHEMA}.v_{t} AS SELECT * FROM {SILVER_SCHEMA}.{t}")

    return bronze_rows, silver_rows, quarantined

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

print("=" * 80)
print("SILVER BUILD START (registry-driven)")
print("=" * 80)

RUN_ID = str(uuid.uuid4())
START = datetime.now()
results = []

# Fabric schema-enabled lakehouses do NOT auto-create schemas on saveAsTable.
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {SILVER_SCHEMA}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {QUARANTINE_SCHEMA}")

# Drive off the registry: every active object.
from com.microsoft.spark.fabric import Constants  # noqa: F401
objs = [r.asDict() for r in
        spark.read.synapsesql(f"{WAREHOUSE}.app.object_registry").filter("is_active = true").collect()]
objs.sort(key=lambda o: (o.get("priority") or 100, o.get("bronze_table")))
print(f"active objects to build: {len(objs)}")

for obj in objs:
    t = obj["bronze_table"]
    try:
        bronze_rows, silver_rows, quarantined = process(obj)
        print(f"OK   {t}: bronze={bronze_rows} silver={silver_rows} quarantined={quarantined}")
        results.append((t, int(bronze_rows), int(silver_rows), int(quarantined), "OK", None))
    except Exception as e:
        err = str(e)[:1000]
        print(f"FAILED {t}: {err}")
        log_error("silver", RUN_ID, t, err, traceback.format_exc(), target_table=f"silver.{t}")
        results.append((t, None, None, None, "FAILED", err))

# summary (explicit schema avoids void inference)
summary_schema = StructType([
    StructField("entity", StringType()),
    StructField("bronze_rows", LongType()),
    StructField("silver_rows", LongType()),
    StructField("quarantined_rows", LongType()),
    StructField("status", StringType()),
    StructField("error", StringType()),
])
summary_df = (spark.createDataFrame(results, summary_schema)
              .withColumn("run_id", F.lit(RUN_ID))
              .withColumn("run_ts", F.current_timestamp()))

# Reliable readback: write the run log to the BRONZE lakehouse (its SQL endpoint syncs fast).
try:
    bronze_log_path = f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com/{BRONZE_LH_ID}/Tables/bronze/silver_run_log/"
    summary_df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(bronze_log_path)
    print("wrote run log to bronze.silver_run_log")
except Exception as e:
    print(f"bronze readback write failed: {e}")

# Also persist the run summary to the warehouse for easy SQL verification.
try:
    summary_df.write.mode("overwrite").option("overwriteSchema", "true").synapsesql(f"{WAREHOUSE}.app.silver_run_log")
except Exception as e:
    print(f"warehouse silver_run_log write failed: {e}")

# Best-effort silver-local summary too.
try:
    summary_df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(SUMMARY_TABLE)
except Exception as e:
    print(f"Error writing {SUMMARY_TABLE}: {e}")

ok = sum(1 for r in results if r[4] == "OK")
failed = sum(1 for r in results if r[4] == "FAILED")
print("=" * 80)
print(f"SILVER BUILD DONE | ok={ok} failed={failed} RUN_ID={RUN_ID} duration={(datetime.now()-START).total_seconds():.1f}s")
print("=" * 80)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
