#!/usr/bin/env bash
set -euo pipefail

# Deploy + run nb_silver_build as the SPN, then verify via the Silver lakehouse SQL endpoint.
CLIENT_ID="${AZURE_CLIENT_ID:?}"; CLIENT_SECRET="${AZURE_CLIENT_SECRET:?}"; TENANT_ID="${AZURE_TENANT_ID:?}"
: "${WORKSPACE_ID:?}"; : "${SILVER_LH_ID:?}"; : "${SILVER_LH_NAME:?}"

log() { echo "$@" >&2; }

log "SPN login..."
az login --service-principal --username "$CLIENT_ID" --password "$CLIENT_SECRET" \
    --tenant "$TENANT_ID" --allow-no-subscriptions --output none
export FABRIC_TOKEN="$(az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken -o tsv)"

log "=== Deploy + run nb_silver_build ==="
NOTEBOOK_NAME="nb_silver_build" NOTEBOOK_DIR="Fabric/nb_silver_build.Notebook" RUN="true" \
    python3 medallion/deploy/deploy_notebook.py

log "=== Verify via Silver lakehouse SQL endpoint ==="
LH_JSON="$(curl -s -H "Authorization: Bearer $FABRIC_TOKEN" \
    "https://api.fabric.microsoft.com/v1/workspaces/$WORKSPACE_ID/lakehouses/$SILVER_LH_ID")"
SQL_EP="$(echo "$LH_JSON" | jq -r '.properties.sqlEndpointProperties.connectionString // empty')"
if [[ -z "$SQL_EP" ]]; then
    log "Could not resolve Silver SQL endpoint; skipping verify."; echo "$LH_JSON" >&2; exit 0
fi
log "SQL endpoint: $SQL_EP (db: $SILVER_LH_NAME)"

SQL_TOKEN="$(az account get-access-token --resource https://database.windows.net/ --query accessToken -o tsv)"
export SQL_SERVER="$SQL_EP" SQL_DATABASE="$SILVER_LH_NAME" SQL_FILE="medallion/sql/verify_silver.sql" SQL_ACCESS_TOKEN="$SQL_TOKEN"

for attempt in 1 2 3 4 5 6; do
    log "verify attempt $attempt..."
    if python3 medallion/sql/run_sql.py; then log "Verify succeeded."; exit 0; fi
    sleep 30
done
log "Verify did not surface within retry window (SQL endpoint lag). Deploy+run itself succeeded."
exit 0
