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
#   Cell 1  imports + Spark properties              (this cell)
#   Cell 2  derive TARGET_TABLE from notebook name + register sources
#   Cell 3  drop the existing stg table             (schema may change each build)
#   Cell 4  SparkSQL business logic -> DataFrame
#   Cell 5  write the DataFrame to TARGET_TABLE      (full overwrite each run)
# This fact resolves Permit_SK from the already-built gold.dim_permit (the DAG makes it
# depend on dim_permit), then materializes stg.fact_permit_amendment for the merge.
# ════════════════════════════════════════════════════════════════════════════
from pyspark.sql import functions as F  # noqa: F401 — available to business-logic cells
from notebookutils import mssparkutils

# Gold sources can contain pre-1900 timestamps (e.g. permit_amendment) — rebase on read/write.
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite", "LEGACY")
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "LEGACY")
spark.conf.set("spark.sql.parquet.int96RebaseModeInWrite", "LEGACY")
spark.conf.set("spark.sql.parquet.int96RebaseModeInRead", "LEGACY")

# Control/lineage columns dropped from the gold-bound projection.
CTRL = {"dl_load_id", "bronze_file_name", "bronze_file_timestamp", "bronze_load_date",
        "dl_load_ts", "dl_rowhash", "silver_load_ts"}

# METADATA ********************

# META { "language": "python", "language_group": "synapse_pyspark" }

# CELL ********************

# NAMING CONVENTION (IMPORTANT): 'nb_gold_tf_<object>' materializes 'stg.<object>'. Target
# is derived from THIS notebook's name so a copied template auto-targets the right table.
NB_PREFIX  = "nb_gold_tf_"
STG_SCHEMA = "stg"
NOTEBOOK_NAME = mssparkutils.runtime.context.get("currentNotebookName")
assert NOTEBOOK_NAME, "could not resolve current notebook name from runtime context"
assert NOTEBOOK_NAME.startswith(NB_PREFIX), f"notebook '{NOTEBOOK_NAME}' must be named '{NB_PREFIX}<object>'"
OBJECT_NAME  = NOTEBOOK_NAME[len(NB_PREFIX):]
TARGET_TABLE = f"{STG_SCHEMA}.{OBJECT_NAME}"
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {STG_SCHEMA}")

# Source: silver.permit_amendment via abfss (cross-lakehouse) → temp view for pure SparkSQL.
# gold.dim_permit is in THIS (default) lakehouse, referenced directly in the business cell.
WORKSPACE_ID = "8f380f88-5ce5-48d1-9fa5-fbbfbe2685a0"
SILVER_LH_ID = "a0190e0e-c2f5-4740-ab90-a2f29b6e6991"
pa = f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com/{SILVER_LH_ID}/Tables/silver/permit_amendment/"
spark.read.format("delta").load(pa).createOrReplaceTempView("src_permit_amendment")

# Project source columns with the pa alias (the business cell adds the dimension key).
SELECT_COLS = ", ".join(f"pa.`{c}`" for c in spark.table("src_permit_amendment").columns if c not in CTRL)
print("notebook:", NOTEBOOK_NAME, "-> target:", TARGET_TABLE)

# METADATA ********************

# META { "language": "python", "language_group": "synapse_pyspark" }

# CELL ********************

# Drop the existing stg table so each build starts clean (schema may change build-to-build).
spark.sql(f"DROP TABLE IF EXISTS {TARGET_TABLE}")
print("dropped (if existed):", TARGET_TABLE)

# METADATA ********************

# META { "language": "python", "language_group": "synapse_pyspark" }

# CELL ********************

# BUSINESS LOGIC (SparkSQL) -> DataFrame. Resolve Permit_SK from the current rows of the
# already-built gold dimension (LEFT JOIN so amendments with no matching permit still load).
df = spark.sql(f"""
    SELECT {SELECT_COLS}, d.Permit_SK
    FROM src_permit_amendment pa
    LEFT JOIN gold.dim_permit d
      ON pa.permit_id = d.permit_id AND d.dl_iscurrent = true
""")
print("built dataframe:", df.count(), "rows,", len(df.columns), "cols")

# METADATA ********************

# META { "language": "python", "language_group": "synapse_pyspark" }

# CELL ********************

# Write the DataFrame to the stg table — full overwrite each run.
(df.write.format("delta").mode("overwrite")
   .option("overwriteSchema", "true").saveAsTable(TARGET_TABLE))
print("wrote", df.count(), "rows to", TARGET_TABLE)

# METADATA ********************

# META { "language": "python", "language_group": "synapse_pyspark" }
