# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": { "name": "synapse_pyspark" },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "8cd34a44-500a-47d9-aa2d-5ad0c2149858",
# META       "default_lakehouse_name": "mines_data_platform_lh1",
# META       "default_lakehouse_workspace_id": "8f380f88-5ce5-48d1-9fa5-fbbfbe2685a0",
# META       "known_lakehouses": [ { "id": "8cd34a44-500a-47d9-aa2d-5ad0c2149858" } ]
# META     }
# META   }
# META }

# CELL ********************

# nb_bronze_load — append-only Bronze loader, OPTIMIZED.
# Per entity: read ALL new raw parquet files in ONE spark.read (Spark parallelizes internally),
# stamp per-file lineage from input_file_name(), write ONCE. Idempotency via a manifest
# (bronze.load_manifest) — no per-file COUNT scans. Entities processed in PARALLEL (thread pool).
# REBUILD=True drops every bronze table + the manifest and reloads from raw (our audit columns
# become the single source of truth); set False after the one-time rebuild.
from pyspark.sql.functions import (lit, current_timestamp, sha2, concat_ws, col, coalesce,
                                   input_file_name, element_at, split, regexp_extract,
                                   to_timestamp, to_date)
from notebookutils import mssparkutils
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import re
import uuid
import traceback

WORKSPACE_ID = "8f380f88-5ce5-48d1-9fa5-fbbfbe2685a0"
BRONZE_LH_ID = "8cd34a44-500a-47d9-aa2d-5ad0c2149858"
RAW_ROOT_PATH = "Files/raw"
TARGET_SCHEMA = "bronze"
MANIFEST_TABLE = "bronze.load_manifest"
# read the manifest by absolute path (spark.catalog can lag across sessions)
MANIFEST_PATH = f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com/{BRONZE_LH_ID}/Tables/bronze/load_manifest"
SUMMARY_TABLE = "bronze.load_summary"
REBUILD = True          # one-time full rebuild; set False afterwards for incremental (manifest-skip)
MAX_WORKERS = 8

spark.conf.set("spark.sql.parquet.int96RebaseModeInRead", "LEGACY")
spark.conf.set("spark.sql.parquet.int96RebaseModeInWrite", "LEGACY")
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "LEGACY")
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite", "LEGACY")
spark.conf.set("spark.databricks.delta.schema.autoMerge.enabled", "true")
try:
    spark.conf.set("spark.scheduler.mode", "FAIR")
except Exception as e:
    print(f"scheduler.mode set skipped: {e}")


def get_table_name(entity):
    e = entity.strip()
    if e.lower().startswith("public."):
        e = e[7:]
    return e.replace(".", "_").replace("-", "_").replace(" ", "_").lower()


def get_entities():
    return sorted([i.name.strip("/") for i in mssparkutils.fs.ls(RAW_ROOT_PATH) if i.isDir])


def get_all_parquet_files(entity):
    """Walk Files/raw/<entity>/<yyyy>/<mm>/<dd>/*.parquet (numeric folders only)."""
    found, base = [], f"{RAW_ROOT_PATH}/{entity}"
    try:
        for y in mssparkutils.fs.ls(base):
            if not y.name.strip("/").isdigit():
                continue
            for m in mssparkutils.fs.ls(y.path):
                if not m.name.strip("/").isdigit():
                    continue
                for d in mssparkutils.fs.ls(m.path):
                    if not d.name.strip("/").isdigit():
                        continue
                    for f in mssparkutils.fs.ls(d.path):
                        if f.name.lower().endswith(".parquet"):
                            found.append((f.name, f.path))
    except Exception as e:
        print(f"list {entity}: {e}")
    return found


def file_ts(name):
    m = re.search(r"(\d{8}_\d{6})", name)
    return datetime.strptime(m.group(1), "%Y%m%d_%H%M%S") if m else None


def load_manifest():
    """Set of (entity, bronze_file_name) already loaded — cheap idempotency, no table scans.
    Read by path (spark.catalog.tableExists can lag across sessions)."""
    try:
        return {(r["entity"], r["bronze_file_name"])
                for r in spark.read.format("delta").load(MANIFEST_PATH).collect()}
    except Exception as e:
        print(f"manifest read (treating as empty): {e}")
        return set()

# METADATA ********************

# META { "language": "python", "language_group": "synapse_pyspark" }

# CELL ********************

print("=" * 80)
print(f"BRONZE LOAD START (optimized){' [REBUILD]' if REBUILD else ''}")
print("=" * 80)

RUN_ID = str(uuid.uuid4())
START = datetime.now()
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {TARGET_SCHEMA}")

if REBUILD:
    spark.sql(f"DROP TABLE IF EXISTS {MANIFEST_TABLE}")
    loaded = set()
else:
    loaded = load_manifest()
print(f"already-loaded files in manifest: {len(loaded)}")

results, manifest_rows = [], []
_lock = threading.Lock()


def process_entity(entity):
    table = get_table_name(entity)
    target = f"{TARGET_SCHEMA}.{table}"
    if REBUILD:
        spark.sql(f"DROP TABLE IF EXISTS {target}")

    files = get_all_parquet_files(entity)
    todo = [(n, p) for (n, p) in files if file_ts(n) is not None and (entity, n) not in loaded]
    if not todo:
        return (entity, "SKIPPED", 0, [])

    paths = [p for (_, p) in todo]
    df = spark.read.option("int96RebaseMode", "LEGACY").option("datetimeRebaseMode", "LEGACY").parquet(*paths)
    data_cols = df.columns  # original source columns (before control columns)
    df = (df
          .withColumn("bronze_file_name", element_at(split(input_file_name(), "/"), -1))
          .withColumn("bronze_file_timestamp",
                      to_timestamp(regexp_extract(col("bronze_file_name"), r"(\d{8}_\d{6})", 1), "yyyyMMdd_HHmmss"))
          .withColumn("bronze_load_date", to_date(col("bronze_file_timestamp")))
          .withColumn("dl_load_id", lit(RUN_ID))
          .withColumn("dl_load_ts", current_timestamp())
          .withColumn("dl_rowhash",
                      sha2(concat_ws("||", *[coalesce(col(c).cast("string"), lit("")) for c in data_cols]), 256)))

    mode = "overwrite" if REBUILD else "append"   # append creates the table if absent
    opt = "overwriteSchema" if mode == "overwrite" else "mergeSchema"
    (df.write.format("delta").partitionBy("bronze_load_date").mode(mode)
        .option(opt, "true").saveAsTable(target))

    rows = [(entity, n, file_ts(n)) for (n, _) in todo]
    return (entity, "LOADED", len(todo), rows)


with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
    futs = {ex.submit(process_entity, e): e for e in get_entities()}
    for fut in as_completed(futs):
        e = futs[fut]
        try:
            entity, status, nfiles, mrows = fut.result()
            with _lock:
                results.append((entity, status, nfiles, None))
                manifest_rows.extend(mrows)
            print(f"{status:8} {entity}: {nfiles} files")
        except Exception as ex2:
            with _lock:
                results.append((e, "FAILED", 0, str(ex2)[:1000]))
            print(f"FAILED {e}: {ex2}")
            traceback.print_exc()

# METADATA ********************

# META { "language": "python", "language_group": "synapse_pyspark" }

# CELL ********************

from pyspark.sql.types import StructType, StructField, StringType, LongType, TimestampType

# Manifest (append loaded files; REBUILD already dropped it so this is a fresh write).
if manifest_rows:
    msch = StructType([StructField("entity", StringType()), StructField("bronze_file_name", StringType()),
                       StructField("bronze_file_timestamp", TimestampType())])
    mdf = (spark.createDataFrame(manifest_rows, msch)
           .withColumn("run_id", lit(RUN_ID)).withColumn("loaded_at", current_timestamp()))
    mode = "overwrite" if REBUILD else "append"
    mdf.write.format("delta").mode(mode).option("mergeSchema", "true").saveAsTable(MANIFEST_TABLE)

# Run summary.
ssch = StructType([StructField("entity", StringType()), StructField("status", StringType()),
                   StructField("files_loaded", LongType()), StructField("error", StringType())])
srows = [(r[0], r[1], int(r[2]), r[3]) for r in results]
(spark.createDataFrame(srows, ssch)
    .withColumn("run_id", lit(RUN_ID)).withColumn("run_ts", current_timestamp())
    .write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(SUMMARY_TABLE))

loaded_n = sum(1 for r in results if r[1] == "LOADED")
skipped_n = sum(1 for r in results if r[1] == "SKIPPED")
failed_n = sum(1 for r in results if r[1] == "FAILED")
files_n = sum(r[2] for r in results)
print("=" * 80)
print(f"BRONZE LOAD DONE | entities loaded={loaded_n} skipped={skipped_n} failed={failed_n} | "
      f"files={files_n} | RUN_ID={RUN_ID} duration={(datetime.now()-START).total_seconds():.1f}s")
print("=" * 80)

# METADATA ********************

# META { "language": "python", "language_group": "synapse_pyspark" }
