#!/bin/bash
# =============================================================================
# initialize/warehouse_init.sh
# Initializes a Fabric Warehouse with medallion schemas and app control objects
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

WORKSPACE_ID="${WORKSPACE_ID:?WORKSPACE_ID is required}"
WAREHOUSE_ID="${WAREHOUSE_ID:?WAREHOUSE_ID is required}"
CLIENT_ID="${AZURE_CLIENT_ID:?AZURE_CLIENT_ID is required}"
CLIENT_SECRET="${AZURE_CLIENT_SECRET:?AZURE_CLIENT_SECRET is required}"
TENANT_ID="${AZURE_TENANT_ID:?AZURE_TENANT_ID is required}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQL_FILE="${SCRIPT_DIR}/warehouse_init.sql"

echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════════════════════╗"
echo "║             Fabric Warehouse Initializer                          ║"
echo "║             Schemas: bronze | silver | gold | app                 ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${BLUE}[INFO]${NC} Workspace ID : ${WORKSPACE_ID}"
echo -e "${BLUE}[INFO]${NC} Warehouse ID : ${WAREHOUSE_ID}"
echo -e "${BLUE}[INFO]${NC} SQL Script   : ${SQL_FILE}"

# ══════════════════════════════════════════════════════════════
# Validate dependencies
# ══════════════════════════════════════════════════════════════

check_dependencies() {
    local missing=()
    command -v az      &>/dev/null || missing+=("azure-cli")
    command -v curl    &>/dev/null || missing+=("curl")
    command -v jq      &>/dev/null || missing+=("jq")
    command -v sqlcmd  &>/dev/null || missing+=("sqlcmd (mssql-tools18)")

    if [[ ${#missing[@]} -gt 0 ]]; then
        echo -e "${RED}[✗]${NC} Missing required tools: ${missing[*]}"
        exit 1
    fi
    echo -e "${GREEN}[✓]${NC} All dependencies present"
}

# ══════════════════════════════════════════════════════════════
# Authentication
# ══════════════════════════════════════════════════════════════

authenticate_azure() {
    echo -e "${BLUE}[INFO]${NC} Logging into Azure via Service Principal..."
    az login --service-principal \
        --username "$CLIENT_ID" \
        --password "$CLIENT_SECRET" \
        --tenant "$TENANT_ID" \
        --allow-no-subscriptions \
        --output none
    echo -e "${GREEN}[✓]${NC} Azure login successful"
}

get_fabric_token() {
    echo -e "${BLUE}[INFO]${NC} Fetching Fabric access token..." >&2
    local token
    token=$(az account get-access-token         --resource https://api.fabric.microsoft.com         --query accessToken         -o tsv)

    if [[ -z "$token" ]]; then
        echo -e "${RED}[✗]${NC} Failed to obtain Fabric access token" >&2
        exit 1
    fi

    # Mask token from logs
    echo "::add-mask::${token}" >&2
    echo -e "${GREEN}[✓]${NC} Fabric token obtained" >&2
    echo "$token"
}

# ══════════════════════════════════════════════════════════════
# Resolve warehouse name and connection string via Fabric REST API
# ══════════════════════════════════════════════════════════════

get_warehouse_details() {
    local token="$1"

    echo -e "${BLUE}[INFO]${NC} Resolving warehouse details..." >&2

    local url="https://api.fabric.microsoft.com/v1/workspaces/${WORKSPACE_ID}/warehouses/${WAREHOUSE_ID}"
    echo -e "${BLUE}[INFO]${NC} GET ${url}" >&2

    local http_code response body
    response=$(curl -s -w "\n%{http_code}" \
        -H "Authorization: Bearer ${token}" \
        -H "Content-Type: application/json" \
        "$url")

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    echo -e "${BLUE}[INFO]${NC} HTTP status: ${http_code}" >&2

    if [[ "$http_code" != "200" ]]; then
        echo -e "${RED}[✗]${NC} API call failed (HTTP ${http_code})" >&2
        echo "$body" | jq . 2>/dev/null || echo "$body" >&2
        exit 1
    fi

    # Extract connection string — try both camelCase and snake_case
    local conn_string
    conn_string=$(echo "$body" | jq -r '
        .properties.connectionString //
        .properties.connection_string //
        .connectionString //
        .connection_string //
        empty
    ')

    # Extract warehouse display name for the -d flag
    local warehouse_name
    warehouse_name=$(echo "$body" | jq -r '.displayName // empty')

    if [[ -z "$conn_string" || "$conn_string" == "null" ]]; then
        echo -e "${RED}[✗]${NC} Could not find connection string in response." >&2
        echo "$body" | jq '.properties // .' 2>/dev/null >&2
        exit 1
    fi

    if [[ -z "$warehouse_name" || "$warehouse_name" == "null" ]]; then
        echo -e "${RED}[✗]${NC} Could not find warehouse display name in response." >&2
        exit 1
    fi

    echo -e "${GREEN}[✓]${NC} Server   : ${conn_string}" >&2
    echo -e "${GREEN}[✓]${NC} Database : ${warehouse_name}" >&2

    # Return both as tab-separated values
    echo "${conn_string}"$'\t'"${warehouse_name}"
}

# ══════════════════════════════════════════════════════════════
# Execute SQL initialization script
# ══════════════════════════════════════════════════════════════

run_sql_init() {
    local server="$1"
    local database="$2"

    if [[ ! -f "$SQL_FILE" ]]; then
        echo -e "${RED}[✗]${NC} SQL file not found: ${SQL_FILE}"
        exit 1
    fi

    echo ""
    echo -e "${BOLD}Running warehouse_init.sql...${NC}"
    echo "─────────────────────────────────────────────────────────────────"

    # go-sqlcmd ActiveDirectoryServicePrincipal auth:
    # -U must be in the form <client_id>@<tenant_id>
    # SQLCMDPASSWORD must be set to the client secret
    # --authentication-method ActiveDirectoryServicePrincipal
    SQLCMDPASSWORD="$CLIENT_SECRET" sqlcmd \
        -S "${server},1433" \
        -d "$database" \
        -U "${CLIENT_ID}@${TENANT_ID}" \
        --authentication-method ActiveDirectoryServicePrincipal \
        -C \
        -i "$SQL_FILE"

    echo "─────────────────────────────────────────────────────────────────"
    echo -e "${GREEN}[✓]${NC} SQL script executed successfully"
}

# ══════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════

main() {
    check_dependencies
    authenticate_azure

    local fabric_token
    fabric_token=$(get_fabric_token)

    local details server database
    details=$(get_warehouse_details "$fabric_token")
    server=$(echo "$details" | cut -f1)
    database=$(echo "$details" | cut -f2)

    run_sql_init "$server" "$database"

    echo ""
    echo -e "${GREEN}${BOLD}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}${BOLD}  Warehouse initialization complete!                           ${NC}"
    echo -e "${GREEN}${BOLD}  Schemas created: bronze | silver | gold | app               ${NC}"
    echo -e "${GREEN}${BOLD}  App objects:     pipeline_control | pipeline_log | config    ${NC}"
    echo -e "${GREEN}${BOLD}                  error_log | schema_registry                 ${NC}"
    echo -e "${GREEN}${BOLD}══════════════════════════════════════════════════════════════${NC}"
}

main "$@"