# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "a0190e0e-c2f5-4740-ab90-a2f29b6e6991",
# META       "default_lakehouse_name": "lh_silver",
# META       "default_lakehouse_workspace_id": "8f380f88-5ce5-48d1-9fa5-fbbfbe2685a0",
# META       "known_lakehouses": [
# META         {
# META           "id": "a0190e0e-c2f5-4740-ab90-a2f29b6e6991"
# META         }
# META       ]
# META     }
# META   }
# META }

# CELL ********************

tables = spark.sql("SHOW TABLES IN lh_silver.silver")
tables.filter(tables.tableName.contains("mine_incident")).show(truncate=False)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

for t in ["lh_silver.silver.mine_status", "lh_silver.silver.mine_document", "lh_silver.silver.mine_verified_status"]:
    try:
        print(f"✅ {t} — {spark.table(t).count():,} rows")
    except:
        print(f"❌ {t} — NOT FOUND")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
