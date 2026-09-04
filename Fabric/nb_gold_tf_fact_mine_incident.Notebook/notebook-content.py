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
#   effective_timestamp (date part)  -> dim_date  (Effective_Date_SK)   [added 2026-09-03]
#
# DO flag (Dangerous Occurrence): determination_type_code = 'DO'. Matches the
#   Metabase corporate report (questions 3287 / 3289). No category join needed.
#
# EFFECTIVE TIMESTAMP (added 2026-09-03) — the rule the corporate-report KPI cards
#   (Metabase 3284 / 3285 / 3288, R. Gulati) count on:
#     if reported_timestamp > incident_timestamp + 24h  -> use incident_timestamp
#     else                                              -> use reported_timestamp
#   i.e. a report logged more than a day late is distrusted and the incident time
#   is used instead. Materialised here because the semantic model is Direct Lake
#   (no DAX calculated columns). The two corporate CHARTS still use reported_timestamp,
#   so Reported_Date_SK is kept alongside — the measure picks which key to use.
#
# Incident categories are many-to-many -> see nb_gold_tf_bridge_incident_category
#   and nb_gold_tf_dim_incident_category (not joined here).
#
# KNOWN DIVERGENCES vs Metabase (documented, deliberate):
#   * WHERE deleted_ind = 0 — Metabase applies no deleted filter (38 rows at source).
#   * Source carries a future-dated incident (reported 2040-08-22). It is NOT filtered
#     here; bound the date axis in the report, and confirm with R. Gulati.
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
#   Effective ts:  derived in src_mine_incident_adj (see cell below) — never NULL,
#                  both source timestamps are NOT NULL across all rows (verified 2026-09-01).
#
# Confirmed Gold column names (from Spark schema):
#   SCD2 flag:  dl_iscurrent = 1  (dim_mine + dim_party)
#   dim_date:   Date_SK (surrogate key), full_date (join column)

# Effective timestamp — computed once, then the main SELECT reads it like any other column.
spark.sql("""
    SELECT
        *,
        CASE
            WHEN reported_timestamp > incident_timestamp + INTERVAL 24 HOURS
            THEN incident_timestamp
            ELSE reported_timestamp
        END AS effective_timestamp
    FROM src_mine_incident
""").createOrReplaceTempView("src_mine_incident_adj")

df = spark.sql("""
    SELECT
        i.mine_incident_id,
        i.mine_incident_guid,
        i.mine_incident_no,

        -- Surrogate keys
        dm.Mine_SK,
        rdd.Date_SK                   AS Reported_Date_SK,
        idd.Date_SK                   AS Incident_Date_SK,
        edd.Date_SK                   AS Effective_Date_SK,
        dp_rpt.Party_SK               AS Reported_To_Inspector_SK,
        dp_res.Party_SK               AS Responsible_Inspector_SK,
        dp_det.Party_SK               AS Determination_Inspector_SK,

        -- Incident timestamps
        i.reported_timestamp,
        CAST(i.reported_timestamp AS DATE) AS reported_date,
        i.incident_timestamp,
        CAST(i.incident_timestamp AS DATE) AS incident_date,
        i.effective_timestamp,
        CAST(i.effective_timestamp AS DATE) AS effective_date,
        CASE WHEN i.reported_timestamp > i.incident_timestamp + INTERVAL 24 HOURS
             THEN 1 ELSE 0 END          AS is_late_report,

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

    FROM src_mine_incident_adj i

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

    -- Date keys: effective date (corporate-report KPI rule)
    LEFT JOIN gold_dim_date edd
        ON edd.full_date = CAST(i.effective_timestamp AS DATE)

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

    -- Filter: exclude soft-deleted incidents (38 rows at source; Metabase does not filter these)
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

# ── Schema guard (added 2026-09-03) ─────────────────────────────────────────
# build_fact's MERGE (whenMatchedUpdateAll / whenNotMatchedInsertAll) does NOT
# evolve the target schema: any stg column missing from gold.fact_mine_incident
# would be silently dropped. So, when the gold table already exists, add any
# missing stg columns to it here (typed from the stg schema) before the
# orchestrator merges. First-ever load needs nothing — build_fact creates the
# table from stg.
GOLD_TABLE = f"gold.{OBJECT_NAME}"
if spark.catalog.tableExists(GOLD_TABLE):
    gold_cols = {f.name.lower() for f in spark.table(GOLD_TABLE).schema}
    missing   = [f for f in spark.table(TARGET_TABLE).schema if f.name.lower() not in gold_cols]
    if missing:
        ddl = ", ".join(f"`{f.name}` {f.dataType.simpleString()}" for f in missing)
        spark.sql(f"ALTER TABLE {GOLD_TABLE} ADD COLUMNS ({ddl})")
        print(f"schema guard: added {len(missing)} column(s) to {GOLD_TABLE}: "
              + ", ".join(f.name for f in missing))
    else:
        print(f"schema guard: {GOLD_TABLE} already has every stg column")
else:
    print(f"schema guard: {GOLD_TABLE} does not exist yet — build_fact will create it")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
