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

# nb_bronze_load — append-only Bronze loader. Discovers raw parquet under Files/raw,
# appends each new file once (idempotent via bronze_file_name), adds control columns.
from pyspark.sql.functions import lit, current_timestamp, sha2, concat_ws, col, coalesce
from notebookutils import mssparkutils
from datetime import datetime
import re
import uuid
import traceback

RAW_ROOT_PATH = "Files/raw"
TARGET_SCHEMA = "bronze"
SUMMARY_TABLE = "bronze.load_summary"

spark.conf.set("spark.sql.parquet.int96RebaseModeInRead", "LEGACY")
spark.conf.set("spark.sql.parquet.int96RebaseModeInWrite", "LEGACY")
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "LEGACY")
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite", "LEGACY")
spark.conf.set("spark.databricks.delta.schema.autoMerge.enabled", "true")


def get_table_name(entity):
    entity = entity.strip()
    if entity.lower().startswith("public."):
        entity = entity[7:]
    return entity.replace(".", "_").replace("-", "_").replace(" ", "_").lower()


def get_entities():
    items = mssparkutils.fs.ls(RAW_ROOT_PATH)
    return sorted([i.name.strip("/") for i in items if i.isDir])


def get_file_timestamp(file_name):
    m = re.search(r"(\d{8}_\d{6})", file_name)
    return datetime.strptime(m.group(1), "%Y%m%d_%H%M%S") if m else None


def get_all_parquet_files(entity):
    """Walk Files/raw/<entity>/<yyyy>/<mm>/<dd>/*.parquet (numeric folders only)."""
    found = []
    base = f"{RAW_ROOT_PATH}/{entity}"
    try:
        for y in mssparkutils.fs.ls(base):
            yy = y.name.strip("/")
            if not yy.isdigit():
                continue
            for m in mssparkutils.fs.ls(f"{base}/{yy}"):
                mm = m.name.strip("/")
                if not mm.isdigit():
                    continue
                for d in mssparkutils.fs.ls(f"{base}/{yy}/{mm}"):
                    dd = d.name.strip("/")
                    if not dd.isdigit():
                        continue
                    for f in mssparkutils.fs.ls(f"{base}/{yy}/{mm}/{dd}"):
                        if f.name.lower().endswith(".parquet"):
                            found.append((f.name, f.path))
    except Exception as e:
        print(f"Error listing {entity}: {e}")
    return found


def table_exists(t):
    try:
        return spark.catalog.tableExists(t)
    except Exception:
        return False


def file_already_loaded(table, file_name):
    if not table_exists(table):
        return False
    try:
        safe = file_name.replace("'", "''")
        return spark.sql(
            f"SELECT COUNT(*) FROM {table} WHERE bronze_file_name = '{safe}'"
        ).first()[0] > 0
    except Exception:
        return False


def load_file(entity, file_name, file_path):
    table_name = f"{TARGET_SCHEMA}.{get_table_name(entity)}"

    if file_already_loaded(table_name, file_name):
        return ("SKIPPED", None)

    file_ts = get_file_timestamp(file_name)
    if file_ts is None:
        return ("SKIPPED", None)

    df = (
        spark.read
        .option("int96RebaseMode", "LEGACY")
        .option("datetimeRebaseMode", "LEGACY")
        .parquet(file_path)
    )
    row_count = df.count()
    if row_count == 0:
        return ("SKIPPED", 0)

    data_cols = df.columns  # capture before adding control columns
    df = (
        df.withColumn("dl_load_id", lit(str(uuid.uuid4())))
          .withColumn("bronze_file_name", lit(file_name))
          .withColumn("bronze_file_timestamp", lit(file_ts))
          .withColumn("bronze_load_date", lit(file_ts.date()))
          .withColumn("dl_load_ts", current_timestamp())
          .withColumn(
              "dl_rowhash",
              sha2(concat_ws("||", *[coalesce(col(c).cast("string"), lit("")) for c in data_cols]), 256),
          )
    )

    if not table_exists(table_name):
        (df.write.format("delta").partitionBy("bronze_load_date")
           .mode("overwrite").option("overwriteSchema", "true").saveAsTable(table_name))
    else:
        (df.write.format("delta").mode("append")
           .option("mergeSchema", "true").saveAsTable(table_name))

    safe = file_name.replace("'", "''")
    target_count = spark.sql(
        f"SELECT COUNT(*) FROM {table_name} WHERE bronze_file_name = '{safe}'"
    ).first()[0]
    if target_count != row_count:
        raise Exception(f"Row mismatch {file_name}: source={row_count} target={target_count}")

    return ("LOADED", row_count)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

print("=" * 80)
print("BRONZE LOAD START")
print("=" * 80)

RUN_ID = str(uuid.uuid4())
START = datetime.now()
loaded = skipped = failed = 0
results = []

for entity in get_entities():
    files = get_all_parquet_files(entity)
    files = sorted(files, key=lambda x: get_file_timestamp(x[0]) or datetime.min)
    for file_name, file_path in files:
        try:
            status, rows = load_file(entity, file_name, file_path)
            if status == "LOADED":
                loaded += 1
            else:
                skipped += 1
            results.append({"entity": entity, "file_name": file_name, "status": status,
                            "rows": rows, "error": None})
        except Exception as e:
            failed += 1
            err = str(e)[:1000]
            print(f"FAILED {entity}/{file_name}: {err}")
            traceback.print_exc()
            results.append({"entity": entity, "file_name": file_name, "status": "FAILED",
                            "rows": None, "error": err})

# Write a queryable run summary into the bronze lakehouse (read later via SQL endpoint).
if results:
    try:
        summary_df = (
            spark.createDataFrame(results)
            .withColumn("run_id", lit(RUN_ID))
            .withColumn("run_ts", current_timestamp())
        )
        if table_exists(SUMMARY_TABLE):
            summary_df.write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable(SUMMARY_TABLE)
        else:
            summary_df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(SUMMARY_TABLE)
    except Exception as e:
        print(f"Error writing {SUMMARY_TABLE}: {e}")
        traceback.print_exc()

print("=" * 80)
print(f"BRONZE LOAD DONE | loaded={loaded} skipped={skipped} failed={failed}")
print(f"RUN_ID={RUN_ID} duration={(datetime.now() - START).total_seconds():.1f}s")
print("=" * 80)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
