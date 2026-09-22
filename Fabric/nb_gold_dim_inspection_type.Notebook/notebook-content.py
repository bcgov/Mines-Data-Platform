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

from pyspark.sql import functions as F


df = (spark.table("silver.nris_inspection_type")
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
