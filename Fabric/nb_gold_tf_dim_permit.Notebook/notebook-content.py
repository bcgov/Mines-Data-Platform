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
# STANDARD GOLD TRANSFORM TEMPLATE  (copy this notebook + rename to add a new one)
# A transform materializes one silver→stg table that the gold orchestrator then
# merges into a dim/fact. Cell layout is fixed so every transform looks the same:
#   Cell 1  imports + Spark properties              (this cell)
#   Cell 2  derive TARGET_TABLE from notebook name + register sources
#   Cell 3  drop the existing stg table             (schema may change each build)
#   Cell 4  SparkSQL business logic -> DataFrame
#   Cell 5  write the DataFrame to TARGET_TABLE      (full overwrite each run)
# ════════════════════════════════════════════════════════════════════════════
from pyspark.sql import functions as F  # noqa: F401 — available to business-logic cells
from notebookutils import mssparkutils

# Gold sources can contain pre-1900 timestamps (e.g. permit_amendment) — rebase on read/write.
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite", "LEGACY")
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "LEGACY")
spark.conf.set("spark.sql.parquet.int96RebaseModeInWrite", "LEGACY")
spark.conf.set("spark.sql.parquet.int96RebaseModeInRead", "LEGACY")

# Control/lineage columns dropped from the gold-bound projection (keeps gold business-focused
# and stops SCD2 from churning on load timestamps / row hashes).
CTRL = {"dl_load_id", "bronze_file_name", "bronze_file_timestamp", "bronze_load_date",
        "dl_load_ts", "dl_rowhash", "silver_load_ts"}

# METADATA ********************

# META { "language": "python", "language_group": "synapse_pyspark" }

# CELL ********************

# NAMING CONVENTION (IMPORTANT): a notebook named 'nb_gold_tf_<object>' materializes the
# table 'stg.<object>'. The target is derived from THIS notebook's own name, so a copied
# template automatically targets the right table — just keep the nb_gold_tf_ prefix.
NB_PREFIX  = "nb_gold_tf_"
STG_SCHEMA = "stg"
NOTEBOOK_NAME = mssparkutils.runtime.context.get("currentNotebookName")
assert NOTEBOOK_NAME, "could not resolve current notebook name from runtime context"
assert NOTEBOOK_NAME.startswith(NB_PREFIX), f"notebook '{NOTEBOOK_NAME}' must be named '{NB_PREFIX}<object>'"
OBJECT_NAME  = NOTEBOOK_NAME[len(NB_PREFIX):]
TARGET_TABLE = f"{STG_SCHEMA}.{OBJECT_NAME}"
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {STG_SCHEMA}")

# Sources: silver is cross-lakehouse (gold is the default lakehouse) → read via abfss and
# register a temp view so the business-logic cell can be pure SparkSQL.
WORKSPACE_ID = "8f380f88-5ce5-48d1-9fa5-fbbfbe2685a0"
SILVER_LH_ID = "a0190e0e-c2f5-4740-ab90-a2f29b6e6991"
silver_permit = f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com/{SILVER_LH_ID}/Tables/silver/permit/"
spark.read.format("delta").load(silver_permit).createOrReplaceTempView("src_permit")

# Business projection: every silver column except the control/lineage set above.
SELECT_COLS = ", ".join(f"`{c}`" for c in spark.table("src_permit").columns if c not in CTRL)
print("notebook:", NOTEBOOK_NAME, "-> target:", TARGET_TABLE)

# METADATA ********************

# META { "language": "python", "language_group": "synapse_pyspark" }

# CELL ********************

# Drop the existing stg table so each build starts clean. The projection can change
# build-to-build (new/removed silver columns, type changes); a fresh table avoids the
# schema-merge conflicts an in-place overwrite could hit.
spark.sql(f"DROP TABLE IF EXISTS {TARGET_TABLE}")
print("dropped (if existed):", TARGET_TABLE)

# METADATA ********************

# META { "language": "python", "language_group": "synapse_pyspark" }

# CELL ********************

# BUSINESS LOGIC (SparkSQL) -> DataFrame. For dim_permit this is a straight projection of the
# current permit attributes; richer dimensions add joins / derivations / renames here.
df = spark.sql(f"""
    SELECT {SELECT_COLS}
    FROM src_permit
""")
print("built dataframe:", df.count(), "rows,", len(df.columns), "cols")

# METADATA ********************

# META { "language": "python", "language_group": "synapse_pyspark" }

# CELL ********************

# Write the DataFrame to the stg table — full overwrite each run; overwriteSchema lets the
# schema evolve freely since the table was dropped above.
(df.write.format("delta").mode("overwrite")
   .option("overwriteSchema", "true").saveAsTable(TARGET_TABLE))
print("wrote", df.count(), "rows to", TARGET_TABLE)

# METADATA ********************

# META { "language": "python", "language_group": "synapse_pyspark" }
