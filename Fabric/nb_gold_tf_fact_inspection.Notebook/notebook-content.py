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

# ════════════════════════════════════════════════════════════════════════════
# nb_gold_tf_fact_inspection — materializes stg.fact_inspection for the Gold orchestrator.
# Replaces the one-off SparkSQL build from July (BC (1)/Notebooks/gold_build_fact_inspection_corrected.sql)
# so the Inspections fact is SCRIPTED and rebuilt on every run.
# Fact type: upsert_fact on inspection_id (incremental). Level 1 — depends on dim_mine.
# Grain: one row per NRIS inspection. Columns = every silver.nris_inspection column
#   + mine_guid (via silver.mine on mine_no) + Mine_SK (current dim_mine row)
#   + inspection_date_key = CAST(inspection_date AS DATE)  (the model joins dim_date on this;
#     joining on the raw timestamp dropped ~88% of rows in July).
# ════════════════════════════════════════════════════════════════════════════
from pyspark.sql import functions as F  # noqa: F401
from notebookutils import mssparkutils

spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite", "LEGACY")
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "LEGACY")
spark.conf.set("spark.sql.parquet.int96RebaseModeInWrite", "LEGACY")
spark.conf.set("spark.sql.parquet.int96RebaseModeInRead", "LEGACY")

CTRL = {"dl_load_id", "bronze_file_name", "bronze_file_timestamp", "bronze_load_date",
        "dl_load_ts", "dl_rowhash", "silver_load_ts"}

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

NB_PREFIX  = "nb_gold_tf_"
STG_SCHEMA = "stg"
NOTEBOOK_NAME = mssparkutils.runtime.context.get("currentNotebookName")
assert NOTEBOOK_NAME, "could not resolve current notebook name from runtime context"
assert NOTEBOOK_NAME.startswith(NB_PREFIX), f"notebook '{NOTEBOOK_NAME}' must be named '{NB_PREFIX}<object>'"
OBJECT_NAME  = NOTEBOOK_NAME[len(NB_PREFIX):]
TARGET_TABLE = f"{STG_SCHEMA}.{OBJECT_NAME}"
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {STG_SCHEMA}")

# Silver + gold.dim_mine are all in the same (default) lakehouse -> read by table name.
# Dedupe: NRIS tables are full loads with no watermark, so silver.nris_inspection can hold
# one copy per run (2 copies on 18 Sep). silver.mine has 18 mine_no values shared by 2 mines
# (test mines). Keep one row per inspection_id and one mine per mine_no.
from pyspark.sql import Window
w_i = Window.partitionBy("inspection_id").orderBy(F.col("silver_load_ts").desc())
(spark.table("silver.nris_inspection")
    .withColumn("_rn", F.row_number().over(w_i)).filter("_rn = 1").drop("_rn")
    .createOrReplaceTempView("src_inspection"))

w_m = Window.partitionBy("mine_no").orderBy(F.col("create_timestamp").asc(), F.col("mine_guid"))
(spark.table("silver.mine")
    .withColumn("_rn", F.row_number().over(w_m)).filter("_rn = 1").drop("_rn")
    .createOrReplaceTempView("src_mine"))

spark.table("gold.dim_mine").createOrReplaceTempView("gold_dim_mine")

DERIVED = {"mine_guid", "mine_sk", "inspection_date_key"}
INSP_COLS = ", ".join(f"i.`{c}`" for c in spark.table("src_inspection").columns
                      if c not in CTRL and c.lower() not in DERIVED)
print("notebook:", NOTEBOOK_NAME, "-> target:", TARGET_TABLE,
      "| nris_inspection rows:", spark.table("src_inspection").count())

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

spark.sql(f"DROP TABLE IF EXISTS {TARGET_TABLE}")
print("dropped (if existed):", TARGET_TABLE)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# BUSINESS LOGIC — one row per inspection; mine resolved through silver.mine (mine_no -> mine_guid)
# then to the CURRENT dim_mine row (dim_mine is SCD2).
df = spark.sql(f"""
    SELECT {INSP_COLS},
           CAST(i.inspection_date AS DATE) AS inspection_date_key,
           m.mine_guid,
           d.Mine_SK
    FROM src_inspection i
    LEFT JOIN (SELECT mine_no, MAX(mine_guid) AS mine_guid FROM src_mine GROUP BY mine_no) m
           ON i.mine_no = m.mine_no
    LEFT JOIN gold_dim_mine d
           ON m.mine_guid = d.mine_guid AND d.dl_iscurrent = true
""")
n = df.count()
dupes = df.groupBy("inspection_id").count().filter("count > 1").count()
print("built dataframe:", n, "rows,", len(df.columns), "cols | duplicate inspection_id:", dupes)
assert dupes == 0, "fact_inspection grain broken: duplicate inspection_id"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

(df.write.format("delta").mode("overwrite")
   .option("overwriteSchema", "true").saveAsTable(TARGET_TABLE))
print("wrote", df.count(), "rows to", TARGET_TABLE)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

