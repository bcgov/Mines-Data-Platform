#!/usr/bin/env bash
set -euo pipefail

# ══════════════════════════════════════════════════════════════
# Provision schema-enabled Fabric lakehouses (idempotent) as the
# CI service principal. Mirrors the auth pattern in create_workspace.sh.
# ══════════════════════════════════════════════════════════════

CLIENT_ID="${AZURE_CLIENT_ID:?AZURE_CLIENT_ID is required}"
CLIENT_SECRET="${AZURE_CLIENT_SECRET:?AZURE_CLIENT_SECRET is required}"
TENANT_ID="${AZURE_TENANT_ID:?AZURE_TENANT_ID is required}"
WORKSPACE_ID="${WORKSPACE_ID:?WORKSPACE_ID is required}"
LAKEHOUSES="${LAKEHOUSES:-lh_silver lh_gold}"
BRONZE_LH_ID="${BRONZE_LH_ID:-}"

API="https://api.fabric.microsoft.com/v1"
log() { echo "$@" >&2; }

authenticate_azure() {
    log "Logging into Azure via Service Principal..."
    az login --service-principal \
        --username "$CLIENT_ID" \
        --password "$CLIENT_SECRET" \
        --tenant "$TENANT_ID" \
        --allow-no-subscriptions \
        --output none
}

get_fabric_token() {
    az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken -o tsv
}

# Resolve a lakehouse id by displayName (empty if not found). Fabric returns {"value":[...]}.
lh_id_by_name() {
    local token="$1" name="$2"
    curl -s -H "Authorization: Bearer $token" \
        "$API/workspaces/$WORKSPACE_ID/lakehouses" \
        | jq -r --arg n "$name" '.value[]? | select(.displayName == $n) | .id' | head -n1
}

authenticate_azure
TOKEN="$(get_fabric_token)"

declare -A IDS

for name in $LAKEHOUSES; do
    existing="$(lh_id_by_name "$TOKEN" "$name" || true)"
    if [[ -n "$existing" && "$existing" != "null" ]]; then
        log "Reusing lakehouse '$name' ($existing)"
        IDS[$name]="$existing"
        continue
    fi

    log "Creating schema-enabled lakehouse '$name'..."
    resp="$(curl -s -w $'\n%{http_code}' -X POST "$API/workspaces/$WORKSPACE_ID/lakehouses" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"displayName\":\"$name\",\"description\":\"Medallion $name\",\"creationPayload\":{\"enableSchemas\":true}}")"
    code="$(printf '%s' "$resp" | tail -n1)"
    body="$(printf '%s' "$resp" | sed '$d')"

    new_id=""
    if [[ "$code" == "200" || "$code" == "201" ]]; then
        new_id="$(printf '%s' "$body" | jq -r '.id // empty')"
    elif [[ "$code" == "202" ]]; then
        log "Accepted (HTTP 202, async create). Polling for '$name'..."
    else
        log "Failed to create '$name' (HTTP $code):"
        log "$body"
        exit 1
    fi

    if [[ -z "$new_id" ]]; then
        for _ in $(seq 1 10); do
            sleep 5
            new_id="$(lh_id_by_name "$TOKEN" "$name" || true)"
            [[ -n "$new_id" && "$new_id" != "null" ]] && break
            new_id=""
        done
    fi

    if [[ -z "$new_id" ]]; then
        log "Could not resolve id for '$name' after polling"
        exit 1
    fi
    log "Created '$name' ($new_id)"
    IDS[$name]="$new_id"
done

# ── Outputs + job summary ──────────────────────────────────────
if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
    {
        echo "### Medallion lakehouses provisioned"
        echo ""
        echo "| Lakehouse | Lakehouse ID | Workspace ID |"
        echo "| --- | --- | --- |"
    } >> "$GITHUB_STEP_SUMMARY"
fi

for name in $LAKEHOUSES; do
    id="${IDS[$name]:-}"
    [[ -n "${GITHUB_OUTPUT:-}" ]] && echo "${name}_id=${id}" >> "$GITHUB_OUTPUT"
    [[ -n "${GITHUB_STEP_SUMMARY:-}" ]] && echo "| $name | $id | $WORKSPACE_ID |" >> "$GITHUB_STEP_SUMMARY"
done

# ── Print FABRIC_LAKEHOUSE_MAPPING JSON to stdout (for the path registry) ──
# Maps lh_silver -> silver_lakehouse, lh_gold -> gold_lakehouse; bronze only if BRONZE_LH_ID set.
jq -n \
    --arg ws "$WORKSPACE_ID" \
    --arg silver "${IDS[lh_silver]:-}" \
    --arg gold "${IDS[lh_gold]:-}" \
    --arg bronze "$BRONZE_LH_ID" '
    {
        silver_lakehouse: { workspace_id: $ws, lakehouse_id: $silver },
        gold_lakehouse:   { workspace_id: $ws, lakehouse_id: $gold }
    }
    + ( if $bronze != "" then { bronze_lakehouse: { workspace_id: $ws, lakehouse_id: $bronze } } else {} end )
'
