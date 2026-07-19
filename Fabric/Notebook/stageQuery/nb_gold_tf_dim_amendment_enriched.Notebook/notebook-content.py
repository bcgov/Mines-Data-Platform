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
# STANDARD GOLD TRANSFORM TEMPLATE  (see nb_gold_tf_dim_permit for the canonical example)
# dim_amendment_enriched is a JOIN-BASED type-2 dimension. It enriches each permit amendment
# with its parent permit's attributes (silver.permit) AND resolves the permit surrogate key from
# the already-built gold.dim_permit — so it DEPENDS ON dim_permit (a dim->dim DAG edge). It sits
# at LEVEL 1, built after the roots. BK = permit_amendment_id, surrogate = Amendment_SK.
# ════════════════════════════════════════════════════════════════════════════
from pyspark.sql import functions as F  # noqa: F401 — available to business-logic cells
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

NB_PREFIX  = "nb_gold_tf_"
STG_SCHEMA = "stg"
NOTEBOOK_NAME = mssparkutils.runtime.context.get("currentNotebookName")
assert NOTEBOOK_NAME, "could not resolve current notebook name from runtime context"
assert NOTEBOOK_NAME.startswith(NB_PREFIX), f"notebook '{NOTEBOOK_NAME}' must be named '{NB_PREFIX}<object>'"
OBJECT_NAME  = NOTEBOOK_NAME[len(NB_PREFIX):]
TARGET_TABLE = f"{STG_SCHEMA}.{OBJECT_NAME}"
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {STG_SCHEMA}")

# Two silver sources via abfss; gold.dim_permit is in THIS (default) lakehouse → referenced directly.
WORKSPACE_ID = "8f380f88-5ce5-48d1-9fa5-fbbfbe2685a0"
SILVER_LH_ID = "a0190e0e-c2f5-4740-ab90-a2f29b6e6991"
base = f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com/{SILVER_LH_ID}/Tables/silver"
spark.read.format("delta").load(f"{base}/permit_amendment/").createOrReplaceTempView("src_permit_amendment")
spark.read.format("delta").load(f"{base}/permit/").createOrReplaceTempView("src_permit")

# Projection: all amendment columns (pa alias) + permit attributes prefixed 'permit_' to avoid
# collisions (permit_id is the join key and stays from pa) + the resolved Permit_SK.
pa_cols = [c for c in spark.table("src_permit_amendment").columns if c not in CTRL]
p_cols  = [c for c in spark.table("src_permit").columns if c not in CTRL and c != "permit_id"]
PA_SEL = ", ".join(f"pa.`{c}`" for c in pa_cols)
P_SEL  = ", ".join(f"p.`{c}` AS `permit_{c}`" for c in p_cols)
print("notebook:", NOTEBOOK_NAME, "-> target:", TARGET_TABLE, "| pa cols:", len(pa_cols), "permit cols:", len(p_cols))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

spark.sql(f"DROP TABLE IF EXISTS {TARGET_TABLE}")
print("dropped (if existed):", TARGET_TABLE)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# BUSINESS LOGIC — join amendment + its permit + the gold permit surrogate key.
# LEFT JOINs so amendments with a missing permit still load (Permit_SK / permit_* = NULL).
df = spark.sql(f"""
    SELECT {PA_SEL}, {P_SEL}, d.Permit_SK
    FROM src_permit_amendment pa
    LEFT JOIN src_permit p
      ON pa.permit_id = p.permit_id
    LEFT JOIN gold.dim_permit d
      ON pa.permit_id = d.permit_id AND d.dl_iscurrent = true
""")
print("built dataframe:", df.count(), "rows,", len(df.columns), "cols")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

(df.write.format("delta").mode("overwrite")
   .option("overwriteSchema", "true").saveAsTable(TARGET_TABLE))
print("wrote", df.count(), "rows to", TARGET_TABLE)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
