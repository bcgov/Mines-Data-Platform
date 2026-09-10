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

# ADMIN: register dim_incident_category + bridge_incident_category in app.gold_build,
# add the dependency row, and deactivate the dead fact_inspection node.
# Runs T-SQL against the warehouse via pyodbc + the notebook identity token. Idempotent.
import struct, pyodbc
from notebookutils import mssparkutils

SERVER = "ABJNW3YNHWFEVMBW2NUF4NM23Q-RAHTRD7FLTIURH5F7O734JUFUA.datawarehouse.fabric.microsoft.com"
DB     = "mines-data-platform-fabwh1"

token = None
for aud in ("pbi", "https://analysis.windows.net/powerbi/api", "https://database.windows.net/"):
    try:
        token = mssparkutils.credentials.getToken(aud); print("token audience:", aud); break
    except Exception as e:
        print("token failed for", aud, ":", str(e)[:120])
tb = token.encode("utf-16-le")
ts = struct.pack(f"<I{len(tb)}s", len(tb), tb)
conn = pyodbc.connect(
    f"Driver={{ODBC Driver 18 for SQL Server}};Server={SERVER},1433;Database={DB};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=60",
    attrs_before={1256: ts}, autocommit=True)
cur = conn.cursor()
def q(sql):
    cur.execute(sql)
    return cur.fetchall() if cur.description else cur.rowcount
print("connected:", q("SELECT DB_NAME(), SUSER_SNAME()"))
print("BEFORE:")
for r in q("SELECT node_name, table_type, load_strategy, is_active FROM app.gold_build ORDER BY node_name"): print("  ", tuple(r))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

print("gold_dependency columns:", [tuple(r) for r in q("SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='app' AND TABLE_NAME='gold_dependency' ORDER BY ORDINAL_POSITION")])
print("gold_dependency rows BEFORE:")
for r in q("SELECT * FROM app.gold_dependency ORDER BY node_name"): print("  ", tuple(r))

stmts = [
("dim_incident_category", """
IF NOT EXISTS (SELECT 1 FROM app.gold_build WHERE node_name = 'dim_incident_category')
INSERT INTO app.gold_build (node_name, gold_object, object_type, transform_notebook, source_table,
    table_type, load_strategy, surrogate_key, business_keys, non_historized_columns,
    is_active, created_date, created_by, modified_date, modified_by)
VALUES ('dim_incident_category','gold.dim_incident_category','DIM','nb_gold_tf_dim_incident_category',
    'stg.dim_incident_category','type1_dimension','full','Incident_Category_SK','mine_incident_category_code',NULL,
    1, GETDATE(),'system',GETDATE(),'system')"""),
("bridge_incident_category", """
IF NOT EXISTS (SELECT 1 FROM app.gold_build WHERE node_name = 'bridge_incident_category')
INSERT INTO app.gold_build (node_name, gold_object, object_type, transform_notebook, source_table,
    table_type, load_strategy, surrogate_key, business_keys, non_historized_columns,
    is_active, created_date, created_by, modified_date, modified_by)
VALUES ('bridge_incident_category','gold.bridge_incident_category','FACT','nb_gold_tf_bridge_incident_category',
    'stg.bridge_incident_category','reload_fact','full',NULL,'mine_incident_id,mine_incident_category_code',NULL,
    1, GETDATE(),'system',GETDATE(),'system')"""),
("dependency: delete stale", "DELETE FROM app.gold_dependency WHERE node_name = 'bridge_incident_category'"),
("dependency: insert",       "INSERT INTO app.gold_dependency (node_name, depends_on, created_date, created_by, modified_date, modified_by) VALUES ('bridge_incident_category','dim_incident_category', GETDATE(), 'system', GETDATE(), 'system')"),
("deactivate fact_inspection (transform notebook nb_gold_tf_fact_inspection does not exist)", """
UPDATE app.gold_build SET is_active = 0, modified_date = GETDATE(), modified_by = 'claude-admin'
WHERE node_name = 'fact_inspection' AND is_active = 1"""),
]
for name, sql in stmts:
    try:
        print(name, "->", q(sql))
    except Exception as e:
        print(name, "-> ERROR:", str(e)[:400])

print("gold_dependency rows AFTER:")
for r in q("SELECT * FROM app.gold_dependency ORDER BY node_name"): print("  ", tuple(r))
print("AFTER:")
for r in q("""SELECT gb.node_name, gb.table_type, gb.load_strategy, gb.is_active, gd.depends_on
FROM app.gold_build gb LEFT JOIN app.gold_dependency gd ON gb.node_name = gd.node_name
WHERE gb.node_name IN ('dim_incident_category','bridge_incident_category','fact_mine_incident','fact_inspection')
ORDER BY gb.node_name, gd.depends_on"""): print("  ", tuple(r))
conn.close()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
