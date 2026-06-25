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

# Transform: silver.permit_amendment + gold.dim_permit -> stg.v_fact_permit_amendment.
# Resolves the Permit_SK from the (already-built) gold dimension — this is why the DAG
# makes the fact depend on dim_permit.
WORKSPACE_ID = "8f380f88-5ce5-48d1-9fa5-fbbfbe2685a0"
SILVER_LH_ID = "a0190e0e-c2f5-4740-ab90-a2f29b6e6991"

CTRL = {"dl_load_id", "bronze_file_name", "bronze_file_timestamp", "bronze_load_date",
        "dl_load_ts", "dl_rowhash", "silver_load_ts"}

pa = f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com/{SILVER_LH_ID}/Tables/silver/permit_amendment/"
cols = [c for c in spark.read.format("delta").load(pa).columns if c not in CTRL]
col_list = ", ".join(f"pa.`{c}`" for c in cols)

spark.sql("CREATE SCHEMA IF NOT EXISTS stg")
spark.sql(f"""
    CREATE OR REPLACE VIEW stg.v_fact_permit_amendment AS
    SELECT {col_list}, d.Permit_SK
    FROM delta.`{pa}` pa
    LEFT JOIN gold.dim_permit d
      ON pa.permit_id = d.permit_id AND d.dl_iscurrent = true
""")
print("created stg.v_fact_permit_amendment with columns:", cols + ["Permit_SK"])

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
