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
# META     }
# META   }
# META }

# CELL ********************

# # ==========================================
# # IMPORTS
# # ==========================================

# from pyspark.sql.functions import *
# from pyspark.sql.types import *
# from pyspark.sql.window import Window
# from datetime import datetime
# import traceback
# import uuid

# from com.microsoft.spark.fabric import Constants


# # ==========================================
# # CONFIG
# # ==========================================

# # Replace this with your Fabric Warehouse name
# warehouse_name = "mines-data-platform-fabwh1"

# # Optional:
# # If the Warehouse is in a different workspace, uncomment and set workspace_id.
# # workspace_id = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

# # Schema/table names used by the framework
# control_schema = "app"
# control_table = "pipeline_control"

# log_schema = "app"
# pipeline_log_table = "pipeline_log"
# error_log_table = "error_log"

# source_schema = "bronze"

# # Staging schema used for incremental loads
# # Make sure this schema exists in the Warehouse.
# staging_schema = "stg"


# # ==========================================
# # HELPER FUNCTIONS
# # ==========================================

# def wh_table(schema_name, table_name):
#     """
#     Returns Fabric Warehouse 3-part table name:
#     Warehouse.Schema.Table
#     """
#     return f"{warehouse_name}.{schema_name}.{table_name}"


# def read_wh_table(schema_name, table_name):
#     """
#     Reads a Fabric Warehouse table into a Spark DataFrame.
#     """
#     reader = spark.read

#     # Use this only when reading from a different workspace.
#     # reader = reader.option(Constants.WorkspaceId, workspace_id)

#     return reader.synapsesql(wh_table(schema_name, table_name))


# def write_wh_table(df, schema_name, table_name, mode="append"):
#     """
#     Writes a Spark DataFrame into a Fabric Warehouse table.
#     mode can be append, overwrite, etc.
#     """
#     writer = df.write.mode(mode)

#     # Use this only when writing to a different workspace.
#     # writer = writer.option(Constants.WorkspaceId, workspace_id)

#     writer.synapsesql(wh_table(schema_name, table_name))


# def clean_sql_value(value):
#     """
#     Handles single quotes for SQL string values.
#     """
#     if value is None:
#         return None

#     return str(value).replace("'", "''")


# def get_non_audit_columns(df):
#     """
#     Returns dataframe columns excluding generated row number if present.
#     """
#     return [c for c in df.columns if c.lower() != "rn"]


# # ==========================================
# # READ PIPELINE METADATA FROM WAREHOUSE
# # ==========================================

# metadata_df = (
#     read_wh_table(control_schema, control_table)
#     .filter(col("is_active") == lit(1))
# )

# metadata_list = metadata_df.collect()


# # ==========================================
# # LOOP THROUGH ALL TABLES
# # ==========================================

# for row in metadata_list:

#     # ==========================================
#     # METADATA
#     # ==========================================

#     pipeline_name = row["pipeline_name"]
#     source_entity = row["source_entity"]
#     target_schema = row["target_schema"]
#     target_table = row["target_table"]
#     watermark_column = row["watermark_column"]
#     last_watermark = row["last_watermark"]
#     load_type = row["load_type"]
#     primary_key = row["primary_key"]

#     run_id = str(uuid.uuid4())
#     start_time = datetime.now()

#     target_table_name = wh_table(target_schema, target_table)
#     source_table_name = wh_table(source_schema, target_table)
#     staging_table = f"{target_table}_stg"
#     staging_table_name = wh_table(staging_schema, staging_table)

#     print(f"Starting table: {target_table}")

#     try:

#         # ==========================================
#         # READ BRONZE TABLE FROM WAREHOUSE
#         # ==========================================

#         source_df = read_wh_table(source_schema, target_table)

#         rows_read = source_df.count()

#         # ==========================================
#         # INCREMENTAL FILTER
#         # ==========================================

#         if load_type == "INCREMENTAL":

#             if watermark_column is None:
#                 raise Exception(
#                     f"Watermark column is required for incremental load: {target_table}"
#                 )

#             if last_watermark is not None:
#                 source_df = source_df.filter(
#                     col(watermark_column) > lit(last_watermark)
#                 )

#         # ==========================================
#         # STANDARDIZE COLUMN NAMES
#         # ==========================================

#         source_df = source_df.toDF(
#             *[c.lower() for c in source_df.columns]
#         )

#         # Normalize metadata columns too, because dataframe columns are now lowercase
#         if watermark_column is not None:
#             watermark_column = watermark_column.lower()

#         if primary_key is not None:
#             primary_key = primary_key.lower()

#         # ==========================================
#         # TRIM STRING COLUMNS
#         # ==========================================

#         for field in source_df.schema.fields:

#             if isinstance(field.dataType, StringType):

#                 source_df = source_df.withColumn(
#                     field.name,
#                     trim(col(field.name))
#                 )

#         # ==========================================
#         # HANDLE NULL VALUES FOR STRING COLUMNS
#         # ==========================================

#         for field in source_df.schema.fields:

#             if isinstance(field.dataType, StringType):

#                 source_df = source_df.fillna(
#                     {field.name: ""}
#                 )

#         # ==========================================
#         # REMOVE DUPLICATES
#         # ==========================================

#         if primary_key is not None:

#             if watermark_column is not None:

#                 window_spec = (
#                     Window
#                     .partitionBy(primary_key)
#                     .orderBy(col(watermark_column).desc())
#                 )

#                 source_df = (
#                     source_df
#                     .withColumn("rn", row_number().over(window_spec))
#                     .filter(col("rn") == 1)
#                     .drop("rn")
#                 )

#             else:

#                 source_df = source_df.dropDuplicates([primary_key])

#         # ==========================================
#         # ADD AUDIT COLUMNS
#         # ==========================================

#         source_df = (
#             source_df
#             .withColumn("silver_load_timestamp", current_timestamp())
#             .withColumn("silver_load_date", current_date())
#         )

#         rows_written = source_df.count()

#         # ==========================================
#         # FULL LOAD
#         # ==========================================

#         if load_type == "FULL":

#             print("Executing FULL load")

#             write_wh_table(
#                 source_df,
#                 target_schema,
#                 target_table,
#                 mode="overwrite"
#             )

#         # ==========================================
#         # INCREMENTAL LOAD
#         # ==========================================

#         elif load_type == "INCREMENTAL":

#             print("Executing INCREMENTAL load")

#             if primary_key is None:
#                 raise Exception(
#                     f"Primary key is required for incremental load: {target_table}"
#                 )

#             # Write transformed data into Warehouse staging table
#             write_wh_table(
#                 source_df,
#                 staging_schema,
#                 staging_table,
#                 mode="overwrite"
#             )

#             # Build MERGE SQL for Fabric Warehouse
#             columns = get_non_audit_columns(source_df)

#             update_set_clause = ",\n                ".join(
#                 [
#                     f"target.{c} = source.{c}"
#                     for c in columns
#                     if c != primary_key
#                 ]
#             )

#             insert_columns = ", ".join(columns)

#             insert_values = ", ".join(
#                 [f"source.{c}" for c in columns]
#             )

#             merge_sql = f"""
# MERGE INTO {target_schema}.{target_table} AS target
# USING {staging_schema}.{staging_table} AS source
# ON target.{primary_key} = source.{primary_key}
# WHEN MATCHED THEN
#     UPDATE SET
#                 {update_set_clause}
# WHEN NOT MATCHED THEN
#     INSERT ({insert_columns})
#     VALUES ({insert_values});
# """

#             print("Run this MERGE SQL in the Fabric Warehouse SQL editor:")
#             print(merge_sql)

#             # IMPORTANT:
#             # PySpark synapsesql is mainly for reading/writing DataFrames.
#             # For Warehouse DML like MERGE, run the printed SQL in:
#             # 1. Warehouse SQL editor, or
#             # 2. Stored procedure, or
#             # 3. Fabric pipeline Script/Stored Procedure activity.

#         else:

#             raise Exception(f"Unsupported load_type: {load_type}")

#         # ==========================================
#         # UPDATE WATERMARK VALUE
#         # ==========================================

#         if (
#             load_type == "INCREMENTAL"
#             and watermark_column is not None
#             and rows_written > 0
#         ):

#             max_watermark = source_df.agg(
#                 max(watermark_column)
#             ).collect()[0][0]

#             safe_target_table = clean_sql_value(target_table)
#             safe_max_watermark = clean_sql_value(max_watermark)

#             update_watermark_sql = f"""
# UPDATE {control_schema}.{control_table}
# SET
#     last_watermark = '{safe_max_watermark}',
#     last_run_status = 'SUCCESS',
#     last_run_date = CURRENT_TIMESTAMP
# WHERE target_table = '{safe_target_table}';
# """

#             print("Run this watermark update SQL in the Fabric Warehouse SQL editor:")
#             print(update_watermark_sql)

#         else:

#             max_watermark = None

#         end_time = datetime.now()

#         # ==========================================
#         # PIPELINE SUCCESS LOGGING
#         # ==========================================

#         log_df = spark.createDataFrame(
#             [
#                 (
#                     run_id,
#                     pipeline_name,
#                     source_entity,
#                     target_schema,
#                     target_table,
#                     "SUCCESS",
#                     rows_read,
#                     rows_written,
#                     last_watermark,
#                     max_watermark,
#                     None,
#                     start_time,
#                     end_time
#                 )
#             ],
#             [
#                 "run_id",
#                 "pipeline_name",
#                 "source_entity",
#                 "target_schema",
#                 "target_table",
#                 "status",
#                 "rows_read",
#                 "rows_written",
#                 "watermark_start",
#                 "watermark_end",
#                 "error_message",
#                 "start_time",
#                 "end_time"
#             ]
#         )

#         log_df = log_df.withColumn(
#             "created_date",
#             current_timestamp()
#         )

#         write_wh_table(
#             log_df,
#             log_schema,
#             pipeline_log_table,
#             mode="append"
#         )

#         print(f"Completed: {target_table}")

#     except Exception as e:

#         error_message = str(e)
#         stack_trace = traceback.format_exc()
#         end_time = datetime.now()

#         print(f"Failed: {target_table}")
#         print(error_message)

#         # ==========================================
#         # ERROR LOGGING
#         # ==========================================

#         error_df = spark.createDataFrame(
#             [
#                 (
#                     run_id,
#                     pipeline_name,
#                     error_message,
#                     stack_trace
#                 )
#             ],
#             [
#                 "run_id",
#                 "pipeline_name",
#                 "error_message",
#                 "stack_trace"
#             ]
#         )

#         error_df = error_df.withColumn(
#             "created_date",
#             current_timestamp()
#         )

#         write_wh_table(
#             error_df,
#             log_schema,
#             error_log_table,
#             mode="append"
#         )

#         # ==========================================
#         # PIPELINE FAILURE LOG
#         # ==========================================

#         failed_log_df = spark.createDataFrame(
#             [
#                 (
#                     run_id,
#                     pipeline_name,
#                     source_entity,
#                     target_schema,
#                     target_table,
#                     "FAILED",
#                     0,
#                     0,
#                     last_watermark,
#                     None,
#                     error_message,
#                     start_time,
#                     end_time
#                 )
#             ],
#             [
#                 "run_id",
#                 "pipeline_name",
#                 "source_entity",
#                 "target_schema",
#                 "target_table",
#                 "status",
#                 "rows_read",
#                 "rows_written",
#                 "watermark_start",
#                 "watermark_end",
#                 "error_message",
#                 "start_time",
#                 "end_time"
#             ]
#         )

#         failed_log_df = failed_log_df.withColumn(
#             "created_date",
#             current_timestamp()
#         )

#         write_wh_table(
#             failed_log_df,
#             log_schema,
#             pipeline_log_table,
#             mode="append"
#         )

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# =====================================================================================
# NOTEBOOK : silver_dynamic_etl
#
# PURPOSE
# -------
# Dynamically transform ALL Bronze tables into Silver tables
#
# FEATURES
# --------
# 1. Auto-discover Bronze tables
# 2. Column standardization
# 3. Data cleansing
# 4. Duplicate removal
# 5. Audit columns
# 6. Row hash generation
# 7. Safe error handling per table
# 8. No notebook failure on single table error
# =====================================================================================

from pyspark.sql.functions import *
from pyspark.sql.utils import AnalysisException
from datetime import datetime
import traceback

# =====================================================================================
# CONFIG
# =====================================================================================

BRONZE_SCHEMA = "bronze"
SILVER_SCHEMA = "silver"

start_time = datetime.now()

print("=" * 100)
print("DYNAMIC SILVER ETL STARTED")
print(f"Start Time : {start_time}")
print("=" * 100)

# =====================================================================================
# HELPERS
# =====================================================================================

def normalize_name(name):
    return (
        name.strip()
            .replace(" ", "_")
            .replace("-", "_")
            .replace(".", "_")
            .lower()
    )

def get_bronze_tables():
    """Fetch all tables from bronze schema safely"""
    try:
        tables = spark.sql(f"SHOW TABLES IN {BRONZE_SCHEMA}").collect()
        return [t["tableName"] for t in tables]
    except Exception as e:
        print("ERROR: Unable to fetch Bronze tables")
        print(str(e))
        return []

# =====================================================================================
# GET ALL BRONZE TABLES
# =====================================================================================

bronze_tables = get_bronze_tables()

if not bronze_tables:
    print("No Bronze tables found. Exiting safely.")
    mssparkutils.notebook.exit("NO_TABLES")

print(f"Found Bronze Tables: {bronze_tables}")

# =====================================================================================
# PROCESS EACH TABLE
# =====================================================================================

results = []

for table_name in bronze_tables:

    bronze_table = f"{BRONZE_SCHEMA}.{table_name}"
    silver_table = f"{SILVER_SCHEMA}.{table_name}"

    print("\n" + "=" * 80)
    print(f"PROCESSING TABLE : {table_name}")
    print("=" * 80)

    try:

        # =========================================================================
        # READ BRONZE
        # =========================================================================

        df = spark.table(bronze_table)

        row_count = df.count()

        if row_count == 0:
            print(f"Skipping {table_name} (no data)")
            continue

        print(f"Rows Read : {row_count}")

        # =========================================================================
        # STANDARDIZE COLUMN NAMES
        # =========================================================================

        for old_name in df.columns:
            new_name = normalize_name(old_name)

            if old_name != new_name:
                df = df.withColumnRenamed(old_name, new_name)

        # =========================================================================
        # STRING CLEANING
        # =========================================================================

        string_cols = [c for c, d in df.dtypes if d == "string"]

        for c in string_cols:
            df = df.withColumn(c, trim(col(c)))

        # =========================================================================
        # EMPTY STRING → NULL
        # =========================================================================

        df = df.replace("", None)

        # =========================================================================
        # REMOVE DUPLICATES
        # =========================================================================

        before = df.count()
        df = df.dropDuplicates()
        after = df.count()

        print(f"Duplicates Removed : {before - after}")

        # =========================================================================
        # AUDIT COLUMN
        # =========================================================================

        df = df.withColumn("silver_load_ts", current_timestamp())

        # =========================================================================
        # ROW HASH
        # =========================================================================

        hash_cols = [c for c in df.columns if c != "silver_load_ts"]

        df = df.withColumn(
            "row_hash",
            sha2(
                concat_ws(
                    "||",
                    *[coalesce(col(c).cast("string"), lit("")) for c in hash_cols]
                ),
                256
            )
        )

        # =========================================================================
        # WRITE TO SILVER
        # =========================================================================

        df.write \
          .format("delta") \
          .mode("overwrite") \
          .option("overwriteSchema", "true") \
          .saveAsTable(silver_table)

        print(f"SUCCESS : {silver_table}")

        results.append({
            "table": table_name,
            "status": "SUCCESS",
            "rows": row_count
        })

    except Exception as e:

        print(f"FAILED TABLE : {table_name}")
        print(str(e))
        print(traceback.format_exc())

        results.append({
            "table": table_name,
            "status": "FAILED",
            "error": str(e)
        })

# =====================================================================================
# FINAL SUMMARY
# =====================================================================================

end_time = datetime.now()

print("\n" + "=" * 100)
print("DYNAMIC ETL SUMMARY")
print("=" * 100)

for r in results:
    print(r)

print("=" * 100)
print(f"Start Time : {start_time}")
print(f"End Time   : {end_time}")
print(f"Duration   : {end_time - start_time}")
print("=" * 100)

print("DYNAMIC SILVER ETL COMPLETED")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
