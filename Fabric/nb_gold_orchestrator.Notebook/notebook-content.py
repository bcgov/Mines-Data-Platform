# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": { "name": "synapse_pyspark" },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "5e43f78b-2156-4469-980e-bffda0295fac",
# META       "default_lakehouse_name": "lh_gold",
# META       "default_lakehouse_workspace_id": "8f380f88-5ce5-48d1-9fa5-fbbfbe2685a0",
# META       "known_lakehouses": [ { "id": "5e43f78b-2156-4469-980e-bffda0295fac" } ]
# META     },
# META     "warehouse": {
# META       "default_warehouse": "dad1e7ab-adc2-bd51-408b-33e59ed9a608",
# META       "known_warehouses": [ { "id": "dad1e7ab-adc2-bd51-408b-33e59ed9a608", "type": "Datawarehouse" } ]
# META     }
# META   }
# META }

# CELL ********************

%run nb_util_gold

# METADATA ********************

# META { "language": "python", "language_group": "synapse_pyspark" }

# CELL ********************

from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, LongType
from notebookutils import mssparkutils
import uuid
import traceback

WAREHOUSE = "mines-data-platform-fabwh1"
RUN_ID = str(uuid.uuid4())

# Source data contains pre-1900 timestamps (e.g. permit_amendment) — rebase on write/read.
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite", "LEGACY")
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "LEGACY")
spark.conf.set("spark.sql.parquet.int96RebaseModeInWrite", "LEGACY")
spark.conf.set("spark.sql.parquet.int96RebaseModeInRead", "LEGACY")


def log_error(entity, error_message, stack_trace=None, target_table=None):
    try:
        from com.microsoft.spark.fabric import Constants  # noqa: F401
        from pyspark.sql.types import IntegerType
        sch = StructType([
            StructField("error_id", StringType()), StructField("layer", StringType()),
            StructField("log_id", LongType()), StructField("pipeline_name", StringType()),
            StructField("run_id", StringType()), StructField("entity", StringType()),
            StructField("target_table", StringType()), StructField("error_message", StringType()),
            StructField("error_code", StringType()), StructField("error_context", StringType()),
            StructField("stack_trace", StringType()),
        ])
        row = (str(uuid.uuid4()), "gold", None, None, RUN_ID, entity, target_table,
               (error_message or "(no message)")[:8000], None, None,
               (stack_trace[:8000] if stack_trace else None))
        # SQL TRY/CATCH fields (used by other SQL-based writers) left null; appended after
        # created_date to match the table's physical order (name- and position-safe).
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


# Read build config + DAG from the warehouse (split tables: metadata + dependencies).
from com.microsoft.spark.fabric import Constants  # noqa: F401
build = spark.read.synapsesql(f"{WAREHOUSE}.app.gold_build").filter("is_active = true")
nodes = {r["node_name"]: r.asDict() for r in build.collect()}
deps = {r["node_name"]: (r["depends_on"] or "")
        for r in spark.read.synapsesql(f"{WAREHOUSE}.app.gold_dependency").collect()}
print("gold_build nodes:", list(nodes))


def deps_of(n):
    # parents from gold_dependency (comma list). Ignore parents that aren't active build
    # nodes so an inactive/absent parent can't deadlock level computation.
    return [d.strip() for d in deps.get(n, "").split(",") if d.strip() and d.strip() in nodes]


# Topological levels (Kahn): independent nodes share a level (run in parallel).
levels, done, remaining = [], set(), set(nodes)
while remaining:
    level = [n for n in remaining if all(d in done for d in deps_of(n))]
    if not level:
        raise Exception(f"DAG cycle or missing dependency among: {sorted(remaining)}")
    level.sort()
    levels.append(level)
    done |= set(level)
    remaining -= set(level)
print("execution levels:", levels)

# METADATA ********************

# META { "language": "python", "language_group": "synapse_pyspark" }

# CELL ********************

# dimension table_type -> (scd_type, load_mode). *_full handles source deletes; *_incremental does not.
DIM_MAP = {
    "type1_incremental_dimension": (1, "incremental"),
    "type1_full_dimension":        (1, "full"),
    "type2_incremental_dimension": (2, "incremental"),
    "type2_full_dimension":        (2, "full"),
}
FACT_MAP = {"append_only_fact": "append", "upsert_fact": "upsert", "reload_fact": "reload"}

results = []
for li, level in enumerate(levels):
    print(f"\n===== LEVEL {li}: {level} =====")

    # 1) run this level's transform notebooks in parallel (they materialize the stg.* tables)
    activities = [{
        "name": nodes[n]["transform_notebook"],
        "path": nodes[n]["transform_notebook"],
        "args": {},
        "dependencies": [],
    } for n in level]
    try:
        rm = mssparkutils.notebook.runMultiple({"activities": activities, "timeoutInSeconds": 3600, "concurrency": 0})
        print(f"runMultiple L{li} result: {rm}")
        log_error(f"runMultiple_L{li}", f"transform result: {str(rm)[:6000]}", target_table=str(level))
    except Exception as e:
        print(f"runMultiple failed for level {li}: {e}")
        log_error(f"runMultiple_L{li}", f"runMultiple raised: {e}", traceback.format_exc())

    # 2) merge each node in this level into gold (orchestrator does the merge)
    for n in level:
        c = nodes[n]
        try:
            tt = (c.get("table_type") or "").strip()
            if tt in DIM_MAP:
                scd, lm = DIM_MAP[tt]
                res = build_dimension(c["gold_object"], c["source_table"], scd,
                                      c["surrogate_key"], c["business_keys"],
                                      c.get("non_historized_columns"), load_mode=lm)
            elif tt in FACT_MAP:
                res = build_fact(c["gold_object"], c["source_table"], FACT_MAP[tt],
                                 c.get("business_keys"), c.get("watermark_column"), c.get("last_n_days"))
            else:
                raise Exception(f"unknown table_type '{tt}' for node {n}")
            print(n, "->", res)
            detail = str(res.get("action"))
            if res.get("deleted"):
                detail += f" del={res['deleted']}"
            results.append((n, c["gold_object"], "OK", int(res.get("rows") or 0), detail))
        except Exception as e:
            err = str(e)[:1000]
            print(f"MERGE FAILED {n}: {err}")
            traceback.print_exc()
            log_error(n, err, traceback.format_exc(), target_table=c["gold_object"])
            results.append((n, c["gold_object"], "FAILED", 0, err[:200]))

# Write a build log to the warehouse for reliable verification.
try:
    sch = StructType([
        StructField("node_name", StringType()), StructField("gold_object", StringType()),
        StructField("status", StringType()), StructField("rows", LongType()), StructField("detail", StringType()),
    ])
    (spark.createDataFrame(results, sch)
        .withColumn("run_id", F.lit(RUN_ID)).withColumn("run_ts", F.current_timestamp())
        .write.mode("overwrite").option("overwriteSchema", "true").synapsesql(f"{WAREHOUSE}.app.gold_run_log"))
    print("wrote app.gold_run_log")
except Exception as e:
    print(f"gold_run_log write failed: {e}")

ok = sum(1 for r in results if r[2] == "OK")
print(f"\nGOLD BUILD DONE | ok={ok} failed={len(results)-ok} RUN_ID={RUN_ID}")

# METADATA ********************

# META { "language": "python", "language_group": "synapse_pyspark" }
