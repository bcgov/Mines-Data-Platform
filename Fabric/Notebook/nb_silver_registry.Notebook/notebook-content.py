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
# META     },
# META     "warehouse": {
# META       "default_warehouse": "dad1e7ab-adc2-bd51-408b-33e59ed9a608",
# META       "known_warehouses": [
# META         {
# META           "id": "dad1e7ab-adc2-bd51-408b-33e59ed9a608",
# META           "type": "Datawarehouse"
# META         }
# META       ]
# META     }
# META   }
# META }

# CELL ********************

# nb_silver_registry — populate app.object_registry + app.field_registry FROM SOURCE metadata.
# Source = bronze Files/raw/mds_source_catalog (a pg_catalog dump landed by pl_extract_source_catalog,
# a clone of the team's Metadata_Extractor with the PK-only filter removed). This gives TRUE source
# primary keys (composite where applicable), every column with type/nullability/FK flags, and ALL
# public tables — including ones not yet landed in bronze. Enriched with load_type/watermark/priority
# from app.pipeline_control (ingestion config, not source metadata). is_active = landed in bronze AND
# not an operational/staging table.
from pyspark.sql import functions as F
from pyspark.sql.types import (StructType, StructField, StringType, LongType, IntegerType, BooleanType)
from notebookutils import mssparkutils
from collections import defaultdict

WORKSPACE_ID = "8f380f88-5ce5-48d1-9fa5-fbbfbe2685a0"
BRONZE_LH_ID = "8cd34a44-500a-47d9-aa2d-5ad0c2149858"
WAREHOUSE = "mines-data-platform-fabwh1"
RAW = f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com/{BRONZE_LH_ID}/Files/raw/"
BRONZE_TABLES = f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com/{BRONZE_LH_ID}/Tables/bronze/"
INACTIVE_PREFIXES = ("celery_", "etl_", "django_", "auth_", "spatial_ref")


def norm(name):
    return (name or "").strip().lower().replace(" ", "_").replace("-", "_").replace(".", "_")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Resolve the source catalog file/dir landed by pl_extract_source_catalog (name may lack .txt
# or be a folder of part files). Fail loudly with a directory listing if absent.
raw_entries = mssparkutils.fs.ls(RAW)
matches = [e.path for e in raw_entries if "mds_source_catalog" in e.name.lower()]
if not matches:
    raise Exception("source catalog not found in Files/raw; present: " + str([e.name for e in raw_entries]))
CATALOG = matches[0]
print("catalog path:", CATALOG)

# Source column catalog (CSV with header) — true PKs + every column.
cat = (spark.read.option("header", "true").option("multiLine", "true")
       .option("quote", '"').option("escape", "\\").csv(CATALOG)
       .filter(F.col("table_schema") == "public"))
cat_rows = cat.collect()
print("source catalog rows (public columns):", len(cat_rows))

# Ingestion config (load_type / watermark / priority / dependency) — not part of source metadata.
from com.microsoft.spark.fabric import Constants  # noqa: F401
pcm = {}
for r in spark.read.synapsesql(f"{WAREHOUSE}.app.pipeline_control").collect():
    d = r.asDict()
    if d.get("target_table"):
        pcm[d["target_table"].lower()] = d
print("pipeline_control entries:", len(pcm))

# What actually landed in bronze (case-insensitive) -> real dir name.
landed_ci = {e.name.rstrip("/").lower(): e.name.rstrip("/") for e in mssparkutils.fs.ls(BRONZE_TABLES) if e.isDir}
print("bronze tables landed:", len(landed_ci))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

cols_by_table = defaultdict(list)
for r in cat_rows:
    cols_by_table[r["table_name"]].append(r)

obj_rows, fld_rows = [], []
fid = 0
for oid, tname in enumerate(sorted(cols_by_table), start=1):
    cols = sorted(cols_by_table[tname], key=lambda r: int(r["column_position"] or 0))
    pk_cols = [norm(c["column_name"]) for c in cols if c["is_primary_key"] == "YES"]
    pk = ",".join(pk_cols) if pk_cols else None          # TRUE source PK (composite -> comma list)
    cfg = pcm.get(tname.lower(), {})
    load_type = (cfg.get("load_type") or "FULL").upper()
    wm = cfg.get("watermark_column")
    pri = int(cfg.get("priority") or 100)
    dep = cfg.get("dependency_on")
    actual = landed_ci.get(tname.lower())
    t = actual or tname
    is_active = bool(actual is not None and not tname.lower().startswith(INACTIVE_PREFIXES))
    obj_rows.append((oid, f"public.{tname}", "bronze", t, "silver", t, load_type, pk, wm,
                     is_active, 1, pri, dep))
    for c in cols:
        fid += 1
        fld_rows.append((fid, oid, t, norm(c["column_name"]), c["data_type"],
                         c["is_nullable"] == "YES", c["is_primary_key"] == "YES",
                         True, None, int(c["column_position"] or 0)))

active = sum(1 for r in obj_rows if r[9])
composite = sum(1 for r in obj_rows if r[7] and "," in r[7])
nopk = sum(1 for r in obj_rows if not r[7])
print(f"objects={len(obj_rows)} (active={active}); fields={len(fld_rows)}; composite_pk={composite}; no_pk={nopk}")
print("sample composite PKs:", [(r[3], r[7]) for r in obj_rows if r[7] and "," in r[7]][:8])

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Write both registries to the warehouse (full rebuild from source each run).
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

(obj_df.write.mode("overwrite").option("overwriteSchema", "true").synapsesql(f"{WAREHOUSE}.app.object_registry"))
(fld_df.write.mode("overwrite").option("overwriteSchema", "true").synapsesql(f"{WAREHOUSE}.app.field_registry"))
print(f"WROTE object_registry={len(obj_rows)} field_registry={len(fld_rows)}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
