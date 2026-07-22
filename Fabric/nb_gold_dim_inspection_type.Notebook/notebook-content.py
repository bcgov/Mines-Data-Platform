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

from pyspark.sql import functions as F

WORKSPACE_ID = "8f380f88-5ce5-48d1-9fa5-fbbfbe2685a0"
LH1_ID       = "8cd34a44-500a-47d9-aa2d-5ad0c2149858"   # mines_data_platform_lh1 (holds silver)
silver_path  = f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com/{LH1_ID}/Tables/silver/nris_inspection_type/"

df = (spark.read.format("delta").load(silver_path)
        .select(F.col("inspection_type_id").cast("int").alias("inspection_type_id"),
                F.col("inspection_type_code").alias("inspection_type_name"))
        .dropDuplicates(["inspection_type_id"]))

spark.sql("CREATE SCHEMA IF NOT EXISTS gold")
(df.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable("gold.dim_inspection_type"))

print(f"built gold.dim_inspection_type: {df.count()} rows")
df.orderBy("inspection_type_id").show(20, truncate=False)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
