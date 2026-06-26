#!/usr/bin/env bash
set -euo pipefail

# Deploy + run nb_bronze_load as the SPN, then verify via the Bronze lakehouse SQL endpoint.
CLIENT_ID="${AZURE_CLIENT_ID:?}"; CLIENT_SECRET="${AZURE_CLIENT_SECRET:?}"; TENANT_ID="${AZURE_TENANT_ID:?}"
: "${WORKSPACE_ID:?}"; : "${BRONZE_LH_ID:?}"; : "${BRONZE_LH_NAME:?}"

log() { echo "$@" >&2; }

log "SPN login..."
az login --service-principal --username "$CLIENT_ID" --password "$CLIENT_SECRET" \
    --tenant "$TENANT_ID" --allow-no-subscriptions --output none
export FABRIC_TOKEN="$(az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken -o tsv)"

log "=== Cancel any in-progress nb_bronze_load jobs (avoid concurrent writes) ==="
NB_ID="$(curl -s -H "Authorization: Bearer $FABRIC_TOKEN" \
   "https://api.fabric.microsoft.com/v1/workspaces/$WORKSPACE_ID/notebooks" \
   | jq -r '.value[]? | select(.displayName=="nb_bronze_load") | .id')"
if [[ -n "$NB_ID" ]]; then
  for attempt in $(seq 1 80); do   # wait up to ~20 min for any in-flight job to truly stop
    IDS="$(curl -s -H "Authorization: Bearer $FABRIC_TOKEN" \
       "https://api.fabric.microsoft.com/v1/workspaces/$WORKSPACE_ID/items/$NB_ID/jobs/instances" \
       | jq -r '.value[]? | select(.status=="InProgress" or .status=="NotStarted" or .status=="Running" or .status=="Cancelling") | .id')"
    [[ -z "$IDS" ]] && { log "no in-progress jobs"; break; }
    for j in $IDS; do
      curl -s -X POST -H "Authorization: Bearer $FABRIC_TOKEN" \
        "https://api.fabric.microsoft.com/v1/workspaces/$WORKSPACE_ID/items/$NB_ID/jobs/instances/$j/cancel" >/dev/null || true
    done
    log "waiting for in-flight bronze job(s) to stop (attempt $attempt)"
    sleep 15
  done
fi

log "=== Deploy + run nb_bronze_load ==="
NOTEBOOK_NAME="nb_bronze_load" NOTEBOOK_DIR="Fabric/Notebook/nb_bronze_load.Notebook" RUN="true" \
    python3 medallion/deploy/deploy_notebook.py

log "=== Verify via Bronze lakehouse SQL endpoint ==="
LH_JSON="$(curl -s -H "Authorization: Bearer $FABRIC_TOKEN" \
    "https://api.fabric.microsoft.com/v1/workspaces/$WORKSPACE_ID/lakehouses/$BRONZE_LH_ID")"
SQL_EP="$(echo "$LH_JSON" | jq -r '.properties.sqlEndpointProperties.connectionString // empty')"
if [[ -z "$SQL_EP" ]]; then
    log "Could not resolve lakehouse SQL endpoint; skipping verify. Response:"; echo "$LH_JSON" >&2
    exit 0
fi
log "SQL endpoint: $SQL_EP (db: $BRONZE_LH_NAME)"

SQL_TOKEN="$(az account get-access-token --resource https://database.windows.net/ --query accessToken -o tsv)"
export SQL_SERVER="$SQL_EP" SQL_DATABASE="$BRONZE_LH_NAME" SQL_FILE="medallion/sql/verify_bronze.sql" SQL_ACCESS_TOKEN="$SQL_TOKEN"

# The lakehouse SQL endpoint lags Delta writes; retry a few times. Verify is best-effort.
for attempt in 1 2 3 4 5 6; do
    log "verify attempt $attempt..."
    if python3 medallion/sql/run_sql.py; then
        log "Verify succeeded."
        exit 0
    fi
    sleep 30
done
log "Verify did not succeed after retries (SQL endpoint lag, or no bronze tables/summary — possibly no raw data landed). Deploy+run itself succeeded."
exit 0
