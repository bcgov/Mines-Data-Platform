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


from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from delta.tables import DeltaTable
from datetime import datetime
import traceback

spark = SparkSession.builder.getOrCreate()

spark.conf.set("spark.sql.shuffle.partitions", "32")
spark.conf.set("spark.databricks.delta.schema.autoMerge.enabled", "true")

# Fix ancient date/timestamp issue
spark.conf.set(
    "spark.sql.parquet.datetimeRebaseModeInWrite",
    "LEGACY"
)

spark.conf.set(
    "spark.sql.parquet.int96RebaseModeInWrite",
    "LEGACY"
)

print("BLOCK 1 COMPLETED - SPARK READY")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

CONTROL_TABLE = "app.pipeline_control"

BRONZE_DB = "bronze"
SILVER_DB = "silver"

DEFAULT_WATERMARK = "1900-01-01T00:00:00.000Z"

run_summary = []

start_time = datetime.now()

print("BLOCK 2 COMPLETED - CONFIG READY")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

def table_exists(table_name):
    return spark.catalog.tableExists(table_name)


def resolve_bronze(source_entity):

    source_table = source_entity.split(".")[-1]

    return f"{BRONZE_DB}.{source_table.lower()}"


def get_pk_cols(primary_key):

    if primary_key is None:
        return []

    return [
        c.strip()
        for c in str(primary_key).split(",")
        if c.strip()
    ]


def deduplicate(df, pk_cols):

    if not pk_cols:
        return df

    return df.dropDuplicates(pk_cols)


def is_empty(df):

    return len(df.take(1)) == 0


print("BLOCK 3 COMPLETED - HELPERS READY")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

def process_table(row):

    source_entity = row["source_entity"]

    target_table = row["target_table"].strip().lower()

    silver_table = f"{SILVER_DB}.{target_table}"

    load_type = (
        str(row["load_type"]).upper()
        if row["load_type"]
        else "FULL"
    )

    watermark_column = row["watermark_column"]

    last_watermark = row["last_watermark"]

    primary_key = row["primary_key"]

    try:

        print("\n" + "=" * 90)
        print(f"SOURCE : {source_entity}")
        print(f"TARGET : {silver_table}")
        print(f"LOAD   : {load_type}")
        print("=" * 90)

        # --------------------------------------------------
        # PRIMARY KEY CHECK
        # --------------------------------------------------

        pk_cols = get_pk_cols(primary_key)

        if len(pk_cols) == 0:

            print("SKIPPED - PRIMARY KEY NOT DEFINED")

            run_summary.append({
                "table": source_entity,
                "status": "SKIPPED",
                "reason": "Primary key missing"
            })

            return

        # --------------------------------------------------
        # BRONZE TABLE CHECK
        # --------------------------------------------------

        bronze_table = resolve_bronze(source_entity)

        if not table_exists(bronze_table):

            print(f"SKIPPED - BRONZE TABLE NOT FOUND: {bronze_table}")

            run_summary.append({
                "table": source_entity,
                "status": "SKIPPED",
                "reason": "Bronze table missing"
            })

            return

        # --------------------------------------------------
        # READ BRONZE
        # --------------------------------------------------

        df = spark.table(bronze_table)

        # --------------------------------------------------
        # FULL LOAD
        # --------------------------------------------------

        if load_type == "FULL" or not last_watermark:

            print("MODE: FULL LOAD")

            if table_exists(silver_table):

                spark.sql(
                    f"DROP TABLE IF EXISTS {silver_table}"
                )

            (
                df.write
                .format("delta")
                .mode("overwrite")
                .option("overwriteSchema", "true")
                .saveAsTable(silver_table)
            )

            run_summary.append({
                "table": source_entity,
                "status": "SUCCESS"
            })

            print("FULL LOAD COMPLETED")

            return

        # --------------------------------------------------
        # INCREMENTAL LOAD
        # --------------------------------------------------

        print(
            f"MODE: INCREMENTAL FROM {last_watermark}"
        )

        watermark_ts = F.to_timestamp(
            F.lit(last_watermark)
        )

        inc_df = df.filter(
            F.to_timestamp(
                F.col(watermark_column)
            ) > watermark_ts
        )

        if is_empty(inc_df):

            print("NO NEW DATA FOUND")

            run_summary.append({
                "table": source_entity,
                "status": "SUCCESS"
            })

            return

        # Remove duplicate PK records
        inc_df = deduplicate(
            inc_df,
            pk_cols
        )

        merge_condition = " AND ".join(
            [f"t.{c}=s.{c}" for c in pk_cols]
        )

        # --------------------------------------------------
        # CREATE SILVER TABLE
        # --------------------------------------------------

        if not table_exists(silver_table):

            print(
                "SILVER TABLE DOES NOT EXIST - CREATING"
            )

            (
                inc_df.write
                .format("delta")
                .mode("overwrite")
                .option("overwriteSchema", "true")
                .saveAsTable(silver_table)
            )

        else:

            print("MERGING INTO SILVER")

            (
                DeltaTable.forName(
                    spark,
                    silver_table
                )
                .alias("t")
                .merge(
                    inc_df.alias("s"),
                    merge_condition
                )
                .whenMatchedUpdateAll()
                .whenNotMatchedInsertAll()
                .execute()
            )

        run_summary.append({
            "table": source_entity,
            "status": "SUCCESS"
        })

        print("PROCESS COMPLETED")

    except Exception as e:

        print(
            f"FAILED TABLE: {source_entity}"
        )

        traceback.print_exc()

        run_summary.append({
            "table": source_entity,
            "status": "FAILED",
            "error": str(e)
        })
print("BLOCK 4 COMPLETED - PROCESS TABLE")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

print("=" * 90)
print("DYNAMIC SILVER ETL STARTED")
print("=" * 90)

control_df = (
    spark.table(CONTROL_TABLE)
    .filter(F.col("is_active") == 1)
    .select(
        "source_entity",
        "target_table",
        "primary_key",
        "watermark_column",
        "last_watermark",
        "load_type"
    )
)

rows = control_df.collect()

print(
    f"TABLES FROM CONTROL TABLE: {len(rows)}"
)

for row in rows:

    process_table(row)

# ==================================================
# SUMMARY
# ==================================================

print("\n" + "=" * 90)
print("ETL SUMMARY")
print("=" * 90)

success_count = len(
    [x for x in run_summary
     if x["status"] == "SUCCESS"]
)

failed_count = len(
    [x for x in run_summary
     if x["status"] == "FAILED"]
)

skipped_count = len(
    [x for x in run_summary
     if x["status"] == "SKIPPED"]
)

print(f"SUCCESS : {success_count}")
print(f"FAILED  : {failed_count}")
print(f"SKIPPED : {skipped_count}")

print("\nFAILED TABLES")
print("-" * 90)

for item in run_summary:

    if item["status"] == "FAILED":

        print(
            f"{item['table']} --> "
            f"{item['error']}"
        )

print("\nSKIPPED TABLES")
print("-" * 90)

for item in run_summary:

    if item["status"] == "SKIPPED":

        print(
            f"{item['table']} --> "
            f"{item['reason']}"
        )

print("\n" + "=" * 90)

print(f"START TIME : {start_time}")
print(f"END TIME   : {datetime.now()}")
print(
    f"DURATION   : "
    f"{datetime.now() - start_time}"
)

print("=" * 90)

print("DYNAMIC SILVER ETL COMPLETED")
print("BLOCK 5 COMPLETED - MAIN EXECUTION")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
