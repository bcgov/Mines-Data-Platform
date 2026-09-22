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
# GOLD TRANSFORM — dim_incident_category                        (added 2026-09-03)
#   Cell 1  imports + Spark properties              (this cell)
#   Cell 2  derive TARGET_TABLE from notebook name + register sources
#   Cell 3  drop the existing stg table
#   Cell 4  SparkSQL business logic -> DataFrame
#   Cell 5  write the DataFrame to TARGET_TABLE
#
# Grain: one row per incident category CODE (mine_incident_category_code).
# Dim type: type1_dimension, load_strategy full (source is a complete snapshot).
# Level 0 in Gold DAG — no upstream Gold dependency.
#
# WHY THIS EXISTS
#   The corporate incidents report will break incidents down "by type". The source
#   table public.mine_incident_category is a TWO-LEVEL HIERARCHY (56 codes, 38 of
#   which carry parent_mine_incident_category_code). Rolled up to the parent, the
#   incidents fall into nine groups (Mobile Equipment, Health and Safety, Other,
#   Geotechnical, Working at Height, Blasting, Electrical, Fire, Ventilation).
#   That parent rollup is carried here as `category_group` so the grouping is a
#   plain column, not a CASE statement — and easy to override if Caroline's
#   grouping differs (change the CASE in cell 4, nothing else).
#
# An explicit member 'UNC' (Uncategorised) is appended so incidents with no xref
#   row can still be sliced. Only 47% of incidents carry any category at source.
# ════════════════════════════════════════════════════════════════════════════
from pyspark.sql import functions as F  # noqa: F401
from notebookutils import mssparkutils

spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite", "LEGACY")
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "LEGACY")
spark.conf.set("spark.sql.parquet.int96RebaseModeInWrite", "LEGACY")
spark.conf.set("spark.sql.parquet.int96RebaseModeInRead", "LEGACY")

CTRL = {"dl_load_id", "bronze_file_name", "bronze_file_timestamp", "bronze_load_date",
        "dl_load_ts", "dl_rowhash", "silver_load_ts"}

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# NAMING CONVENTION: notebook named nb_gold_tf_<object> materializes stg.<object>.
NB_PREFIX     = "nb_gold_tf_"
STG_SCHEMA    = "stg"
NOTEBOOK_NAME = mssparkutils.runtime.context.get("currentNotebookName")
assert NOTEBOOK_NAME, "could not resolve current notebook name from runtime context"
assert NOTEBOOK_NAME.startswith(NB_PREFIX), f"notebook must be named '{NB_PREFIX}<object>'"
OBJECT_NAME   = NOTEBOOK_NAME[len(NB_PREFIX):]
TARGET_TABLE  = f"{STG_SCHEMA}.{OBJECT_NAME}"
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {STG_SCHEMA}")

# Silver is in the same lakehouse (schema silver) -> read by table name, no IDs needed.
# Same lakehouse the incident fact reads from (lh_silver).

spark.table("silver.mine_incident_category").createOrReplaceTempView("src_category")

print("notebook:", NOTEBOOK_NAME, "-> target:", TARGET_TABLE)
print("mine_incident_category source rows:", spark.table("src_category").count())

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

# BUSINESS LOGIC — build dim_incident_category.
#
# Source columns (public.mine_incident_category, verified 2026-09-01):
#   mine_incident_category_code | description | active_ind | display_order
#   is_historic | parent_mine_incident_category_code | create/update audit cols
#
# category_group = the PARENT's description (or the code's own description when it
#   is itself a top-level code). This is the report's "type" rollup.
#
# The orchestrator generates the surrogate key (Incident_Category_SK) and the
#   dl_* SCD columns; business key = mine_incident_category_code.

df = spark.sql("""
    SELECT
        c.mine_incident_category_code,
        c.description                              AS category_description,
        c.parent_mine_incident_category_code       AS parent_category_code,
        p.description                              AS parent_category_description,
        COALESCE(p.description, c.description)     AS category_group,
        CASE WHEN c.parent_mine_incident_category_code IS NULL THEN 1 ELSE 0 END
                                                   AS is_top_level,
        CAST(c.active_ind AS BOOLEAN)              AS active_ind,
        CAST(c.is_historic AS BOOLEAN)             AS is_historic,
        CAST(c.display_order AS INT)               AS display_order,
        CAST(0 AS INT)                             AS is_uncategorised_member
    FROM src_category c
    LEFT JOIN src_category p
        ON p.mine_incident_category_code = c.parent_mine_incident_category_code

    UNION ALL

    -- Explicit member for incidents that carry no category at all.
    SELECT
        'UNC'                    AS mine_incident_category_code,
        'Uncategorised'          AS category_description,
        CAST(NULL AS STRING)     AS parent_category_code,
        CAST(NULL AS STRING)     AS parent_category_description,
        'Uncategorised'          AS category_group,
        1                        AS is_top_level,
        CAST(TRUE AS BOOLEAN)    AS active_ind,
        CAST(FALSE AS BOOLEAN)   AS is_historic,
        CAST(9999 AS INT)        AS display_order,
        CAST(1 AS INT)           AS is_uncategorised_member
""").dropDuplicates(["mine_incident_category_code"])

print("built dataframe:", df.count(), "rows,", len(df.columns), "cols")
df.groupBy("category_group").count().orderBy(F.desc("count")).show(20, truncate=False)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Write the DataFrame to the stg table — full overwrite each run.
# The orchestrator then merges stg.dim_incident_category -> gold.dim_incident_category
# as a type-1 dimension on mine_incident_category_code (full snapshot: absent codes soft-expire).
(df.write.format("delta").mode("overwrite")
   .option("overwriteSchema", "true").saveAsTable(TARGET_TABLE))
print("wrote", df.count(), "rows to", TARGET_TABLE)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
