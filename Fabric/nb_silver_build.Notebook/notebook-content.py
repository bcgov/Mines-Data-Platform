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
# META     }
# META   }
# META }

# CELL ********************

# nb_silver_build — Bronze -> Silver: standardize, cleanse, dedup-to-latest-per-PK,
# not-null DQ with bad rows quarantined. Silver lakehouse is the default; Bronze is
# read cross-lakehouse via absolute OneLake paths. Lakehouse-only logging this cut
# (silver.load_summary); routing dq_result/error_log to the warehouse via synapsesql
# is a noted follow-up.
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import StructType, StructField, StringType, LongType
from datetime import datetime
import uuid
import traceback

WORKSPACE_ID = "8f380f88-5ce5-48d1-9fa5-fbbfbe2685a0"
BRONZE_LH_ID = "8cd34a44-500a-47d9-aa2d-5ad0c2149858"
SILVER_SCHEMA = "silver"
QUARANTINE_SCHEMA = "quarantine"
SUMMARY_TABLE = "silver.load_summary"

# v1 entities (registry-aligned; object_registry seeded separately). PK drives dedup;
# not_null drives the DQ quarantine split.
V1 = [
    # NOTE: the conformed 'mine' hub is absent from bronze (public.mine did not land in
    # Files/raw — a raw-landing gap to resolve before dim_mine can be built). Re-add when present.
    {"entity": "mine_incident",    "pk": "mine_incident_id",    "not_null": ["mine_incident_id"]},
    {"entity": "permit",           "pk": "permit_id",           "not_null": ["permit_id"]},
    {"entity": "permit_amendment", "pk": "permit_amendment_id", "not_null": ["permit_amendment_id"]},
]

spark.conf.set("spark.databricks.delta.schema.autoMerge.enabled", "true")


def bronze_path(table):
    return f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com/{BRONZE_LH_ID}/Tables/bronze/{table}/"


def normalize(name):
    return name.lower().replace(" ", "_").replace("-", "_").replace(".", "_")


def process(cfg):
    entity = cfg["entity"]
    df = spark.read.format("delta").load(bronze_path(entity))
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

    # 3. dedup to latest per PK (by bronze load timestamp)
    pk = cfg["pk"]
    if pk in df.columns and "dl_load_ts" in df.columns:
        w = Window.partitionBy(pk).orderBy(F.col("dl_load_ts").desc())
        df = df.withColumn("_rn", F.row_number().over(w)).filter(F.col("_rn") == 1).drop("_rn")
    elif pk in df.columns:
        df = df.dropDuplicates([pk])
    else:
        df = df.dropDuplicates()

    # 4. DQ: not-null on key columns -> valid vs quarantine
    nn_cols = [c for c in cfg["not_null"] if c in df.columns]
    cond = None
    for c in nn_cols:
        cond = F.col(c).isNotNull() if cond is None else (cond & F.col(c).isNotNull())
    if cond is not None:
        valid_df = df.filter(cond)
        invalid_df = df.filter(~cond)   # any required col is null
        quarantined = invalid_df.count()
    else:
        valid_df, invalid_df, quarantined = df, None, 0

    # 5. write silver
    valid_df = valid_df.withColumn("silver_load_ts", F.current_timestamp())
    (valid_df.write.format("delta").mode("overwrite")
        .option("overwriteSchema", "true").saveAsTable(f"{SILVER_SCHEMA}.{entity}"))
    silver_rows = valid_df.count()

    # 6. quarantine failing rows
    if quarantined > 0:
        reason = "null in one of: " + ", ".join(nn_cols)
        q_df = (invalid_df
                .withColumn("dq_rule", F.lit("not_null"))
                .withColumn("dq_reason", F.lit(reason))
                .withColumn("run_id", F.lit(RUN_ID))
                .withColumn("quarantine_ts", F.current_timestamp()))
        (q_df.write.format("delta").mode("append")
            .option("mergeSchema", "true").saveAsTable(f"{QUARANTINE_SCHEMA}.{entity}"))

    # 7. current-state view
    spark.sql(f"CREATE OR REPLACE VIEW {SILVER_SCHEMA}.v_{entity} AS SELECT * FROM {SILVER_SCHEMA}.{entity}")

    return bronze_rows, silver_rows, quarantined

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

print("=" * 80)
print("SILVER BUILD START")
print("=" * 80)

RUN_ID = str(uuid.uuid4())
START = datetime.now()
results = []

# Fabric schema-enabled lakehouses do NOT auto-create schemas on saveAsTable.
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {SILVER_SCHEMA}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {QUARANTINE_SCHEMA}")

for cfg in V1:
    entity = cfg["entity"]
    try:
        bronze_rows, silver_rows, quarantined = process(cfg)
        print(f"OK   {entity}: bronze={bronze_rows} silver={silver_rows} quarantined={quarantined}")
        results.append((entity, int(bronze_rows), int(silver_rows), int(quarantined), "OK", None))
    except Exception as e:
        err = str(e)[:1000]
        print(f"FAILED {entity}: {err}")
        traceback.print_exc()
        results.append((entity, None, None, None, "FAILED", err))

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

# Reliable readback: write the run log to the BRONZE lakehouse (writes proven + its SQL
# endpoint syncs fast), so per-entity status/errors are queryable from CI via pyodbc.
try:
    bronze_log_path = f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com/{BRONZE_LH_ID}/Tables/bronze/silver_run_log/"
    summary_df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(bronze_log_path)
    print("wrote run log to bronze.silver_run_log")
except Exception as e:
    print(f"bronze readback write failed: {e}")
    traceback.print_exc()

# Best-effort silver-local summary too.
try:
    summary_df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(SUMMARY_TABLE)
except Exception as e:
    print(f"Error writing {SUMMARY_TABLE}: {e}")
    traceback.print_exc()

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
