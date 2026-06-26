# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": { "name": "synapse_pyspark" },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "a0190e0e-c2f5-4740-ab90-a2f29b6e6991",
# META       "default_lakehouse_name": "lh_silver",
# META       "default_lakehouse_workspace_id": "8f380f88-5ce5-48d1-9fa5-fbbfbe2685a0",
# META       "known_lakehouses": [ { "id": "a0190e0e-c2f5-4740-ab90-a2f29b6e6991" } ]
# META     },
# META     "warehouse": {
# META       "default_warehouse": "dad1e7ab-adc2-bd51-408b-33e59ed9a608",
# META       "known_warehouses": [ { "id": "dad1e7ab-adc2-bd51-408b-33e59ed9a608", "type": "Datawarehouse" } ]
# META     }
# META   }
# META }

# CELL ********************

# nb_silver_registry — auto-populate app.object_registry + app.field_registry FROM SOURCE
# (no manual entry). object_registry is driven by app.pipeline_control (the ingestion's own
# table list, with primary_key / load_type / watermark / priority / dependency); field_registry
# is introspected from each landed bronze Delta table's schema. is_active is set by rule:
# operational/staging prefixes and not-yet-landed tables -> 0 (registered but skipped by silver).
from pyspark.sql import functions as F
from pyspark.sql.types import (StructType, StructField, StringType, LongType, IntegerType, BooleanType)
from notebookutils import mssparkutils

WORKSPACE_ID = "8f380f88-5ce5-48d1-9fa5-fbbfbe2685a0"
BRONZE_LH_ID = "8cd34a44-500a-47d9-aa2d-5ad0c2149858"
WAREHOUSE = "mines-data-platform-fabwh1"
BRONZE_TABLES = f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com/{BRONZE_LH_ID}/Tables/bronze/"

# bronze lineage/control columns — registered but flagged include_in_load=0
CTRL_COLS = {"dl_load_id", "bronze_file_name", "bronze_file_timestamp", "bronze_load_date",
             "dl_load_ts", "dl_rowhash"}
# operational/staging source tables — registered but is_active=0 (excluded from silver build)
INACTIVE_PREFIXES = ("celery_", "etl_", "django_", "auth_", "spatial_ref")

# METADATA ********************

# META { "language": "python", "language_group": "synapse_pyspark" }

# CELL ********************

# Source list = app.pipeline_control (what the ingestion pipeline is configured to land).
from com.microsoft.spark.fabric import Constants  # noqa: F401
pc = spark.read.synapsesql(f"{WAREHOUSE}.app.pipeline_control")
pc_rows = [r.asDict() for r in pc.collect()]
print("pipeline_control entries:", len(pc_rows))

# What actually landed in bronze (dir per table). Used to know which can be field-introspected.
landed = {e.name.rstrip("/") for e in mssparkutils.fs.ls(BRONZE_TABLES) if e.isDir}
print("bronze tables landed:", len(landed))

# METADATA ********************

# META { "language": "python", "language_group": "synapse_pyspark" }

# CELL ********************

def norm(name):
    return name.lower().replace(" ", "_").replace("-", "_").replace(".", "_")

landed_ci = {n.lower(): n for n in landed}  # case-insensitive lookup -> actual bronze dir name

obj_rows, fld_rows = [], []
fid = 0
for oid, cfg in enumerate(sorted(pc_rows, key=lambda c: c.get("target_table") or ""), start=1):
    name = cfg.get("target_table")
    if not name:
        continue
    actual = landed_ci.get(name.lower())          # real bronze dir name if it landed
    t = actual or name                            # register/resolve by the actual dir name
    pk = norm(cfg["primary_key"]) if cfg.get("primary_key") else None
    load_type = (cfg.get("load_type") or "FULL").upper()
    wm = cfg.get("watermark_column")
    src = cfg.get("source_entity") or f"public.{name}"
    pri = int(cfg.get("priority") or 100)
    dep = cfg.get("dependency_on")
    is_landed = actual is not None
    is_active = bool(is_landed and not name.lower().startswith(INACTIVE_PREFIXES))
    obj_rows.append((oid, src, "bronze", t, "silver", t, load_type, pk, wm,
                     is_active, 1, pri, dep))

    # fields — introspected from the landed bronze Delta schema (real source columns)
    if is_landed:
        try:
            schema = spark.read.format("delta").load(BRONZE_TABLES + t).schema
            for ordn, f in enumerate(schema.fields, start=1):
                cn = norm(f.name)
                fid += 1
                fld_rows.append((fid, oid, t, cn, f.dataType.simpleString(),
                                 bool(f.nullable), bool(pk and cn == pk),
                                 bool(cn not in CTRL_COLS), None, ordn))
        except Exception as e:
            print(f"field introspect failed for {t}: {e}")

active = sum(1 for r in obj_rows if r[9])
print(f"objects: {len(obj_rows)} (active={active}, inactive={len(obj_rows)-active}); fields: {len(fld_rows)}")
print("inactive (not landed or operational):",
      sorted(r[3] for r in obj_rows if not r[9])[:60])

# METADATA ********************

# META { "language": "python", "language_group": "synapse_pyspark" }

# CELL ********************

# Write both registries to the warehouse (overwrite — full rebuild from source each run).
AUDIT_BY = "nb_silver_registry"
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

fld_schema = StructType([
    StructField("field_id", LongType()), StructField("object_id", LongType()),
    StructField("entity", StringType()), StructField("column_name", StringType()),
    StructField("spark_type", StringType()), StructField("nullable", BooleanType()),
    StructField("is_pk", BooleanType()), StructField("include_in_load", BooleanType()),
    StructField("pii_type", StringType()), StructField("ordinal", IntegerType()),
])
fld_df = (spark.createDataFrame(fld_rows, fld_schema)
          .withColumn("created_date", F.current_timestamp()).withColumn("created_by", F.lit(AUDIT_BY))
          .withColumn("modified_date", F.current_timestamp()).withColumn("modified_by", F.lit(AUDIT_BY)))

(obj_df.write.mode("overwrite").option("overwriteSchema", "true")
    .synapsesql(f"{WAREHOUSE}.app.object_registry"))
(fld_df.write.mode("overwrite").option("overwriteSchema", "true")
    .synapsesql(f"{WAREHOUSE}.app.field_registry"))
print(f"WROTE object_registry={len(obj_rows)} field_registry={len(fld_rows)}")

# METADATA ********************

# META { "language": "python", "language_group": "synapse_pyspark" }
