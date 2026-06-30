#!/usr/bin/env bash
set -euo pipefail

# Deploy the gold framework notebooks (util + transforms + orchestrator) and run the
# orchestrator as the SPN; then verify via the warehouse app.gold_run_log.
CLIENT_ID="${AZURE_CLIENT_ID:?}"; CLIENT_SECRET="${AZURE_CLIENT_SECRET:?}"; TENANT_ID="${AZURE_TENANT_ID:?}"
: "${WORKSPACE_ID:?}"; : "${WAREHOUSE_NAME:?}"

log() { echo "$@" >&2; }

log "SPN login..."
az login --service-principal --username "$CLIENT_ID" --password "$CLIENT_SECRET" \
    --tenant "$TENANT_ID" --allow-no-subscriptions --output none
export FABRIC_TOKEN="$(az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken -o tsv)"

deploy_nb() { NOTEBOOK_NAME="$1" NOTEBOOK_DIR="$2" RUN="${3:-false}" python3 medallion/deploy/deploy_notebook.py; }

log "=== Deploy gold notebooks (util + transforms, no run) ==="
deploy_nb nb_util_gold                     Fabric/Notebook/utility/nb_util_gold.Notebook
deploy_nb nb_gold_tf_dim_permit              Fabric/Notebook/stageQuery/nb_gold_tf_dim_permit.Notebook
deploy_nb nb_gold_tf_fact_permit_amendment   Fabric/Notebook/stageQuery/nb_gold_tf_fact_permit_amendment.Notebook
deploy_nb nb_gold_tf_dim_party               Fabric/Notebook/stageQuery/nb_gold_tf_dim_party.Notebook
deploy_nb nb_gold_tf_dim_municipality        Fabric/Notebook/stageQuery/nb_gold_tf_dim_municipality.Notebook
deploy_nb nb_gold_tf_dim_amendment_enriched  Fabric/Notebook/stageQuery/nb_gold_tf_dim_amendment_enriched.Notebook
deploy_nb nb_gold_tf_fact_amendment_activity Fabric/Notebook/stageQuery/nb_gold_tf_fact_amendment_activity.Notebook

log "=== Deploy + RUN orchestrator ==="
deploy_nb nb_gold_orchestrator Fabric/Notebook/nb_gold_orchestrator.Notebook true

log "=== Verify via warehouse app.gold_run_log ==="
WH_ID="$(curl -s -H "Authorization: Bearer $FABRIC_TOKEN" \
    "https://api.fabric.microsoft.com/v1/workspaces/$WORKSPACE_ID/warehouses" \
    | jq -r --arg n "$WAREHOUSE_NAME" '.value[]? | select(.displayName==$n) | .id')"
CONN="$(curl -s -H "Authorization: Bearer $FABRIC_TOKEN" \
    "https://api.fabric.microsoft.com/v1/workspaces/$WORKSPACE_ID/warehouses/$WH_ID" \
    | jq -r '.properties.connectionString // empty')"
[[ -z "$CONN" ]] && { log "no warehouse conn"; exit 1; }

SQL_TOKEN="$(az account get-access-token --resource https://database.windows.net/ --query accessToken -o tsv)"
export SQL_SERVER="$CONN" SQL_DATABASE="$WAREHOUSE_NAME" SQL_FILE="medallion/sql/verify_gold.sql" SQL_ACCESS_TOKEN="$SQL_TOKEN"
python3 medallion/sql/run_sql.py
log "Verify complete."
