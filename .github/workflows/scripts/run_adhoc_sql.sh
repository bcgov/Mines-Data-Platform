#!/usr/bin/env bash
set -euo pipefail

# Run medallion/sql/adhoc.sql against the workspace warehouse as the SPN. Reusable ad-hoc
# query tool (read error_log stack traces, inspect app.* tables, etc.) without re-running notebooks.
CLIENT_ID="${AZURE_CLIENT_ID:?}"; CLIENT_SECRET="${AZURE_CLIENT_SECRET:?}"; TENANT_ID="${AZURE_TENANT_ID:?}"
: "${WORKSPACE_ID:?}"; : "${WAREHOUSE_NAME:?}"

log() { echo "$@" >&2; }

az login --service-principal --username "$CLIENT_ID" --password "$CLIENT_SECRET" \
    --tenant "$TENANT_ID" --allow-no-subscriptions --output none
TOKEN="$(az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken -o tsv)"
WH_ID="$(curl -s -H "Authorization: Bearer $TOKEN" \
    "https://api.fabric.microsoft.com/v1/workspaces/$WORKSPACE_ID/warehouses" \
    | jq -r --arg n "$WAREHOUSE_NAME" '.value[]? | select(.displayName==$n) | .id')"
CONN="$(curl -s -H "Authorization: Bearer $TOKEN" \
    "https://api.fabric.microsoft.com/v1/workspaces/$WORKSPACE_ID/warehouses/$WH_ID" \
    | jq -r '.properties.connectionString // empty')"
[[ -z "$CONN" ]] && { log "no warehouse conn"; exit 1; }

SQL_TOKEN="$(az account get-access-token --resource https://database.windows.net/ --query accessToken -o tsv)"
export SQL_SERVER="$CONN" SQL_DATABASE="$WAREHOUSE_NAME" SQL_FILE="medallion/sql/adhoc.sql" SQL_ACCESS_TOKEN="$SQL_TOKEN"
python3 medallion/sql/run_sql.py
