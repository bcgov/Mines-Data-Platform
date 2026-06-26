#!/usr/bin/env bash
set -euo pipefail

# Deploy + run nb_silver_registry only (rebuild object/field registry from the source catalog),
# then verify via the warehouse. Fast path — does NOT run the full silver build.
CLIENT_ID="${AZURE_CLIENT_ID:?}"; CLIENT_SECRET="${AZURE_CLIENT_SECRET:?}"; TENANT_ID="${AZURE_TENANT_ID:?}"
: "${WORKSPACE_ID:?}"; : "${WAREHOUSE_NAME:?}"

log() { echo "$@" >&2; }

az login --service-principal --username "$CLIENT_ID" --password "$CLIENT_SECRET" \
    --tenant "$TENANT_ID" --allow-no-subscriptions --output none
export FABRIC_TOKEN="$(az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken -o tsv)"

log "=== Files/raw contents (confirm the source catalog landed) ==="
BRONZE_LH_ID="8cd34a44-500a-47d9-aa2d-5ad0c2149858"
ST="$(az account get-access-token --resource https://storage.azure.com/ --query accessToken -o tsv)"
curl -s -H "Authorization: Bearer $ST" \
  "https://onelake.dfs.fabric.microsoft.com/${WORKSPACE_ID}?recursive=true&resource=filesystem&directory=${BRONZE_LH_ID}/Files/raw" \
  | jq -r '.paths[]? | .name' | sed "s#^${BRONZE_LH_ID}/Files/raw/##" | grep -iE "catalog|core_meta" >&2 || log "(no catalog files matched)"

log "=== Deploy + run nb_silver_registry ==="
NOTEBOOK_NAME="nb_silver_registry" NOTEBOOK_DIR="Fabric/Notebook/nb_silver_registry.Notebook" RUN="true" \
    python3 medallion/deploy/deploy_notebook.py

log "=== Verify registries (warehouse) ==="
WH_ID="$(curl -s -H "Authorization: Bearer $FABRIC_TOKEN" \
    "https://api.fabric.microsoft.com/v1/workspaces/$WORKSPACE_ID/warehouses" \
    | jq -r --arg n "$WAREHOUSE_NAME" '.value[]? | select(.displayName==$n) | .id')"
CONN="$(curl -s -H "Authorization: Bearer $FABRIC_TOKEN" \
    "https://api.fabric.microsoft.com/v1/workspaces/$WORKSPACE_ID/warehouses/$WH_ID" \
    | jq -r '.properties.connectionString // empty')"
[[ -z "$CONN" ]] && { log "no warehouse conn"; exit 1; }
SQL_TOKEN="$(az account get-access-token --resource https://database.windows.net/ --query accessToken -o tsv)"
export SQL_SERVER="$CONN" SQL_DATABASE="$WAREHOUSE_NAME" SQL_FILE="medallion/sql/verify_registry.sql" SQL_ACCESS_TOKEN="$SQL_TOKEN"
python3 medallion/sql/run_sql.py
log "Done."
