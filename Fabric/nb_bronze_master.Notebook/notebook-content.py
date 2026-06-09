# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "8cd34a44-500a-47d9-aa2d-5ad0c2149858",
# META       "default_lakehouse_name": "mines_data_platform_lh1",
# META       "default_lakehouse_workspace_id": "8f380f88-5ce5-48d1-9fa5-fbbfbe2685a0",
# META       "known_lakehouses": [
# META         {
# META           "id": "8cd34a44-500a-47d9-aa2d-5ad0c2149858"
# META         }
# META       ]
# META     },
# META     "warehouse": {
# META       "default_warehouse": "dad1e7ab-adc2-bd51-408b-33e59ed9a608",
# META       "known_warehouses": [
# META         {
# META           "id": "dad1e7ab-adc2-bd51-408b-33e59ed9a608",
# META           "type": "Datawarehouse"
# META         }
# META       ]
# META     }
# META   }
# META }

# CELL ********************

# Welcome to your new notebook
# Type here in the cell editor to add code!


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# # ==========================================
# # IMPORTS
# # ==========================================

# from pyspark.sql.functions import col
# from com.microsoft.spark.fabric import Constants


# # ==========================================
# # CONFIGURATION
# # ==========================================

# # Replace this with your actual Fabric Warehouse name
# warehouse_name = "mines-data-platform-fabwh1"

# # Schema and table name
# schema_name = "app"
# table_name = "pipeline_control"


# # ==========================================
# # READ PIPELINE_CONTROL FROM WAREHOUSE
# # ==========================================

# pipeline_control_df = (
#     spark.read
#     .synapsesql(f"{warehouse_name}.{schema_name}.{table_name}")
# )


# # ==========================================
# # DISPLAY FULL TABLE
# # ==========================================

# display(pipeline_control_df)


# # ==========================================
# # OPTIONAL: DISPLAY ONLY ACTIVE RECORDS
# # ==========================================

# active_pipeline_control_df = (
#     pipeline_control_df
#     .filter(col("is_active") == 1)
# )

# display(active_pipeline_control_df)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# # =====================================================================================
# # NOTEBOOK NAME : nb_load_bronze
# #
# # PURPOSE
# # -------
# # Load Raw Parquet Files into Bronze Tables
# #
# # FEATURES
# # --------
# # 1. Historical Data Retained
# # 2. Same-Day Re-Runs Do Not Create Duplicates
# # 3. Original Datatypes Preserved
# # 4. Row Count Validation
# # 5. Source vs Target Value Validation
# # 6. Delta Storage
# # 7. Partitioned by bronze_load_date
# # =====================================================================================

# from pyspark.sql.functions import (
#     lit,
#     current_timestamp,
#     col
# )

# from datetime import datetime
# import traceback

# # =====================================================================================
# # CONFIGURATION
# # =====================================================================================

# SOURCE_ENTITY = "camp_detail"

# LOAD_YEAR = "2026"
# LOAD_MONTH = "05"
# LOAD_DAY = "26"

# SOURCE_PATH = (
#     f"Files/raw/{SOURCE_ENTITY}/"
#     f"{LOAD_YEAR}/"
#     f"{LOAD_MONTH}/"
#     f"{LOAD_DAY}"
# )

# TARGET_SCHEMA = "bronze"
# TARGET_TABLE = SOURCE_ENTITY

# LOAD_DATE = f"{LOAD_YEAR}-{LOAD_MONTH}-{LOAD_DAY}"

# START_TIME = datetime.now()

# # =====================================================================================
# # START
# # =====================================================================================

# try:

#     print("=" * 100)
#     print(f"STARTING BRONZE LOAD : {TARGET_SCHEMA}.{TARGET_TABLE}")
#     print("=" * 100)

#     print(f"Source Path : {SOURCE_PATH}")

#     # =================================================================================
#     # READ SOURCE
#     # =================================================================================

#     source_df = spark.read.parquet(SOURCE_PATH)

#     source_count = source_df.count()

#     print(f"Source Row Count : {source_count}")

#     if source_count == 0:
#         raise Exception(
#             f"No records found under {SOURCE_PATH}"
#         )

#     print("\nSOURCE SCHEMA")
#     print("=" * 100)

#     source_df.printSchema()

#     # =================================================================================
#     # SAMPLE SOURCE VALUES
#     # =================================================================================

#     print("\nSOURCE SAMPLE")

#     display(
#         source_df
#             .select(
#                 "activity_detail_id",
#                 "number_people",
#                 "number_structures"
#             )
#             .orderBy("activity_detail_id")
#             .limit(20)
#     )

#     # =================================================================================
#     # AUDIT COLUMNS
#     # =================================================================================

#     load_df = (
#         source_df
#         .withColumn(
#             "bronze_load_date",
#             lit(LOAD_DATE).cast("date")
#         )
#         .withColumn(
#             "bronze_load_ts",
#             current_timestamp()
#         )
#     )

#     # =================================================================================
#     # CREATE SCHEMA
#     # =================================================================================

#     spark.sql("""
#         CREATE SCHEMA IF NOT EXISTS bronze
#     """)

#     table_name = f"{TARGET_SCHEMA}.{TARGET_TABLE}"

#     table_exists = spark.catalog.tableExists(
#         table_name
#     )

#     # =================================================================================
#     # FIRST LOAD
#     # =================================================================================

#     if not table_exists:

#         print(
#             f"Creating Table : {table_name}"
#         )

#         (
#             load_df.write
#                    .format("delta")
#                    .partitionBy("bronze_load_date")
#                    .mode("overwrite")
#                    .option(
#                        "overwriteSchema",
#                        "true"
#                    )
#                    .saveAsTable(table_name)
#         )

#     # =================================================================================
#     # RELOAD SAME DAY
#     # =================================================================================

#     else:

#         print(
#             f"Deleting Existing Records "
#             f"for {LOAD_DATE}"
#         )

#         spark.sql(f"""
#             DELETE
#             FROM {table_name}
#             WHERE bronze_load_date =
#                   DATE('{LOAD_DATE}')
#         """)

#         (
#             load_df.write
#                    .format("delta")
#                    .mode("append")
#                    .saveAsTable(table_name)
#         )

#     # =================================================================================
#     # ROW COUNT VALIDATION
#     # =================================================================================

#     target_count = spark.sql(f"""
#         SELECT COUNT(*)
#         FROM {table_name}
#         WHERE bronze_load_date =
#               DATE('{LOAD_DATE}')
#     """).collect()[0][0]

#     print(
#         f"\nTarget Row Count : {target_count}"
#     )

#     if source_count != target_count:

#         raise Exception(
#             f"""
#             ROW COUNT VALIDATION FAILED

#             Source Count : {source_count}
#             Target Count : {target_count}
#             """
#         )

#     # =================================================================================
#     # SOURCE VS TARGET VALIDATION
#     # =================================================================================

#     print("\nCOMPARING SOURCE AND TARGET VALUES")

#     source_compare = (
#         source_df
#         .select(
#             "activity_detail_id",
#             "number_people",
#             "number_structures"
#         )
#     )

#     target_compare = (
#         spark.table(table_name)
#              .filter(
#                  col("bronze_load_date") == LOAD_DATE
#              )
#              .select(
#                  "activity_detail_id",
#                  "number_people",
#                  "number_structures"
#              )
#     )

#     mismatch_df = (
#         source_compare.alias("s")
#         .join(
#             target_compare.alias("t"),
#             "activity_detail_id",
#             "full"
#         )
#         .filter(
#             (col("s.number_people")
#              != col("t.number_people"))
#             |
#             (col("s.number_structures")
#              != col("t.number_structures"))
#         )
#     )

#     mismatch_count = mismatch_df.count()

#     print(
#         f"Mismatch Count : {mismatch_count}"
#     )

#     if mismatch_count > 0:

#         print(
#             "\nSOURCE AND TARGET VALUES DIFFER"
#         )

#         display(
#             mismatch_df.orderBy(
#                 "activity_detail_id"
#             )
#         )

#         raise Exception(
#             f"""
#             VALUE VALIDATION FAILED

#             Mismatch Count :
#             {mismatch_count}
#             """
#         )

#     print(
#         "\nSource and Target Values Match"
#     )

#     # =================================================================================
#     # LOAD HISTORY
#     # =================================================================================

#     print("\nLOAD HISTORY")

#     display(
#         spark.sql(f"""
#             SELECT
#                 bronze_load_date,
#                 COUNT(*) AS row_count
#             FROM {table_name}
#             GROUP BY bronze_load_date
#             ORDER BY bronze_load_date
#         """)
#     )

#     # =================================================================================
#     # TARGET SCHEMA
#     # =================================================================================

#     print("\nTARGET SCHEMA")

#     spark.table(
#         table_name
#     ).printSchema()

#     # =================================================================================
#     # TARGET SAMPLE
#     # =================================================================================

#     print("\nTARGET SAMPLE")

#     display(
#         spark.sql(f"""
#             SELECT *
#             FROM {table_name}
#             ORDER BY activity_detail_id
#             LIMIT 20
#         """)
#     )

#     END_TIME = datetime.now()

#     print("=" * 100)
#     print("BRONZE LOAD SUCCESSFUL")
#     print("=" * 100)

#     print(f"Table Name       : {table_name}")
#     print(f"Load Date        : {LOAD_DATE}")
#     print(f"Rows Loaded      : {source_count}")
#     print(f"Target Rows      : {target_count}")
#     print(f"Started At       : {START_TIME}")
#     print(f"Completed At     : {END_TIME}")

# except Exception as e:

#     error_message = str(e)

#     print("=" * 100)
#     print("BRONZE LOAD FAILED")
#     print("=" * 100)

#     print(error_message)
#     print(traceback.format_exc())

#     raise Exception(
#         f"""
#         BRONZE LOAD FAILED

#         Source Entity : {SOURCE_ENTITY}
#         Load Date     : {LOAD_DATE}

#         Error:
#         {error_message}
#         """
#     )

# finally:

#     print("=" * 100)
#     print("PROCESS FINISHED")
#     print("=" * 100)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# =====================================================================================
# NOTEBOOK : nb_bronze_dynamic_loader
#
# PURPOSE
# -------
# Load all RAW parquet files into bronze schema tables (Fabric Lakehouse)
#
# TARGET
# -------
# bronze.activity_detail
# bronze.mine_commodity_code
# bronze.camp_detail
#
# FEATURES
# --------
# 1. Auto-discovery of entities under Files/raw
# 2. Auto-discovery of yyyy/mm/dd folders
# 3. Auto-discovery of parquet files
# 4. Loads only new files (no tracker table)
# 5. Preserves full history
# 6. Handles INT96 parquet compatibility
# 7. Delta tables with schema evolution
# 8. Audit columns (file name + timestamp)
# =====================================================================================

from pyspark.sql.functions import lit, current_timestamp
from datetime import datetime
import traceback
import re

# =====================================================================================
# CONFIG
# =====================================================================================

RAW_ROOT_PATH = "Files/raw"
TARGET_SCHEMA = "bronze"

START_TIME = datetime.now()

# =====================================================================================
# SPARK SETTINGS (IMPORTANT FOR PARQUET COMPATIBILITY)
# =====================================================================================

spark.conf.set("spark.sql.parquet.int96RebaseModeInRead", "LEGACY")
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "LEGACY")
spark.conf.set("spark.sql.parquet.int96RebaseModeInWrite", "LEGACY")
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite", "LEGACY")

spark.conf.set("spark.databricks.delta.schema.autoMerge.enabled", "true")

# =====================================================================================
# HELPERS
# =====================================================================================

def get_table_name(entity: str):

    entity = entity.strip()

    if entity.lower().startswith("public."):
        entity = entity[7:]

    entity = (
        entity
        .replace(".", "_")
        .replace("-", "_")
        .replace(" ", "_")
        .lower()
    )

    return entity


def get_entities():

    items = mssparkutils.fs.ls(RAW_ROOT_PATH)

    return sorted([
        item.name.replace("/", "").strip()
        for item in items
        if item.name
    ])


def get_file_timestamp(file_name: str):

    match = re.search(r"(\d{8}_\d{6})", file_name)

    if not match:
        return None

    return datetime.strptime(match.group(1), "%Y%m%d_%H%M%S")


def get_all_parquet_files(entity: str):

    files_found = []
    base_path = f"{RAW_ROOT_PATH}/{entity}"

    try:

        for year in mssparkutils.fs.ls(base_path):

            y = year.name.replace("/", "").strip()
            if not y.isdigit():
                continue

            for month in mssparkutils.fs.ls(f"{base_path}/{y}"):

                m = month.name.replace("/", "").strip()
                if not m.isdigit():
                    continue

                for day in mssparkutils.fs.ls(f"{base_path}/{y}/{m}"):

                    d = day.name.replace("/", "").strip()
                    if not d.isdigit():
                        continue

                    folder = f"{base_path}/{y}/{m}/{d}"

                    for f in mssparkutils.fs.ls(folder):

                        if f.name.lower().endswith(".parquet"):
                            files_found.append((f.name, f.path))

    except Exception as e:
        print(f"Error reading {entity}: {e}")

    return files_found


def table_exists(table_name: str):
    return spark.catalog.tableExists(table_name)


def file_already_loaded(table_name: str, file_name: str):

    if not table_exists(table_name):
        return False

    try:
        return spark.sql(f"""
            SELECT COUNT(*)
            FROM {table_name}
            WHERE bronze_file_name = '{file_name}'
        """).collect()[0][0] > 0
    except:
        return False


# =====================================================================================
# LOAD FUNCTION
# =====================================================================================

def load_file(entity, file_name, file_path):

    table_name = f"{TARGET_SCHEMA}.{get_table_name(entity)}"

    print("\n" + "=" * 100)
    print(f"ENTITY : {entity}")
    print(f"TABLE  : {table_name}")
    print(f"FILE   : {file_name}")
    print("=" * 100)

    if file_already_loaded(table_name, file_name):
        print("SKIPPED (already loaded)")
        return "SKIPPED"

    file_ts = get_file_timestamp(file_name)

    if file_ts is None:
        print("SKIPPED (no timestamp in filename)")
        return "SKIPPED"

    df = (
        spark.read
        .option("int96RebaseMode", "LEGACY")
        .option("datetimeRebaseMode", "LEGACY")
        .parquet(file_path)
    )

    row_count = df.count()

    if row_count == 0:
        print("SKIPPED (empty file)")
        return "SKIPPED"

    print(f"Rows: {row_count}")

    df = (
        df
        .withColumn("bronze_file_name", lit(file_name))
        .withColumn("bronze_file_timestamp", lit(file_ts))
        .withColumn("bronze_load_date", lit(file_ts.date()))
        .withColumn("bronze_load_ts", current_timestamp())
    )

    if not table_exists(table_name):

        print(f"Creating table {table_name}")

        df.write.format("delta") \
            .partitionBy("bronze_load_date") \
            .mode("overwrite") \
            .option("overwriteSchema", "true") \
            .saveAsTable(table_name)

    else:

        print(f"Appending to {table_name}")

        df.write.format("delta") \
            .mode("append") \
            .option("mergeSchema", "true") \
            .saveAsTable(table_name)

    target_count = spark.sql(f"""
        SELECT COUNT(*)
        FROM {table_name}
        WHERE bronze_file_name = '{file_name}'
    """).collect()[0][0]

    if target_count != row_count:
        raise Exception(f"Row mismatch {file_name}")

    print("VALIDATION PASSED")

    return "LOADED"


# =====================================================================================
# MAIN EXECUTION
# =====================================================================================

loaded = 0
skipped = 0
failed = 0
failures = []

try:

    print("=" * 100)
    print("BRONZE LOAD STARTED")
    print("=" * 100)

    entities = get_entities()

    print(f"Entities found: {len(entities)}")

    for e in entities:
        print(" -", e)

    for entity in entities:

        print("\n" + "#" * 100)
        print(f"PROCESSING: {entity}")
        print("#" * 100)

        files = get_all_parquet_files(entity)

        files = sorted(
            files,
            key=lambda x: get_file_timestamp(x[0]) or datetime.min
        )

        for file_name, file_path in files:

            try:
                status = load_file(entity, file_name, file_path)

                if status == "LOADED":
                    loaded += 1
                else:
                    skipped += 1

            except Exception as e:
                failed += 1
                failures.append((entity, file_name, str(e)))

                print(f"FAILED: {file_name}")
                print(str(e))

    print("\n" + "=" * 100)
    print("COMPLETED")
    print("=" * 100)

    print("Loaded :", loaded)
    print("Skipped:", skipped)
    print("Failed :", failed)

    if failures:

        print("\nFAILURES:")
        for f in failures:
            print(f)

except Exception as e:

    print("NOTEBOOK FAILED")
    print(str(e))
    print(traceback.format_exc())

    raise

finally:

    print("\nPROCESS FINISHED")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

from notebookutils import mssparkutils

path = "Files/raw"

items = mssparkutils.fs.ls(path)

folders = [i.name.strip("/") for i in items if i.isDir]

print(f"Folder count: {len(folders)}")

for folder in sorted(folders):
    print(folder)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

tables = spark.catalog.listTables("bronze")

print(f"Table count: {len(tables)}")

for table in sorted(t.name for t in tables):
    print(table)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
