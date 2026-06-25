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

# Transform: silver.permit -> stg.v_dim_permit (the in-between layer). Selects business
# columns (drops lineage/control cols so SCD2 doesn't churn on load timestamps).
WORKSPACE_ID = "8f380f88-5ce5-48d1-9fa5-fbbfbe2685a0"
SILVER_LH_ID = "a0190e0e-c2f5-4740-ab90-a2f29b6e6991"

CTRL = {"dl_load_id", "bronze_file_name", "bronze_file_timestamp", "bronze_load_date",
        "dl_load_ts", "dl_rowhash", "silver_load_ts"}

silver_permit = f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com/{SILVER_LH_ID}/Tables/silver/permit/"
cols = [c for c in spark.read.format("delta").load(silver_permit).columns if c not in CTRL]
col_list = ", ".join(f"`{c}`" for c in cols)

spark.sql("CREATE SCHEMA IF NOT EXISTS stg")
spark.sql(f"""
    CREATE OR REPLACE VIEW stg.v_dim_permit AS
    SELECT {col_list}
    FROM delta.`{silver_permit}`
""")
print("created stg.v_dim_permit with columns:", cols)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
