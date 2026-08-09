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

# Builds the Notice of Work permitting fact table.
# Grain = one row per permit amendment. We work out the two report flags here -
# is it approved, and is it an administrative amendment - so the measures downstream stay simple.
from pyspark.sql import functions as F

# permit_amendment has a few ancient pre-1900 issue dates - Spark needs legacy mode to read and write those
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead","LEGACY")
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite","LEGACY")

# grab the four permitting tables from silver. abfss path because silver sits in a different lakehouse
b="abfss://8f380f88-5ce5-48d1-9fa5-fbbfbe2685a0@onelake.dfs.fabric.microsoft.com/a0190e0e-c2f5-4740-ab90-a2f29b6e6991/Tables/silver/"
spark.read.format("delta").load(b+"permit_amendment/").createOrReplaceTempView("src_pa")            # the permit actions - this is our grain
spark.read.format("delta").load(b+"now_application/").createOrReplaceTempView("src_na")             # carries the AIA approved status
spark.read.format("delta").load(b+"now_application_identity/").createOrReplaceTempView("src_nai")   # bridge from now_application_guid to now_application_id
spark.read.format("delta").load(b+"application_reason_code_xref/").createOrReplaceTempView("src_x")  # a reason code in here means the amendment is administrative

# The query is two steps - the JOIN conditions sit on their own lines so they are easy to read:
#   Step 1 (app CTE): roll the application side up to ONE row per now_application_guid,
#           so a permit cannot match several application rows and get double counted.
#   Step 2 (final SELECT): attach that rolled-up info onto each permit amendment.
q = """
WITH app AS (
SELECT nai.now_application_guid,
MAX(CASE WHEN na.now_application_status_code = 'AIA' THEN 1 ELSE 0 END) AS is_aia,
MAX(CASE WHEN aprcx.application_reason_code IS NOT NULL AND aprcx.application_reason_code <> '' THEN 1 ELSE 0 END) AS has_reason
FROM src_nai nai
JOIN src_na na ON nai.now_application_id = na.now_application_id
LEFT JOIN src_x aprcx ON na.now_application_id = aprcx.now_application_id
GROUP BY nai.now_application_guid
)
SELECT pa.permit_amendment_id,
pa.permit_id,
pa.permit_amendment_type_code,
pa.permit_amendment_status_code,
pa.now_application_guid,
pa.mine_guid,
pa.issue_date,
CAST(pa.issue_date AS date) AS issue_date_key,
pa.deleted_ind,
COALESCE(app.is_aia, 0) AS is_approved_aia,
CASE WHEN COALESCE(app.is_aia, 0) = 1 THEN 'AIA' ELSE NULL END AS now_application_status_code,
COALESCE(app.has_reason, 0) AS is_administrative_amendment
FROM src_pa pa
LEFT JOIN app ON pa.now_application_guid = app.now_application_guid
"""
df = spark.sql(q)

spark.sql("CREATE SCHEMA IF NOT EXISTS gold")
# full rebuild each run - overwrite, not an incremental load
df.write.format("delta").mode("overwrite").option("overwriteSchema","true").saveAsTable("gold.fact_now_permit")
print("rows", df.count(), "cols", len(df.columns))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

r=spark.read.option("recursiveFileLookup","true").parquet(B+"Files/raw/public.now_application/"); r.selectExpr("count(1) c","max(submitted_date) m").show()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

pa=spark.read.option("recursiveFileLookup","true").parquet(B+"Files/raw/public.permit_amendment/")
print("RAW_PA rows=", pa.count(), " distinct_id=", pa.select("permit_amendment_id").distinct().count())

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

r=spark.sql("select year(current_date()) as y, month(current_date()) as m").first()
curfy = r.y if r.m>=4 else r.y-1
lo=curfy-5
spark.sql("ALTER TABLE gold.dim_date ADD COLUMNS (fiscal_year_last6 STRING)")
spark.sql("UPDATE gold.dim_date SET fiscal_year_last6 = CASE WHEN fiscal_year >= "+str(lo)+" AND fiscal_year <= "+str(curfy)+" THEN fiscal_year_label ELSE NULL END")
print("curfy", curfy, "lo", lo)
spark.sql("SELECT DISTINCT fiscal_year, fiscal_year_last6 FROM gold.dim_date WHERE fiscal_year_last6 IS NOT NULL ORDER BY fiscal_year").show()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# quick sanity check on the flags after the build.
# approved_ogpamd_permits should land around 157 - the all-time approved new plus amendment permits.
spark.sql("SELECT COUNT(*) AS total_rows, SUM(is_approved_aia) AS aia_rows, SUM(is_administrative_amendment) AS admin_rows, COUNT(DISTINCT CASE WHEN is_approved_aia=1 AND permit_amendment_type_code IN ('OGP','AMD') AND is_administrative_amendment=0 THEN permit_id END) AS approved_ogpamd_permits, MAX(issue_date_key) AS max_issue_date_key FROM gold.fact_now_permit").show()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Power BI cannot store dates before 1899-12-30, and permit_amendment has a handful of junk ones
# like the year 1194. Null those out so the model does not choke - they fall outside every report
# window anyway, so no real permits are lost. This clears about 971 rows.
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead","LEGACY")
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite","LEGACY")
spark.sql("UPDATE gold.fact_now_permit SET issue_date = NULL, issue_date_key = NULL WHERE issue_date < CAST('1900-01-01' AS TIMESTAMP)")
# min date should now be around 1908 instead of 1194
spark.sql("SELECT MIN(issue_date) AS min_dt, MAX(issue_date) AS max_dt, SUM(CASE WHEN issue_date IS NULL THEN 1 ELSE 0 END) AS null_dates FROM gold.fact_now_permit").show()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
