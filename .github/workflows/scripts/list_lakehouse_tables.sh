#!/usr/bin/env bash
set -euo pipefail

# List Delta tables in a lakehouse directly via the OneLake DFS (ADLS Gen2) API,
# as the SPN. Bypasses the lakehouse SQL-endpoint sync lag entirely — confirms what
# Delta table folders actually exist under <lakehouse>/Tables/<schema>/<table>.
CLIENT_ID="${AZURE_CLIENT_ID:?}"; CLIENT_SECRET="${AZURE_CLIENT_SECRET:?}"; TENANT_ID="${AZURE_TENANT_ID:?}"
: "${WORKSPACE_ID:?}"; : "${LAKEHOUSE_ID:?}"

log() { echo "$@" >&2; }

az login --service-principal --username "$CLIENT_ID" --password "$CLIENT_SECRET" \
    --tenant "$TENANT_ID" --allow-no-subscriptions --output none
TOKEN="$(az account get-access-token --resource https://storage.azure.com/ --query accessToken -o tsv)"

URL="https://onelake.dfs.fabric.microsoft.com/${WORKSPACE_ID}?recursive=true&resource=filesystem&directory=${LAKEHOUSE_ID}/Tables"
log "Listing ${LAKEHOUSE_ID}/Tables ..."
RESP="$(curl -s -H "Authorization: Bearer $TOKEN" "$URL")"

# Directory entries two levels under Tables/ are the tables: Tables/<schema>/<table>
echo "$RESP" | jq -r '.paths[]? | select(.isDirectory=="true") | .name' \
    | sed "s#^${LAKEHOUSE_ID}/Tables/##" \
    | awk -F/ 'NF==2 {print $1"."$2}' | sort -u | tee /dev/stderr \
    | { count=$(wc -l); log "=== ${count} tables ==="; }
