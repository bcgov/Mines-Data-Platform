#!/usr/bin/env bash
set -euo pipefail

# Deploy the foundation notebooks into the workspace + run the smoke notebook, as the SPN.
CLIENT_ID="${AZURE_CLIENT_ID:?AZURE_CLIENT_ID is required}"
CLIENT_SECRET="${AZURE_CLIENT_SECRET:?AZURE_CLIENT_SECRET is required}"
TENANT_ID="${AZURE_TENANT_ID:?AZURE_TENANT_ID is required}"
: "${WORKSPACE_ID:?WORKSPACE_ID is required}"
: "${BRONZE_LH_ID:?BRONZE_LH_ID is required}"
: "${SILVER_LH_ID:?SILVER_LH_ID is required}"
: "${GOLD_LH_ID:?GOLD_LH_ID is required}"

echo "Logging into Azure via Service Principal..." >&2
az login --service-principal --username "$CLIENT_ID" --password "$CLIENT_SECRET" \
    --tenant "$TENANT_ID" --allow-no-subscriptions --output none
export FABRIC_TOKEN="$(az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken -o tsv)"

python3 medallion/deploy/deploy_notebooks.py
