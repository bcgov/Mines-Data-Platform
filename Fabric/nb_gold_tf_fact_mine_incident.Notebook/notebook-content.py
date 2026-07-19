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

# ════════════════════════════════════════════════════════════════════════════
# GOLD TRANSFORM — fact_mine_incident
#   Cell 1  imports + Spark properties              (this cell)
#   Cell 2  derive TARGET_TABLE from notebook name + register sources
#   Cell 3  drop the existing stg table
#   Cell 4  SparkSQL business logic -> DataFrame
#   Cell 5  write the DataFrame to TARGET_TABLE
#
# Grain: one row per mine incident (mine_incident_id is the natural PK).
# Fact type: upsert_fact — incremental load, upsert on mine_incident_id.
# Level 1 in Gold DAG — depends on: dim_mine, dim_party, dim_date.
#
# Surrogate key joins:
#   mine_guid                        -> dim_mine  (Mine_SK)
#   reported_date                    -> dim_date  (Reported_Date_SK)
#   incident_timestamp (date part)   -> dim_date  (Incident_Date_SK)
#   reported_to_inspector_party_guid -> dim_party (Reported_To_Inspector_SK)
#   responsible_inspector_party_guid -> dim_party (Responsible_Inspector_SK)
#   determination_inspector_party_guid -> dim_party (Determination_Inspector_SK)
#
# DO flag (Dangerous Occurrence): incident is a DO if any row in
#   mine_incident_category_xref maps to a category where
#   is_dangerous_occurrence = TRUE (verify column name once Silver lands).
#
# ⚠️  BLOCKED until GRANT SELECT applied on public.mine_incident in PostgreSQL.
#     Once unblocked: re-run Bronze + Silver pipeline, then this notebook runs.
# ════════════════════════════════════════════════════════════════════════════
from pyspark.sql import functions as F  # noqa: F401
from notebookutils import mssparkutils

spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite", "LEGACY")
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "LEGACY")
spark.conf.set("spark.sql.parquet.int96RebaseModeInWrite", "LEGACY")
spark.conf.set("spark.sql.parquet.int96RebaseModeInRead", "LEGACY")

# Control/lineage columns stripped from every Silver read.
CTRL = {"dl_load_id", "bronze_file_name", "bronze_file_timestamp", "bronze_load_date",
        "dl_load_ts", "dl_rowhash", "silver_load_ts"}

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# NAMING CONVENTION: notebook named nb_gold_tf_<object> materializes stg.<object>.
NB_PREFIX     = "nb_gold_tf_"
STG_SCHEMA    = "stg"
NOTEBOOK_NAME = mssparkutils.runtime.context.get("currentNotebookName")
assert NOTEBOOK_NAME, "could not resolve current notebook name from runtime context"
assert NOTEBOOK_NAME.startswith(NB_PREFIX), f"notebook must be named '{NB_PREFIX}<object>'"
OBJECT_NAME   = NOTEBOOK_NAME[len(NB_PREFIX):]
TARGET_TABLE  = f"{STG_SCHEMA}.{OBJECT_NAME}"
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {STG_SCHEMA}")

# Silver is cross-lakehouse (gold is the default lakehouse) -> read via abfss.
WORKSPACE_ID = "8f380f88-5ce5-48d1-9fa5-fbbfbe2685a0"
SILVER_LH_ID = "a0190e0e-c2f5-4740-ab90-a2f29b6e6991"
base = f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com/{SILVER_LH_ID}/Tables/silver"

# Silver source — mine_incident is confirmed in Silver (silver_load_ts 2026-06-26).
spark.read.format("delta").load(f"{base}/mine_incident/").createOrReplaceTempView("src_mine_incident")

# Gold dimension lookups — Gold is the default lakehouse, readable as spark.table().
spark.table("gold.dim_mine").createOrReplaceTempView("gold_dim_mine")
spark.table("gold.dim_date").createOrReplaceTempView("gold_dim_date")
spark.table("gold.dim_party").createOrReplaceTempView("gold_dim_party")

print("notebook:", NOTEBOOK_NAME, "-> target:", TARGET_TABLE)
print("mine_incident source rows:", spark.table("src_mine_incident").count())

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Drop the existing stg table so each build starts clean (schema may change build-to-build).
spark.sql(f"DROP TABLE IF EXISTS {TARGET_TABLE}")
print("dropped (if existed):", TARGET_TABLE)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# BUSINESS LOGIC — build fact_mine_incident.
#
# Confirmed schema from silver.mine_incident (silver_load_ts 2026-06-26):
#   PK:            mine_incident_id (integer)
#   Date cols:     reported_timestamp, incident_timestamp (both TIMESTAMP)
#   Counts:        number_of_fatalities, number_of_injuries
#   Party GUIDs:   reported_to_inspector_party_guid,
#                  responsible_inspector_party_guid,
#                  determination_inspector_party_guid
#   DO flag:       determination_type_code = 'DO' (values: 'DO', 'NDO')
#                  No category join needed — DO is determined directly.
#
# Confirmed Gold column names (from Spark schema):
#   SCD2 flag:  dl_iscurrent = 1  (dim_mine + dim_party)
#   dim_date:   Date_SK (surrogate key), full_date (join column)

df = spark.sql("""
    SELECT
        i.mine_incident_id,
        i.mine_incident_guid,
        i.mine_incident_no,

        -- Surrogate keys
        dm.Mine_SK,
        rdd.Date_SK                   AS Reported_Date_SK,
        idd.Date_SK                   AS Incident_Date_SK,
        dp_rpt.Party_SK               AS Reported_To_Inspector_SK,
        dp_res.Party_SK               AS Responsible_Inspector_SK,
        dp_det.Party_SK               AS Determination_Inspector_SK,

        -- Incident timestamps
        i.reported_timestamp,
        CAST(i.reported_timestamp AS DATE) AS reported_date,
        i.incident_timestamp,
        CAST(i.incident_timestamp AS DATE) AS incident_date,

        -- Incident facts
        i.number_of_fatalities,
        i.number_of_injuries,
        i.emergency_services_called,
        i.followup_inspection,
        i.followup_investigation_type_code,
        i.determination_type_code,
        i.status_code,
        i.incident_location,
        i.incident_timezone,

        -- DO flag: Dangerous Occurrence is determined by determination_type_code = 'DO'
        CASE WHEN i.determination_type_code = 'DO' THEN 1 ELSE 0 END
            AS is_dangerous_occurrence

    FROM src_mine_incident i

    -- Mine surrogate key (SCD2 current row)
    LEFT JOIN gold_dim_mine dm
        ON i.mine_guid = dm.mine_guid
        AND dm.dl_iscurrent = 1

    -- Date keys: reported date
    LEFT JOIN gold_dim_date rdd
        ON rdd.full_date = CAST(i.reported_timestamp AS DATE)

    -- Date keys: incident date
    LEFT JOIN gold_dim_date idd
        ON idd.full_date = CAST(i.incident_timestamp AS DATE)

    -- Party roles (3 FKs)
    LEFT JOIN gold_dim_party dp_rpt
        ON i.reported_to_inspector_party_guid = dp_rpt.party_guid
        AND dp_rpt.dl_iscurrent = 1

    LEFT JOIN gold_dim_party dp_res
        ON i.responsible_inspector_party_guid = dp_res.party_guid
        AND dp_res.dl_iscurrent = 1

    LEFT JOIN gold_dim_party dp_det
        ON i.determination_inspector_party_guid = dp_det.party_guid
        AND dp_det.dl_iscurrent = 1

    -- Filter: exclude soft-deleted incidents
    WHERE i.deleted_ind = 0
""")
print("built dataframe:", df.count(), "rows,", len(df.columns), "cols")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Write the DataFrame to the stg table — full overwrite each run.
# The orchestrator then merges stg.fact_mine_incident -> gold.fact_mine_incident
# using upsert on mine_incident_id (incremental load strategy).
(df.write.format("delta").mode("overwrite")
   .option("overwriteSchema", "true").saveAsTable(TARGET_TABLE))
print("wrote", df.count(), "rows to", TARGET_TABLE)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
