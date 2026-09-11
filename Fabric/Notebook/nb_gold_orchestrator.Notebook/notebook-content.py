# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "896cd6b0-6cd0-47e5-8438-f50dde9564b8",
# META       "default_lakehouse_name": "mcm_mdp_lh1_dev",
# META       "default_lakehouse_workspace_id": "475a3e70-610e-49ae-be54-dd2c31167535",
# META       "known_lakehouses": [
# META         {
# META           "id": "896cd6b0-6cd0-47e5-8438-f50dde9564b8"
# META         }
# META       ]
# META     }
# META   }
# META }

# CELL ********************

%run nb_config

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

%run nb_gold_config

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

%run nb_util_gold

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, LongType
from notebookutils import mssparkutils
import uuid
import traceback

# WAREHOUSE comes from nb_config / vl_mdp.
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
        # notebooks log to their own table: the pipeline-owned app.error_log has a different (IDENTITY) shape
        edf.write.mode("append").synapsesql(f"{WAREHOUSE}.app.nb_error_log")
    except Exception as e:
        print(f"log_error failed (non-fatal): {e}")


# Build plan + DAG come from nb_gold_config (in Git), not hand-edited warehouse rows.
from com.microsoft.spark.fabric import Constants  # noqa: F401
nodes = {n["node_name"]: dict(n) for n in GOLD_BUILD if n["is_active"]}
deps = dict(GOLD_DEPENDENCY)
print("gold_build nodes:", list(nodes))

# Publish the plan to the warehouse for visibility only (non-fatal; the run does not read it back).
try:
    from pyspark.sql.types import IntegerType, BooleanType
    _plan_schema = StructType([StructField(k, StringType()) for k in (
        "node_name", "gold_object", "object_type", "transform_notebook", "source_table", "table_type",
        "load_strategy", "surrogate_key", "business_keys", "non_historized_columns", "watermark_column")]
        + [StructField("last_n_days", IntegerType()), StructField("is_active", BooleanType())])
    _cols = [f.name for f in _plan_schema.fields]
    (spark.createDataFrame([tuple(n[c] for c in _cols) for n in GOLD_BUILD], _plan_schema)
        .withColumn("modified_date", F.current_timestamp())
        .write.mode("overwrite").option("overwriteSchema", "true").synapsesql(f"{WAREHOUSE}.app.gold_build"))
    (spark.createDataFrame([(k, v) for k, v in GOLD_DEPENDENCY.items()], "node_name string, depends_on string")
        .withColumn("modified_date", F.current_timestamp())
        .write.mode("overwrite").option("overwriteSchema", "true").synapsesql(f"{WAREHOUSE}.app.gold_dependency"))
except Exception as e:
    print(f"plan publish to warehouse skipped (non-fatal): {e}")


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

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# table_type -> builder; load_strategy (incremental|full) is a separate column. For dimensions and
# upsert facts, 'full' means a complete-snapshot source so absent business keys are (soft) deleted.
DIM_SCD = {"type1_dimension": 1, "type2_dimension": 2}
FACT_MODE = {"append_fact": "append", "upsert_fact": "upsert", "reload_fact": "reload"}

results = []

# 0) standalone builders (calendar, lookups, NoW facts) — independent, run in parallel first
print(f"\n===== STANDALONE: {STANDALONE_NOTEBOOKS} =====")
_standalone = [{"name": nb, "path": nb, "args": {}, "dependencies": []} for nb in STANDALONE_NOTEBOOKS]
try:
    rm = mssparkutils.notebook.runMultiple({"activities": _standalone, "timeoutInSeconds": 3600, "concurrency": 0})
    print(f"runMultiple standalone result: {rm}")
    results += [(nb, nb, "OK", 0, "standalone") for nb in STANDALONE_NOTEBOOKS]
except Exception as e:
    print(f"runMultiple standalone failed: {e} — running one by one")
    for nb in STANDALONE_NOTEBOOKS:
        try:
            mssparkutils.notebook.run(nb, 3600)
            results.append((nb, nb, "OK", 0, "standalone"))
        except Exception as e2:
            log_error(nb, f"standalone run failed: {e2}", traceback.format_exc(), target_table=nb)
            results.append((nb, nb, "FAILED", 0, str(e2)[:200]))

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
        # Fallback: runMultiple is all-or-nothing (one missing/bad notebook aborts the whole level),
        # so run the remaining transforms one by one and let only the bad node fail at merge time.
        for a in activities:
            try:
                mssparkutils.notebook.run(a["path"], 3600)
                print(f"fallback run OK: {a['name']}")
            except Exception as e2:
                print(f"fallback run FAILED: {a['name']}: {str(e2)[:300]}")
                log_error(a["name"], f"fallback run failed: {e2}", traceback.format_exc(), target_table=a["name"])

    # 2) merge each node in this level into gold (orchestrator does the merge)
    for n in level:
        c = nodes[n]
        try:
            tt = (c.get("table_type") or "").strip()
            ls = (c.get("load_strategy") or "incremental").strip()
            if tt in DIM_SCD:
                res = build_dimension(c["gold_object"], c["source_table"], DIM_SCD[tt],
                                      c["surrogate_key"], c["business_keys"],
                                      c.get("non_historized_columns"), load_mode=ls)
            elif tt in FACT_MODE:
                res = build_fact(c["gold_object"], c["source_table"], FACT_MODE[tt], ls,
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

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
