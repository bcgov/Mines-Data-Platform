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

# Builds the Notice of Work "Received" fact table (intake side).
# Grain = one row per NoW application (now_application_id). This is a DIFFERENT report
# from NoW Permitting (Issued): it is keyed on submitted_date (received), counts distinct
# now_application_id, status <> 'PCO', excludes administrative amendments, and splits by
# type_of_application (New Permit / Amendment) and notice_of_work_type (commodity).
# Mirrors nb_build_fact_now_permit's standalone-build pattern.
from pyspark.sql import functions as F

# some source dates can be pre-1900 / junk - Spark needs legacy mode to read and write those
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "LEGACY")
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite", "LEGACY")

WS     = "8f380f88-5ce5-48d1-9fa5-fbbfbe2685a0"
SILVER = "a0190e0e-c2f5-4740-ab90-a2f29b6e6991"
BRONZE = "8cd34a44-500a-47d9-aa2d-5ad0c2149858"
sp = f"abfss://{WS}@onelake.dfs.fabric.microsoft.com/{SILVER}/Tables/silver/"
bp = f"abfss://{WS}@onelake.dfs.fabric.microsoft.com/{BRONZE}/Tables/bronze/"

# silver control/lineage columns dropped from the gold-bound projection
CTRL = {"dl_load_id", "bronze_file_name", "bronze_file_timestamp", "bronze_load_date",
        "dl_load_ts", "dl_rowhash", "silver_load_ts"}

# the grain + the admin-amendment link, from silver
spark.read.format("delta").load(sp + "now_application/").createOrReplaceTempView("src_na")               # grain: one row per now_application_id
spark.read.format("delta").load(sp + "application_reason_code_xref/").createOrReplaceTempView("src_x")   # a reason code here => administrative amendment

# notice_of_work_type (commodity lookup) - prefer silver, fall back to bronze (tiny static lookup)
nowt_src = None
for p in (sp + "notice_of_work_type/", bp + "notice_of_work_type/"):
    try:
        spark.read.format("delta").load(p).createOrReplaceTempView("src_nowt")
        nowt_src = p
        break
    except Exception as e:
        print("could not load", p, "->", str(e)[:120])
assert nowt_src, "notice_of_work_type not found in silver or bronze"
print("notice_of_work_type loaded from:", nowt_src)

# keep every now_application column (except lineage) so we don't guess names, then add derived cols
NA_COLS = [c for c in spark.table("src_na").columns if c not in CTRL]
SEL = ", ".join(f"na.`{c}`" for c in NA_COLS)
print("now_application cols kept:", len(NA_COLS))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# BUSINESS LOGIC. Roll the reason xref up to ONE row per application (so a multi-reason
# application can't fan the grain out), and roll notice_of_work_type to one row per code.
q = f"""
WITH reason AS (
    SELECT now_application_id,
           MAX(CASE WHEN application_reason_code IS NOT NULL AND application_reason_code <> ''
                    THEN 1 ELSE 0 END) AS has_reason
    FROM src_x
    GROUP BY now_application_id
),
nowt AS (
    SELECT notice_of_work_type_code, MAX(description) AS description
    FROM src_nowt
    GROUP BY notice_of_work_type_code
)
SELECT {SEL},
       CAST(na.submitted_date AS date)              AS submitted_date_key,
       t.description                                AS notice_of_work_type_description,
       COALESCE(r.has_reason, 0)                    AS is_administrative_amendment
FROM src_na na
LEFT JOIN reason r ON na.now_application_id = r.now_application_id
LEFT JOIN nowt   t ON na.notice_of_work_type_code = t.notice_of_work_type_code
"""
df = spark.sql(q)

spark.sql("CREATE SCHEMA IF NOT EXISTS gold")
# full rebuild each run - overwrite, not an incremental load (mirrors fact_now_permit)
df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable("gold.fact_now_application")
print("rows", df.count(), "cols", len(df.columns))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Power BI cannot store dates before 1899-12-30 - null any junk submitted dates so the model
# does not choke. They fall outside every report window anyway.
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "LEGACY")
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite", "LEGACY")
spark.sql("""UPDATE gold.fact_now_application
             SET submitted_date = NULL, submitted_date_key = NULL
             WHERE submitted_date < CAST('1900-01-01' AS TIMESTAMP)""")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# sanity check after the build. non_pco is what the report actually counts.
spark.sql("""
  SELECT COUNT(*) AS total_rows,
         COUNT(DISTINCT now_application_id) AS distinct_apps,
         SUM(CASE WHEN now_application_status_code <> 'PCO' THEN 1 ELSE 0 END) AS non_pco_rows,
         SUM(is_administrative_amendment) AS admin_rows,
         MIN(submitted_date_key) AS min_submitted,
         MAX(submitted_date_key) AS max_submitted
  FROM gold.fact_now_application
""").show()

# distribution by commodity (Chart 3) and by type (Charts 1 & 2)
spark.sql("""SELECT notice_of_work_type_description, COUNT(*) c
             FROM gold.fact_now_application
             WHERE now_application_status_code <> 'PCO'
             GROUP BY 1 ORDER BY c DESC""").show(50, False)
spark.sql("""SELECT type_of_application, COUNT(*) c
             FROM gold.fact_now_application
             WHERE now_application_status_code <> 'PCO'
             GROUP BY 1 ORDER BY c DESC""").show()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
