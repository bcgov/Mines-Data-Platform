#!/usr/bin/env bash
set -euo pipefail

# Summarize bronze Files/raw via OneLake DFS (as SPN). Answers: does raw retain full history,
# and what do the file names look like (does nb_bronze_load's yyyymmdd_hhmmss regex match)?
CLIENT_ID="${AZURE_CLIENT_ID:?}"; CLIENT_SECRET="${AZURE_CLIENT_SECRET:?}"; TENANT_ID="${AZURE_TENANT_ID:?}"
: "${WORKSPACE_ID:?}"
BRONZE_LH_ID="8cd34a44-500a-47d9-aa2d-5ad0c2149858"

log() { echo "$@" >&2; }
az login --service-principal --username "$CLIENT_ID" --password "$CLIENT_SECRET" \
    --tenant "$TENANT_ID" --allow-no-subscriptions --output none
ST="$(az account get-access-token --resource https://storage.azure.com/ --query accessToken -o tsv)"
H="Authorization: Bearer $ST"
BASE="https://onelake.dfs.fabric.microsoft.com/${WORKSPACE_ID}"

log "=== top-level entities under Files/raw ==="
ENT="$(curl -s -H "$H" "${BASE}?recursive=false&resource=filesystem&directory=${BRONZE_LH_ID}/Files/raw" \
  | jq -r '.paths[]?.name' | sed "s#^${BRONZE_LH_ID}/Files/raw/##")"
log "entity folders: $(echo "$ENT" | grep -c . )"
echo "$ENT" | head -20 >&2

log ""
log "=== full recursive listing for known data entities (paths + count) ==="
for e in public.permit public.mine_incident public.address_type_code; do
  ALLP="$(curl -s -H "$H" "${BASE}?recursive=true&resource=filesystem&directory=${BRONZE_LH_ID}/Files/raw/${e}" \
    | jq -r '.paths[]?.name' | sed "s#^${BRONZE_LH_ID}/Files/raw/${e}/##")"
  N="$(echo "$ALLP" | grep -c . || true)"
  log "--- ${e}: ${N} total paths (any type) ---"
  echo "$ALLP" | sort | head -25 >&2
done
