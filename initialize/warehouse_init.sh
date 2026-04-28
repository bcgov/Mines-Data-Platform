#!/bin/bash
# =============================================================================
# initialize/warehouse_init.sh
# Initializes a Fabric Warehouse with medallion schemas and app control objects
# Follows the same auth pattern as create_workspace.sh
# =============================================================================

set -euo pipefail

# ══════════════════════════════════════════════════════════════
# Colors
# ══════════════════════════════════════════════════════════════

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

# ══════════════════════════════════════════════════════════════
# Configuration & Validation
# ══════════════════════════════════════════════════════════════

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
        echo ""
        echo "Install sqlcmd on Ubuntu:"
        echo "  curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | sudo gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg"
        echo "  curl -fsSL https://packages.microsoft.com/config/ubuntu/22.04/prod.list | sudo tee /etc/apt/sources.list.d/msprod.list"
        echo "  sudo apt-get update && sudo ACCEPT_EULA=Y apt-get install -y mssql-tools18 unixodbc-dev"
        exit 1
    fi

    echo -e "${GREEN}[✓]${NC} All dependencies present"
}

# ══════════════════════════════════════════════════════════════
# Authentication — identical pattern to create_workspace.sh
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
    echo -e "${BLUE}[INFO]${NC} Fetching Fabric access token..."
    az account get-access-token \
        --resource https://api.fabric.microsoft.com \
        --query accessToken \
        -o tsv
}

# ══════════════════════════════════════════════════════════════
# Resolve warehouse connection string via Fabric REST API
# ══════════════════════════════════════════════════════════════

get_connection_string() {
    local token="$1"

    echo -e "${BLUE}[INFO]${NC} Resolving warehouse connection string..." >&2

    local response
    response=$(curl -s \
        -H "Authorization: Bearer ${token}" \
        "https://api.fabric.microsoft.com/v1/workspaces/${WORKSPACE_ID}/warehouses/${WAREHOUSE_ID}")

    local conn_string
    conn_string=$(echo "$response" | jq -r '.properties.connectionString // empty')

    if [[ -z "$conn_string" || "$conn_string" == "null" ]]; then
        echo -e "${RED}[✗]${NC} Could not resolve connection string. Response:" >&2
        echo "$response" >&2
        exit 1
    fi

    echo -e "${GREEN}[✓]${NC} Connection string: ${conn_string}" >&2
    echo "$conn_string"
}

# ══════════════════════════════════════════════════════════════
# Execute SQL initialization script
# ══════════════════════════════════════════════════════════════

run_sql_init() {
    local conn_string="$1"

    if [[ ! -f "$SQL_FILE" ]]; then
        echo -e "${RED}[✗]${NC} SQL file not found: ${SQL_FILE}"
        exit 1
    fi

    echo ""
    echo -e "${BOLD}Running warehouse_init.sql...${NC}"
    echo "─────────────────────────────────────────────────────────────────"

    # -G  = Azure AD authentication (uses the SP credentials from az login)
    # -C  = trust server certificate
    # -b  = exit on first error
    # -i  = input file
    sqlcmd \
        -S "$conn_string" \
        -G \
        -C \
        -b \
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

    local conn_string
    conn_string=$(get_connection_string "$fabric_token")

    run_sql_init "$conn_string"

    echo ""
    echo -e "${GREEN}${BOLD}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}${BOLD}  Warehouse initialization complete!                           ${NC}"
    echo -e "${GREEN}${BOLD}  Schemas created: bronze | silver | gold | app               ${NC}"
    echo -e "${GREEN}${BOLD}  App objects:     pipeline_control | pipeline_log | config    ${NC}"
    echo -e "${GREEN}${BOLD}                  error_log | schema_registry                 ${NC}"
    echo -e "${GREEN}${BOLD}══════════════════════════════════════════════════════════════${NC}"
}

main "$@"
