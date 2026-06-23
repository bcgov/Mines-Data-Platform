#!/usr/bin/env bash
set -euo pipefail

# Deploy the medallion app.* registry/DQ/error-log tables to the workspace warehouse,
# as the service principal. Resolves the warehouse by displayName for robustness.
# Reuses the proven SPN -> connection-string -> sqlcmd -G pattern from warehouse_init.sh.

CLIENT_ID="${AZURE_CLIENT_ID:?AZURE_CLIENT_ID is required}"
CLIENT_SECRET="${AZURE_CLIENT_SECRET:?AZURE_CLIENT_SECRET is required}"
TENANT_ID="${AZURE_TENANT_ID:?AZURE_TENANT_ID is required}"
WORKSPACE_ID="${WORKSPACE_ID:?WORKSPACE_ID is required}"
WAREHOUSE_NAME="${WAREHOUSE_NAME:?WAREHOUSE_NAME is required}"
SQL_FILE="${SQL_FILE:?SQL_FILE is required}"

log() { echo "$@" >&2; }

log "Logging into Azure via Service Principal..."
az login --service-principal --username "$CLIENT_ID" --password "$CLIENT_SECRET" \
    --tenant "$TENANT_ID" --allow-no-subscriptions --output none
TOKEN="$(az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken -o tsv)"

log "Resolving warehouse '$WAREHOUSE_NAME' in workspace $WORKSPACE_ID..."
WH_JSON="$(curl -s -H "Authorization: Bearer $TOKEN" \
    "https://api.fabric.microsoft.com/v1/workspaces/$WORKSPACE_ID/warehouses")"
WH_ID="$(echo "$WH_JSON" | jq -r --arg n "$WAREHOUSE_NAME" '.value[]? | select(.displayName==$n) | .id')"
if [[ -z "$WH_ID" || "$WH_ID" == "null" ]]; then
    log "Could not find warehouse '$WAREHOUSE_NAME'. Available:"; echo "$WH_JSON" | jq -r '.value[]?.displayName' >&2; exit 1
fi
log "Warehouse id: $WH_ID"

CONN="$(curl -s -H "Authorization: Bearer $TOKEN" \
    "https://api.fabric.microsoft.com/v1/workspaces/$WORKSPACE_ID/warehouses/$WH_ID" \
    | jq -r '.properties.connectionString // empty')"
if [[ -z "$CONN" ]]; then log "Could not resolve connection string."; exit 1; fi
log "Connection string: $CONN"

log "Acquiring SQL access token (resource: database.windows.net) for the SP..."
SQL_TOKEN="$(az account get-access-token --resource https://database.windows.net/ --query accessToken -o tsv)"
if [[ -z "$SQL_TOKEN" ]]; then log "Could not obtain SQL access token."; exit 1; fi

log "Running $SQL_FILE against $WAREHOUSE_NAME via pyodbc (SP access-token auth)..."
# sqlcmd -G cannot do service-principal auth; use pyodbc + ODBC access-token attribute.
export SQL_SERVER="$CONN" SQL_DATABASE="$WAREHOUSE_NAME" SQL_FILE="$SQL_FILE" SQL_ACCESS_TOKEN="$SQL_TOKEN"
python3 "${SQL_RUNNER:-medallion/sql/run_sql.py}"
log "SQL executed successfully."
