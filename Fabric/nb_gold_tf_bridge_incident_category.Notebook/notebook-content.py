# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "5e43f78b-2156-4469-980e-bffda0295fac",
# META       "default_lakehouse_name": "lh_gold",
# META       "default_lakehouse_workspace_id": "8f380f88-5ce5-48d1-9fa5-fbbfbe2685a0",
# META       "known_lakehouses": [
# META         {
# META           "id": "5e43f78b-2156-4469-980e-bffda0295fac"
# META         }
# META       ]
# META     }
# META   }
# META }

# CELL ********************

# ════════════════════════════════════════════════════════════════════════════
# GOLD TRANSFORM — bridge_incident_category                     (added 2026-09-03)
#   Cell 1  imports + Spark properties              (this cell)
#   Cell 2  derive TARGET_TABLE from notebook name + register sources
#   Cell 3  drop the existing stg table
#   Cell 4  SparkSQL business logic -> DataFrame
#   Cell 5  write the DataFrame to TARGET_TABLE
#
# Grain: one row per (mine_incident_id, mine_incident_category_code).
# Fact type: reload_fact — the xref is a small complete snapshot; rebuilt each run.
# Level 1 in Gold DAG — depends on: dim_incident_category (for the surrogate key).
#
# WHY A BRIDGE
#   An incident can carry several categories (public.mine_incident_category_xref is
#   many-to-many), so the category cannot sit on fact_mine_incident without
#   double-counting. This bridge resolves it: fact -> bridge -> dim.
#   In the semantic model: fact_mine_incident[mine_incident_id] 1:* bridge, and
#   dim_incident_category[Incident_Category_SK] 1:* bridge (bi-directional or a
#   DISTINCTCOUNT measure over the fact through the bridge).
#
# UNCATEGORISED
#   Incidents with no xref row get ONE bridge row pointing at the 'UNC' member so
#   a by-type visual sums back to the total. Flagged is_uncategorised = 1 so it can
#   be excluded with a single filter if Caroline / Romil prefer it hidden.
#
# Filter mirrors the fact: deleted_ind = 0 on the incident.
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

# Silver is cross-lakehouse (gold is the default lakehouse) -> read via abfss.
WORKSPACE_ID = "8f380f88-5ce5-48d1-9fa5-fbbfbe2685a0"
SILVER_LH_ID = "a0190e0e-c2f5-4740-ab90-a2f29b6e6991"
base = f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com/{SILVER_LH_ID}/Tables/silver"

spark.read.format("delta").load(f"{base}/mine_incident/").createOrReplaceTempView("src_mine_incident")
spark.read.format("delta").load(f"{base}/mine_incident_category_xref/").createOrReplaceTempView("src_xref")

# Gold dimension lookup — Gold is the default lakehouse, readable as spark.table().
spark.table("gold.dim_incident_category").createOrReplaceTempView("gold_dim_incident_category")

print("notebook:", NOTEBOOK_NAME, "-> target:", TARGET_TABLE)
print("xref source rows:", spark.table("src_xref").count(),
      "| incident source rows:", spark.table("src_mine_incident").count())

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

# BUSINESS LOGIC — build bridge_incident_category.
#
# Source columns (verified 2026-09-01):
#   public.mine_incident_category_xref : mine_incident_id | mine_incident_category_code
#   public.mine_incident               : mine_incident_id | deleted_ind | ...
#
# Two branches, unioned:
#   1) real xref rows for non-deleted incidents (deduplicated on the pair)
#   2) one 'UNC' row per non-deleted incident that has NO xref row at all

df = spark.sql("""
    WITH live_incidents AS (
        SELECT DISTINCT mine_incident_id
        FROM src_mine_incident
        WHERE deleted_ind = 0
    ),
    pairs AS (
        SELECT DISTINCT
            x.mine_incident_id,
            x.mine_incident_category_code
        FROM src_xref x
        JOIN live_incidents li ON li.mine_incident_id = x.mine_incident_id
        WHERE x.mine_incident_category_code IS NOT NULL
    ),
    uncategorised AS (
        SELECT li.mine_incident_id, 'UNC' AS mine_incident_category_code
        FROM live_incidents li
        LEFT ANTI JOIN pairs p ON p.mine_incident_id = li.mine_incident_id
    ),
    all_pairs AS (
        SELECT mine_incident_id, mine_incident_category_code, 0 AS is_uncategorised FROM pairs
        UNION ALL
        SELECT mine_incident_id, mine_incident_category_code, 1 AS is_uncategorised FROM uncategorised
    )
    SELECT
        ap.mine_incident_id,
        ap.mine_incident_category_code,
        d.Incident_Category_SK,
        d.category_group,
        ap.is_uncategorised
    FROM all_pairs ap
    LEFT JOIN gold_dim_incident_category d
        ON d.mine_incident_category_code = ap.mine_incident_category_code
        AND d.dl_iscurrent = true
""")

n_total  = df.count()
n_nosk   = df.filter(F.col("Incident_Category_SK").isNull()).count()
n_uncat  = df.filter(F.col("is_uncategorised") == 1).count()
print(f"built dataframe: {n_total} rows | uncategorised rows: {n_uncat} | rows with NO dim match: {n_nosk}")
assert n_nosk == 0, "xref references a category code that is not in dim_incident_category — rebuild the dim first"
df.groupBy("category_group").agg(F.countDistinct("mine_incident_id").alias("incidents")) \
  .orderBy(F.desc("incidents")).show(20, truncate=False)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Write the DataFrame to the stg table — full overwrite each run.
# The orchestrator then RELOADS gold.bridge_incident_category from it (reload_fact).
(df.write.format("delta").mode("overwrite")
   .option("overwriteSchema", "true").saveAsTable(TARGET_TABLE))
print("wrote", df.count(), "rows to", TARGET_TABLE)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
