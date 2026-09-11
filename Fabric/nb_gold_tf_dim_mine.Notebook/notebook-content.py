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

# ════════════════════════════════════════════════════════════════════════════
# STANDARD GOLD TRANSFORM TEMPLATE  (see nb_gold_tf_dim_permit for the canonical example)
#   Cell 1  imports + Spark properties              (this cell)
#   Cell 2  derive TARGET_TABLE from notebook name + register sources
#   Cell 3  drop the existing stg table             (schema may change each build)
#   Cell 4  SparkSQL business logic -> DataFrame
#   Cell 5  write the DataFrame to TARGET_TABLE      (full overwrite each run)
# dim_mine is a JOIN-BASED type-2 dimension. It enriches each mine record with:
#   - mine_region_code description (decode via silver.mine_region_code)
#   - current operational status (silver.mine_status -> mine_status_xref -> mine_operation_status_code)
# Business keys: mine_guid (uuid PK), mine_no (legacy text key — NRIS uses this).
# SCD2 history tracking (region reassignment, status changes) is handled by the Gold orchestrator.
# Sits at LEVEL 0 (DAG ROOT) — no Gold parents; built in parallel with dim_permit / dim_party.
# ════════════════════════════════════════════════════════════════════════════
from pyspark.sql import functions as F  # noqa: F401 — available to business-logic cells
from notebookutils import mssparkutils

spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite", "LEGACY")
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "LEGACY")
spark.conf.set("spark.sql.parquet.int96RebaseModeInWrite", "LEGACY")
spark.conf.set("spark.sql.parquet.int96RebaseModeInRead", "LEGACY")

# Control/lineage columns dropped from the gold-bound projection.
CTRL = {"dl_load_id", "bronze_file_name", "bronze_file_timestamp", "bronze_load_date",
        "dl_load_ts", "dl_rowhash", "silver_load_ts"}


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# NAMING CONVENTION: notebook named nb_gold_tf_<object> materializes stg.<object>.
NB_PREFIX  = "nb_gold_tf_"
STG_SCHEMA = "stg"
NOTEBOOK_NAME = mssparkutils.runtime.context.get("currentNotebookName")
assert NOTEBOOK_NAME, "could not resolve current notebook name from runtime context"
assert NOTEBOOK_NAME.startswith(NB_PREFIX), f"notebook must be named '{NB_PREFIX}<object>'"
OBJECT_NAME  = NOTEBOOK_NAME[len(NB_PREFIX):]
TARGET_TABLE = f"{STG_SCHEMA}.{OBJECT_NAME}"
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {STG_SCHEMA}")

# Silver is in the same lakehouse (schema silver) -> read by table name, no IDs needed.

# Core mine table (19,257 rows after geom fix — geom lands as WKT text).
spark.table("silver.mine").createOrReplaceTempView("src_mine")
# Region decode: mine.mine_region -> mine_region_code.mine_region_code -> .description
spark.table("silver.mine_region_code").createOrReplaceTempView("src_mine_region_code")
# Current operational status chain: mine_status -> mine_status_xref -> mine_operation_status_code
spark.table("silver.mine_status").createOrReplaceTempView("src_mine_status")
spark.table("silver.mine_status_xref").createOrReplaceTempView("src_mine_status_xref")
spark.table("silver.mine_operation_status_code").createOrReplaceTempView("src_mine_op_status")

# Build mine column list for projection (drop all CTRL/lineage columns).
mine_cols = [c for c in spark.table("src_mine").columns if c not in CTRL]
MINE_SEL  = ", ".join("m." + c for c in mine_cols)
print("notebook:", NOTEBOOK_NAME, "-> target:", TARGET_TABLE)
print("mine source cols:", len(mine_cols))


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Drop the existing stg table so each build starts clean (schema may change build-to-build).
spark.sql(f"DROP TABLE IF EXISTS {TARGET_TABLE}")
print("dropped (if existed):", TARGET_TABLE)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# BUSINESS LOGIC — project mine attributes + decode region + resolve current operational status.
#
# Region decode: mine.mine_region (e.g. "NE") -> mine_region_code.description (e.g. "North East")
# Current op status: most recent mine_status row per mine_guid
#   -> mine_status_xref -> mine_operation_status_code.description
#   Uses ROW_NUMBER() OVER PARTITION to pick the latest status per mine.
# NRIS note: NRIS inspections join mines via mine_no (text), not mine_guid.
#   Both mine_guid and mine_no are projected so NRIS fact tables can join either way.
df = spark.sql(f"""
    WITH current_status AS (
        SELECT
            ms.mine_guid,
            msx.mine_operation_status_code,
            mosc.description AS mine_operation_status_desc,
            ROW_NUMBER() OVER (
                PARTITION BY ms.mine_guid
                ORDER BY ms.status_date DESC, ms.create_timestamp DESC
            ) AS rn
        FROM src_mine_status ms
        LEFT JOIN src_mine_status_xref msx
            ON ms.mine_status_xref_guid = msx.mine_status_xref_guid
        LEFT JOIN src_mine_op_status mosc
            ON msx.mine_operation_status_code = mosc.mine_operation_status_code
    )
    SELECT
        {MINE_SEL},
        mrc.description            AS mine_region_desc,
        cs.mine_operation_status_code,
        cs.mine_operation_status_desc
    FROM src_mine m
    LEFT JOIN src_mine_region_code mrc
        ON m.mine_region = mrc.mine_region_code
    LEFT JOIN current_status cs
        ON m.mine_guid = cs.mine_guid AND cs.rn = 1
""")
print("built dataframe:", df.count(), "rows,", len(df.columns), "cols")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Write the DataFrame to the stg table — full overwrite each run.
(df.write.format("delta").mode("overwrite")
   .option("overwriteSchema", "true").saveAsTable(TARGET_TABLE))
print("wrote", df.count(), "rows to", TARGET_TABLE)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
