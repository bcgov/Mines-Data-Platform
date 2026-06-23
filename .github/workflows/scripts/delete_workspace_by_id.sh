#!/usr/bin/env bash
set -euo pipefail

# Delete a Fabric workspace by ID, as the service principal. Ops utility.
CLIENT_ID="${AZURE_CLIENT_ID:?AZURE_CLIENT_ID is required}"
CLIENT_SECRET="${AZURE_CLIENT_SECRET:?AZURE_CLIENT_SECRET is required}"
TENANT_ID="${AZURE_TENANT_ID:?AZURE_TENANT_ID is required}"
WORKSPACE_ID="${WORKSPACE_ID:?WORKSPACE_ID is required}"

echo "Logging into Azure via Service Principal..." >&2
az login --service-principal --username "$CLIENT_ID" --password "$CLIENT_SECRET" \
    --tenant "$TENANT_ID" --allow-no-subscriptions --output none
TOKEN="$(az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken -o tsv)"

echo "Deleting workspace $WORKSPACE_ID ..." >&2
code="$(curl -s -o /dev/null -w '%{http_code}' -X DELETE \
    -H "Authorization: Bearer $TOKEN" \
    "https://api.fabric.microsoft.com/v1/workspaces/$WORKSPACE_ID")"
echo "DELETE /v1/workspaces/$WORKSPACE_ID -> HTTP $code" >&2

if [[ "$code" =~ ^2[0-9]{2}$ ]]; then
    echo "Deleted (or already absent)." >&2
    [[ -n "${GITHUB_STEP_SUMMARY:-}" ]] && echo "Deleted workspace \`$WORKSPACE_ID\` (HTTP $code)" >> "$GITHUB_STEP_SUMMARY"
else
    echo "Delete failed (HTTP $code)." >&2
    exit 1
fi
