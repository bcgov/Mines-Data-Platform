# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": { "name": "synapse_pyspark" },
# META   "dependencies": {}
# META }

# CELL ********************

# Load mxfabric path classes via %run (v1 delivery mechanism)
%run nb_util_paths

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Build the registry. Prefer Spark conf (mxdata.lakehouse.*) if set at the workspace;
# otherwise register inline with the GUIDs captured during lakehouse provisioning.
reg = LakehouseRegistry()
reg.register("bronze_lakehouse", "<WORKSPACE_ID>", "<BRONZE_LH_ID>")
reg.register("silver_lakehouse", "<WORKSPACE_ID>", "<SILVER_LH_ID>")
reg.register("gold_lakehouse",   "<WORKSPACE_ID>", "<GOLD_LH_ID>")

factory = StoragePathFactory(reg, platform="fabric")

for layer in ("bronze", "silver", "gold"):
    print(layer, "->", factory.delta_table_path(layer, "smoke", "ping"))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cross-lakehouse write/read proof: write a 1-row Delta table into the SILVER lakehouse
# via an absolute OneLake path, then read it back.
from pyspark.sql import Row

silver_path = factory.delta_table_path("silver", "smoke", "ping")
spark.createDataFrame([Row(id=1, note="foundation-ok")]).write.format("delta") \
    .mode("overwrite").save(silver_path)

readback = spark.read.format("delta").load(silver_path)
assert readback.count() == 1, "cross-lakehouse Delta write/read failed"
display(readback)
print("FOUNDATION SMOKE PASSED")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
