#!/usr/bin/env bash
set -euo pipefail

# Deploy + run nb_silver_build as the SPN, then verify the centralized warehouse
# app.error_log received the notebook's failures (warehouse endpoint = no sync lag).
CLIENT_ID="${AZURE_CLIENT_ID:?}"; CLIENT_SECRET="${AZURE_CLIENT_SECRET:?}"; TENANT_ID="${AZURE_TENANT_ID:?}"
: "${WORKSPACE_ID:?}"; : "${WAREHOUSE_NAME:?}"

log() { echo "$@" >&2; }

log "SPN login..."
az login --service-principal --username "$CLIENT_ID" --password "$CLIENT_SECRET" \
    --tenant "$TENANT_ID" --allow-no-subscriptions --output none
export FABRIC_TOKEN="$(az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken -o tsv)"

deploy_nb() { NOTEBOOK_NAME="$1" NOTEBOOK_DIR="$2" RUN="${3:-false}" python3 medallion/deploy/deploy_notebook.py; }

log "=== Deploy + run nb_silver_registry (auto-populate object_registry + field_registry) ==="
deploy_nb nb_silver_registry Fabric/Notebook/nb_silver_registry.Notebook true

log "=== Deploy + run nb_silver_build (registry-driven, all active objects) ==="
deploy_nb nb_silver_build Fabric/Notebook/nb_silver_build.Notebook true

log "=== Verify centralized error log (warehouse app.error_log, layer='silver') ==="
WH_JSON="$(curl -s -H "Authorization: Bearer $FABRIC_TOKEN" \
    "https://api.fabric.microsoft.com/v1/workspaces/$WORKSPACE_ID/warehouses")"
WH_ID="$(echo "$WH_JSON" | jq -r --arg n "$WAREHOUSE_NAME" '.value[]? | select(.displayName==$n) | .id')"
CONN="$(curl -s -H "Authorization: Bearer $FABRIC_TOKEN" \
    "https://api.fabric.microsoft.com/v1/workspaces/$WORKSPACE_ID/warehouses/$WH_ID" \
    | jq -r '.properties.connectionString // empty')"
if [[ -z "$CONN" ]]; then log "Could not resolve warehouse connection string."; exit 1; fi
log "Warehouse SQL endpoint: $CONN"

SQL_TOKEN="$(az account get-access-token --resource https://database.windows.net/ --query accessToken -o tsv)"
export SQL_SERVER="$CONN" SQL_DATABASE="$WAREHOUSE_NAME" SQL_FILE="medallion/sql/verify_silver.sql" SQL_ACCESS_TOKEN="$SQL_TOKEN"
python3 medallion/sql/run_sql.py
log "Verify complete."
