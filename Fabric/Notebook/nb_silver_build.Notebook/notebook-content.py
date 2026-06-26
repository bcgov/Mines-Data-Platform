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

# nb_silver_build — REGISTRY-DRIVEN, INCREMENTAL Bronze -> Silver.
# Per active object (app.object_registry), processes only the bronze delta since the last run
# using a per-entity dl_load_ts watermark (app.silver_load_state). load_type-aware:
#   INCREMENTAL + true PK -> MERGE upsert the latest-per-PK of the delta into silver (soft
#                            deletes propagate via deleted_ind; hard deletes need a full run).
#   FULL                  -> if a new snapshot arrived, overwrite silver from max(bronze_file_timestamp).
#   no PK                 -> reload from latest snapshot / distinct.
# Full rebuild of everything when app.silver_settings.force_full_all = 1 (self-clears), when an
# entity has no cursor yet, or when its silver table is missing.
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import StructType, StructField, StringType, LongType, TimestampType, BooleanType
from delta.tables import DeltaTable
from datetime import datetime
import uuid
import traceback

WORKSPACE_ID = "8f380f88-5ce5-48d1-9fa5-fbbfbe2685a0"
BRONZE_LH_ID = "8cd34a44-500a-47d9-aa2d-5ad0c2149858"
WAREHOUSE = "mines-data-platform-fabwh1"
SILVER_SCHEMA = "silver"
QUARANTINE_SCHEMA = "quarantine"

# bronze lineage/control columns — used for dedup/cursor, then dropped from silver.
# (The team's bronze loader stamps bronze_load_ts/bronze_load_date; an alt loader uses dl_load_ts.)
CTRL_COLS = {"dl_load_id", "bronze_file_name", "bronze_file_timestamp", "bronze_load_date",
             "bronze_load_ts", "dl_load_ts", "dl_rowhash"}
# bronze ingestion-time column, in preference order — auto-detected per table (schemas vary).
LOAD_TS_CANDIDATES = ["bronze_load_ts", "dl_load_ts"]


def load_ts_col(cols):
    for c in LOAD_TS_CANDIDATES:
        if c in cols:
            return c
    return None

spark.conf.set("spark.databricks.delta.schema.autoMerge.enabled", "true")  # MERGE schema evolution
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite", "LEGACY")
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "LEGACY")
spark.conf.set("spark.sql.parquet.int96RebaseModeInWrite", "LEGACY")
spark.conf.set("spark.sql.parquet.int96RebaseModeInRead", "LEGACY")


def bronze_path(table):
    return f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com/{BRONZE_LH_ID}/Tables/bronze/{table}/"


def normalize(name):
    return name.lower().replace(" ", "_").replace("-", "_").replace(".", "_")


def log_error(layer, run_id, entity, error_message, stack_trace=None, target_table=None):
    try:
        from com.microsoft.spark.fabric import Constants  # noqa: F401 — registers the .synapsesql writer
        from pyspark.sql.types import IntegerType
        sch = StructType([
            StructField("error_id", StringType()), StructField("layer", StringType()),
            StructField("log_id", LongType()), StructField("pipeline_name", StringType()),
            StructField("run_id", StringType()), StructField("entity", StringType()),
            StructField("target_table", StringType()), StructField("error_message", StringType()),
            StructField("error_code", StringType()), StructField("error_context", StringType()),
            StructField("stack_trace", StringType()),
        ])
        row = (str(uuid.uuid4()), layer, None, None, run_id, entity, target_table,
               (error_message or "(no message)")[:8000], None, None,
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


def read_cursor():
    try:
        from com.microsoft.spark.fabric import Constants  # noqa: F401
        return {r["entity"]: r["last_dl_load_ts"]
                for r in spark.read.synapsesql(f"{WAREHOUSE}.app.silver_load_state").collect()}
    except Exception as e:
        print(f"no silver_load_state yet ({e}); first run -> full for all")
        return {}


def read_force_full():
    try:
        from com.microsoft.spark.fabric import Constants  # noqa: F401
        rows = spark.read.synapsesql(f"{WAREHOUSE}.app.silver_settings").collect()
        return bool(rows[0]["force_full_all"]) if rows else False
    except Exception as e:
        print(f"no silver_settings ({e}); defaulting force_full_all=False")
        return False


def process(obj, last_ts, force_full):
    t = obj["bronze_table"]
    pk = obj.get("primary_key")
    load_type = (obj.get("load_type") or "FULL").upper()
    pk_cols = [c.strip() for c in (pk or "").split(",") if c.strip()]
    target = f"{SILVER_SCHEMA}.{t}"

    df = spark.read.format("delta").load(bronze_path(t))
    lts = load_ts_col(df.columns)   # bronze ingestion-time column actually present on THIS table
    # full rebuild if forced, no cursor yet, no load-ts column (can't do incremental), or no silver table
    full = bool(force_full) or (last_ts is None) or (lts is None) or (not spark.catalog.tableExists(target))

    if not full:
        df = df.filter(F.col(lts) > F.lit(last_ts))   # only the delta since last run
        # partition prune: bronze is partitioned by bronze_load_date, so bound it too
        if "bronze_load_date" in df.columns and hasattr(last_ts, "date"):
            df = df.filter(F.col("bronze_load_date") >= F.lit(last_ts.date()))

    # one pass for both the new high-water mark and the delta size
    if lts:
        a = df.agg(F.max(lts).alias("mx"), F.count(F.lit(1)).alias("cnt")).collect()[0]
        new_ts, delta_rows = a["mx"], a["cnt"]
    else:
        new_ts, delta_rows = None, df.count()
    if not full and delta_rows == 0:
        return {"status": "OK", "mode": "incremental", "action": "no-change",
                "rows_in": 0, "rows_out": None, "quar": 0, "new_ts": last_ts}

    # standardize + cleanse
    for c in df.columns:
        nc = normalize(c)
        if nc != c:
            df = df.withColumnRenamed(c, nc)
    string_cols = [f.name for f in df.schema.fields if isinstance(f.dataType, StringType)]
    for c in string_cols:
        df = df.withColumn(c, F.trim(F.col(c)))
    if string_cols:
        df = df.replace("", None, subset=string_cols)

    pk_ok = bool(pk_cols) and all(c in df.columns for c in pk_cols)

    # which version of a PK wins: prefer the SOURCE change time (registry watermark, e.g.
    # update_timestamp); fall back to bronze ingestion time. (cursor/snapshot still use lts.)
    wm = normalize(obj.get("watermark_column") or "")
    order_col = wm if (wm and wm in df.columns) else lts

    # dedup to current view (load_type-aware)
    if load_type == "INCREMENTAL" and pk_ok and order_col:
        w = Window.partitionBy(*[F.col(c) for c in pk_cols]).orderBy(F.col(order_col).desc())
        deduped = df.withColumn("_rn", F.row_number().over(w)).filter(F.col("_rn") == 1).drop("_rn")
    elif load_type == "FULL" and lts:
        latest = df.agg(F.max(lts)).collect()[0][0]   # latest full snapshot = newest load batch
        deduped = (df.filter(F.col(lts) == F.lit(latest)).dropDuplicates()
                   if latest is not None else df.dropDuplicates())
    else:
        deduped = df.dropDuplicates()

    # DQ: not-null on every PK column -> valid vs quarantine
    if pk_ok:
        cond = None
        for c in pk_cols:
            cond = F.col(c).isNotNull() if cond is None else (cond & F.col(c).isNotNull())
        valid, invalid, quar = deduped.filter(cond), deduped.filter(~cond), deduped.filter(~cond).count()
    else:
        valid, invalid, quar = deduped, None, 0

    drop_cols = [c for c in CTRL_COLS if c in valid.columns]
    staged = valid.drop(*drop_cols).withColumn("silver_load_ts", F.current_timestamp())

    # write: incremental INCREMENTAL+PK -> MERGE upsert; otherwise overwrite the current view
    if (not full) and load_type == "INCREMENTAL" and pk_ok and spark.catalog.tableExists(target):
        cond_sql = " AND ".join([f"t.{c} <=> s.{c}" for c in pk_cols])
        (DeltaTable.forName(spark, target).alias("t").merge(staged.alias("s"), cond_sql)
            .whenMatchedUpdateAll().whenNotMatchedInsertAll().execute())   # soft-deletes carry via columns
        action = "merged"
    else:
        (staged.write.format("delta").mode("overwrite")
            .option("overwriteSchema", "true").saveAsTable(target))
        action = "reloaded" if full else "overwritten"
    silver_rows = spark.table(target).count()

    if quar > 0:
        q = (invalid.withColumn("dq_rule", F.lit("not_null"))
             .withColumn("dq_reason", F.lit(f"null primary_key: {pk}"))
             .withColumn("run_id", F.lit(RUN_ID)).withColumn("quarantine_ts", F.current_timestamp()))
        (q.write.format("delta").mode("append").option("mergeSchema", "true")
            .saveAsTable(f"{QUARANTINE_SCHEMA}.{t}"))

    spark.sql(f"CREATE OR REPLACE VIEW {SILVER_SCHEMA}.v_{t} AS SELECT * FROM {target}")
    return {"status": "OK", "mode": ("full" if full else "incremental"), "action": action,
            "rows_in": int(delta_rows), "rows_out": int(silver_rows), "quar": int(quar),
            "new_ts": (new_ts if new_ts is not None else last_ts)}

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

print("=" * 80)
print("SILVER BUILD START (registry-driven, incremental)")
print("=" * 80)

RUN_ID = str(uuid.uuid4())
START = datetime.now()
results = []

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {SILVER_SCHEMA}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {QUARANTINE_SCHEMA}")

force_full = read_force_full()
cursor = read_cursor()                      # {entity: last_dl_load_ts}
state = dict(cursor)                         # final cursor to persist (carry unprocessed/failed forward)
print(f"force_full_all={force_full}; entities with a cursor={len(cursor)}")

from com.microsoft.spark.fabric import Constants  # noqa: F401
objs = [r.asDict() for r in
        spark.read.synapsesql(f"{WAREHOUSE}.app.object_registry").filter("is_active = true").collect()]
objs.sort(key=lambda o: (o.get("priority") or 100, o.get("bronze_table")))
print(f"active objects: {len(objs)}")

# Silver tables are independent -> process them in PARALLEL (thread pool submitting Spark jobs;
# FAIR scheduler overlaps the per-table driver overhead). state/results updated under a lock.
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

try:
    spark.conf.set("spark.scheduler.mode", "FAIR")   # better overlap; static conf -> non-fatal if rejected
except Exception as e:
    print(f"scheduler.mode set skipped (non-fatal): {e}")
MAX_WORKERS = 4   # 8 overwhelmed the Spark session (System_Cancelled_Session_Statements_Failed)
_lock = threading.Lock()


def run_one(obj):
    t = obj["bronze_table"]
    try:
        res = process(obj, cursor.get(t), force_full)
        with _lock:
            state[t] = res["new_ts"]        # advance cursor only on success
            results.append((t, res["rows_in"], res["rows_out"], res["quar"], "OK",
                            f"{res['action']}/{res['mode']}"))
        print(f"OK   {t}: {res['action']}/{res['mode']} in={res['rows_in']} out={res['rows_out']} quar={res['quar']}")
    except Exception as e:
        err = str(e)[:1000]
        print(f"FAILED {t}: {err}")
        log_error("silver", RUN_ID, t, err, traceback.format_exc(), target_table=f"silver.{t}")
        with _lock:
            results.append((t, None, None, None, "FAILED", err))


with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
    futs = [ex.submit(run_one, o) for o in objs]
    for _ in as_completed(futs):
        pass

# Persist the per-entity cursor (overwrite the whole small state table).
try:
    st_schema = StructType([
        StructField("entity", StringType()), StructField("last_dl_load_ts", TimestampType()),
        StructField("last_run_id", StringType()), StructField("last_mode", StringType()),
        StructField("rows_processed", LongType()), StructField("updated_date", TimestampType()),
    ])
    now = datetime.now()
    st_rows = [(e, ts, RUN_ID, None, None, now) for e, ts in state.items()]
    (spark.createDataFrame(st_rows, st_schema)
        .write.mode("overwrite").option("overwriteSchema", "true")
        .synapsesql(f"{WAREHOUSE}.app.silver_load_state"))
    print(f"wrote silver_load_state ({len(st_rows)} entities)")
except Exception as e:
    print(f"silver_load_state write failed: {e}")
    traceback.print_exc()

# Self-clear the full-reconcile flag (so force_full is a one-shot).
if force_full:
    try:
        ff_schema = StructType([StructField("force_full_all", BooleanType()),
                                StructField("updated_date", TimestampType())])
        (spark.createDataFrame([(False, datetime.now())], ff_schema)
            .write.mode("overwrite").option("overwriteSchema", "true")
            .synapsesql(f"{WAREHOUSE}.app.silver_settings"))
        print("reset force_full_all -> 0")
    except Exception as e:
        print(f"silver_settings reset failed: {e}")

# Run summary -> warehouse (verification) + bronze readback.
summary_schema = StructType([
    StructField("entity", StringType()), StructField("rows_in", LongType()),
    StructField("silver_rows", LongType()), StructField("quarantined_rows", LongType()),
    StructField("status", StringType()), StructField("detail", StringType()),
])
summary_df = (spark.createDataFrame(results, summary_schema)
              .withColumn("run_id", F.lit(RUN_ID)).withColumn("run_ts", F.current_timestamp()))
try:
    summary_df.write.mode("overwrite").option("overwriteSchema", "true").synapsesql(f"{WAREHOUSE}.app.silver_run_log")
except Exception as e:
    print(f"warehouse silver_run_log write failed: {e}")
try:
    bp = f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com/{BRONZE_LH_ID}/Tables/bronze/silver_run_log/"
    summary_df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(bp)
except Exception as e:
    print(f"bronze readback write failed: {e}")

ok = sum(1 for r in results if r[4] == "OK")
failed = sum(1 for r in results if r[4] == "FAILED")
print("=" * 80)
print(f"SILVER BUILD DONE | ok={ok} failed={failed} force_full={force_full} "
      f"RUN_ID={RUN_ID} duration={(datetime.now()-START).total_seconds():.1f}s")
print("=" * 80)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
