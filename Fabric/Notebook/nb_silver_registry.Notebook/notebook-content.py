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

%run nb_config

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# nb_silver_registry — build app.object_registry (what Silver loads, and each table's primary key)
# FROM THE CONTROL TABLE app.pipeline_control (Sebastian: "Silver should point to the control table,
# we added the primary keys there"). Replaces the old one-time source-catalog file.
#   - one row per target_table, using the LATEST version (control rows are versioned)
#   - is_active = active in the control table AND landed in bronze AND not an operational table
# nb_silver_build reads app.object_registry (bronze_table, primary_key, load_type, is_active).
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import (StructType, StructField, StringType, LongType, IntegerType, BooleanType)
from notebookutils import mssparkutils
from com.microsoft.spark.fabric import Constants  # noqa: F401 — registers the .synapsesql reader/writer

INACTIVE_PREFIXES = ("celery_", "etl_", "django_", "auth_", "spatial_ref")
AUDIT_BY = "nb_silver_registry"


def norm(name):
    return (name or "").strip().lower().replace(" ", "_").replace("-", "_").replace(".", "_")


def norm_pk(pk):
    cols = [norm(c) for c in (pk or "").split(",") if c.strip()]
    return ",".join(cols) if cols else None

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# 1) Control table -> latest version per target table
pc = spark.read.synapsesql(f"{WAREHOUSE}.app.pipeline_control")
w = Window.partitionBy(F.lower(F.col("target_table"))).orderBy(
    F.col("version_number").desc(), F.col("modified_date").desc())
latest = (pc.filter(F.col("target_table").isNotNull())
            .withColumn("_rn", F.row_number().over(w)).filter("_rn = 1").drop("_rn"))
ctl = latest.collect()
print("control-table target tables (latest version):", len(ctl),
      "| with primary_key:", sum(1 for r in ctl if (r["primary_key"] or "").strip()))

# 2) What actually landed in bronze (table folders under Tables/bronze of this lakehouse)
try:
    landed = {e.name.rstrip("/").lower() for e in mssparkutils.fs.ls(f"Tables/{BRONZE_SCHEMA}") if e.isDir}
except Exception as e:
    print(f"no bronze tables yet ({e})")
    landed = set()
print("bronze tables landed:", len(landed))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# 3) Build the registry rows (same shape nb_silver_build already reads)
obj_rows = []
for oid, r in enumerate(sorted(ctl, key=lambda x: norm(x["target_table"])), start=1):
    t = norm(r["target_table"])
    pk = norm_pk(r["primary_key"])
    load_type = (r["load_type"] or "FULL").upper()
    is_active = bool(r["is_active"]) and (t in landed) and not t.startswith(INACTIVE_PREFIXES)
    obj_rows.append((oid, r["source_entity"], BRONZE_SCHEMA, t, SILVER_SCHEMA, t, load_type, pk,
                     r["watermark_column"], is_active, 1, int(r["priority"] or 100), r["dependency_on"]))

active = sum(1 for x in obj_rows if x[9])
nopk = [x[3] for x in obj_rows if x[9] and not x[7]]
missing = sorted({norm(r["target_table"]) for r in ctl if r["is_active"]} - landed)
print(f"objects={len(obj_rows)} active={active} | active without primary_key={len(nopk)} {nopk[:10]}")
print(f"active in control table but not landed in bronze yet: {len(missing)} {missing[:10]}")

obj_schema = StructType([
    StructField("object_id", LongType()), StructField("source_entity", StringType()),
    StructField("bronze_schema", StringType()), StructField("bronze_table", StringType()),
    StructField("silver_schema", StringType()), StructField("silver_table", StringType()),
    StructField("load_type", StringType()), StructField("primary_key", StringType()),
    StructField("watermark_column", StringType()), StructField("is_active", BooleanType()),
    StructField("load_group", IntegerType()), StructField("priority", IntegerType()),
    StructField("dependency_on", StringType()),
])
obj_df = (spark.createDataFrame(obj_rows, obj_schema)
          .withColumn("created_date", F.current_timestamp()).withColumn("created_by", F.lit(AUDIT_BY))
          .withColumn("modified_date", F.current_timestamp()).withColumn("modified_by", F.lit(AUDIT_BY)))

# full rebuild each run — the control table is the source of truth
obj_df.write.mode("overwrite").option("overwriteSchema", "true").synapsesql(f"{WAREHOUSE}.app.object_registry")
print(f"WROTE app.object_registry = {len(obj_rows)} rows ({active} active)")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
