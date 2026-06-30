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
# META     }
# META   }
# META }

# CELL ********************

# ════════════════════════════════════════════════════════════════════════════
# STANDARD GOLD TRANSFORM TEMPLATE  (see nb_gold_tf_dim_permit for the canonical example)
# fact_amendment_activity is a LEVEL-2 append fact. It reads ONLY gold dimensions (default
# lakehouse) — so it has TWO parents and proves multi-parent, multi-level DAG ordering:
#   * gold.dim_amendment_enriched  (LEVEL 1) -> Amendment_SK + grain (permit_amendment_id)
#   * gold.dim_municipality        (LEVEL 0) -> Municipality_SK
# NOTE: measures + the municipality assignment are SYNTHETIC (round-robin / deterministic hash).
# The purpose is to exercise the orchestrator's level/fan-in handling, not business value.
# ════════════════════════════════════════════════════════════════════════════
from pyspark.sql import functions as F  # noqa: F401 — available to business-logic cells
from notebookutils import mssparkutils

spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite", "LEGACY")
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "LEGACY")
spark.conf.set("spark.sql.parquet.int96RebaseModeInWrite", "LEGACY")
spark.conf.set("spark.sql.parquet.int96RebaseModeInRead", "LEGACY")

# METADATA ********************

# META { "language": "python", "language_group": "synapse_pyspark" }

# CELL ********************

NB_PREFIX  = "nb_gold_tf_"
STG_SCHEMA = "stg"
NOTEBOOK_NAME = mssparkutils.runtime.context.get("currentNotebookName")
assert NOTEBOOK_NAME, "could not resolve current notebook name from runtime context"
assert NOTEBOOK_NAME.startswith(NB_PREFIX), f"notebook '{NOTEBOOK_NAME}' must be named '{NB_PREFIX}<object>'"
OBJECT_NAME  = NOTEBOOK_NAME[len(NB_PREFIX):]
TARGET_TABLE = f"{STG_SCHEMA}.{OBJECT_NAME}"
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {STG_SCHEMA}")
# Both sources are gold dims in the default lakehouse — no abfss / temp views needed.
print("notebook:", NOTEBOOK_NAME, "-> target:", TARGET_TABLE)

# METADATA ********************

# META { "language": "python", "language_group": "synapse_pyspark" }

# CELL ********************

spark.sql(f"DROP TABLE IF EXISTS {TARGET_TABLE}")
print("dropped (if existed):", TARGET_TABLE)

# METADATA ********************

# META { "language": "python", "language_group": "synapse_pyspark" }

# CELL ********************

# BUSINESS LOGIC — one activity row per current amendment (grain = permit_amendment_id).
# Amendment_SK is a real FK to dim_amendment_enriched; Municipality_SK is assigned round-robin
# (SYNTHETIC) to exercise the second parent edge; measures are deterministic fakes.
df = spark.sql("""
    WITH muni AS (
        SELECT Municipality_SK,
               row_number() OVER (ORDER BY municipality_guid) - 1 AS muni_idx,
               count(*)     OVER ()                              AS muni_n
        FROM gold.dim_municipality
        WHERE dl_iscurrent = true
    ),
    amd AS (
        SELECT Amendment_SK,
               permit_amendment_id,
               row_number() OVER (ORDER BY permit_amendment_id) - 1 AS amd_idx
        FROM gold.dim_amendment_enriched
        WHERE dl_iscurrent = true
    )
    SELECT a.Amendment_SK,
           a.permit_amendment_id,
           m.Municipality_SK,
           pmod(hash(a.permit_amendment_id), 365) AS processing_days,   -- SYNTHETIC measure
           1                                      AS amendment_count
    FROM amd a
    LEFT JOIN muni m
      ON pmod(a.amd_idx, m.muni_n) = m.muni_idx
""")
print("built dataframe:", df.count(), "rows,", len(df.columns), "cols")

# METADATA ********************

# META { "language": "python", "language_group": "synapse_pyspark" }

# CELL ********************

(df.write.format("delta").mode("overwrite")
   .option("overwriteSchema", "true").saveAsTable(TARGET_TABLE))
print("wrote", df.count(), "rows to", TARGET_TABLE)

# METADATA ********************

# META { "language": "python", "language_group": "synapse_pyspark" }
