# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": { "name": "synapse_pyspark" },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "<BRONZE_LH_ID>",
# META       "default_lakehouse_name": "mines_data_platform_lh1",
# META       "default_lakehouse_workspace_id": "<WORKSPACE_ID>",
# META       "known_lakehouses": [ { "id": "<BRONZE_LH_ID>" } ]
# META     }
# META   }
# META }

# CELL ********************

# Foundation smoke test — self-contained (no %run), validates cross-lakehouse
# OneLake path resolution + Delta write/read as the running identity.
# GUID placeholders are injected at deploy time.
WORKSPACE_ID = "<WORKSPACE_ID>"
BRONZE_LH_ID = "<BRONZE_LH_ID>"
SILVER_LH_ID = "<SILVER_LH_ID>"
GOLD_LH_ID   = "<GOLD_LH_ID>"

def abfss(lakehouse_id, path_type, *parts):
    base = f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com/{lakehouse_id}/{path_type}"
    return base + "/" + "/".join(parts) + "/"

for name, lh in (("bronze", BRONZE_LH_ID), ("silver", SILVER_LH_ID), ("gold", GOLD_LH_ID)):
    print(name, "->", abfss(lh, "Tables", "smoke", "ping"))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cross-lakehouse write/read proof: write a 1-row Delta dataset into the SILVER
# lakehouse via an absolute OneLake path, then read it back.
from pyspark.sql import Row

silver_path = abfss(SILVER_LH_ID, "Files", "_smoke", "ping")
print("writing:", silver_path)

spark.createDataFrame([Row(id=1, note="foundation-ok")]) \
    .write.format("delta").mode("overwrite").save(silver_path)

count = spark.read.format("delta").load(silver_path).count()
assert count == 1, f"cross-lakehouse Delta write/read failed: expected 1, got {count}"
print("FOUNDATION SMOKE PASSED — rows:", count)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
