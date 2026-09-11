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

# nb_config — the ONE place for environment settings. Every entry notebook runs `%run nb_config` first.
# Values come from the Variable Library "vl_mdp" (DEV = default values, TEST / PROD = value sets),
# so no workspace / lakehouse / warehouse IDs live in code. All data is in ONE lakehouse per
# environment, split by schema:  bronze -> silver -> stg -> gold. Control/log tables: warehouse app.*
import notebookutils

_vl = notebookutils.variableLibrary.getLibrary("vl_mdp")
ENVIRONMENT    = _vl.environment        # dev | test | prod
LAKEHOUSE_NAME = _vl.lakehouse_name     # mcm_mdp_lh1_<env>  (must be this notebook's default lakehouse)
WAREHOUSE      = _vl.warehouse_name     # mcm-mdp-fabwh1-<env>  (app.* control + log tables)
RAW_ROOT_PATH  = _vl.raw_root_path      # Files/raw/parquet  (Sebastian's landing folder)

BRONZE_SCHEMA = "bronze"
SILVER_SCHEMA = "silver"
STG_SCHEMA    = "stg"
GOLD_SCHEMA   = "gold"

# Safety check: fail fast if the notebook is attached to a different lakehouse than this
# environment's (e.g. a deployment that did not re-bind the default lakehouse).
_ctx = notebookutils.runtime.context
_attached = _ctx.get("defaultLakehouseName")
if _attached and _attached != LAKEHOUSE_NAME:
    raise Exception(f"Default lakehouse is '{_attached}' but vl_mdp says '{LAKEHOUSE_NAME}' "
                    f"for environment '{ENVIRONMENT}'. Re-bind the default lakehouse.")
print(f"nb_config | env={ENVIRONMENT} lakehouse={LAKEHOUSE_NAME} warehouse={WAREHOUSE} raw={RAW_ROOT_PATH}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
