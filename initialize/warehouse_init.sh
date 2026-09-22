#!/bin/bash
# =============================================================================
# initialize/warehouse_init.sh
# Initializes a Fabric Warehouse with medallion schemas and app control objects
# Uses pyodbc with ActiveDirectoryServicePrincipal — the proven working pattern
# for service principal SQL connections to Fabric Warehouse
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
    command -v python3 &>/dev/null || missing+=("python3")

    if [[ ${#missing[@]} -gt 0 ]]; then
        echo -e "${RED}[✗]${NC} Missing required tools: ${missing[*]}"
        exit 1
    fi

    # Check ODBC driver
    if ! odbcinst -q -d -n "ODBC Driver 18 for SQL Server" &>/dev/null; then
        echo -e "${RED}[✗]${NC} Missing: ODBC Driver 18 for SQL Server"
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
    token=$(az account get-access-token \
        --resource https://api.fabric.microsoft.com \
        --query accessToken \
        -o tsv)

    if [[ -z "$token" ]]; then
        echo -e "${RED}[✗]${NC} Failed to obtain Fabric access token" >&2
        exit 1
    fi

    echo "::add-mask::${token}" >&2
    echo -e "${GREEN}[✓]${NC} Fabric token obtained" >&2
    echo "$token"
}

# ══════════════════════════════════════════════════════════════
# Bootstrap Fabric security token for SP
# Required before any SQL connection — without this first API call
# the SP has no Fabric security token and SQL connections will fail
# ══════════════════════════════════════════════════════════════

bootstrap_fabric_token() {
    local token="$1"

    echo -e "${BLUE}[INFO]${NC} Bootstrapping Fabric security token for SP..." >&2

    local url="https://api.fabric.microsoft.com/v1/workspaces/${WORKSPACE_ID}/warehouses/${WAREHOUSE_ID}"
    local http_code response body

    response=$(curl -s -w "\n%{http_code}" \
        -H "Authorization: Bearer ${token}" \
        -H "Content-Type: application/json" \
        "$url")

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    if [[ "$http_code" != "200" ]]; then
        echo -e "${RED}[✗]${NC} Bootstrap API call failed (HTTP ${http_code})" >&2
        echo "$body" | jq . 2>/dev/null || echo "$body" >&2
        exit 1
    fi

    local conn_string warehouse_name
    conn_string=$(echo "$body" | jq -r '
        .properties.connectionString //
        .properties.connection_string //
        .connectionString //
        .connection_string //
        empty
    ')
    warehouse_name=$(echo "$body" | jq -r '.displayName // empty')

    if [[ -z "$conn_string" || -z "$warehouse_name" ]]; then
        echo -e "${RED}[✗]${NC} Could not resolve warehouse details" >&2
        echo "$body" | jq '.properties // .' 2>/dev/null >&2
        exit 1
    fi

    echo -e "${GREEN}[✓]${NC} Fabric token bootstrapped" >&2
    echo -e "${GREEN}[✓]${NC} Server   : ${conn_string}" >&2
    echo -e "${GREEN}[✓]${NC} Database : ${warehouse_name}" >&2

    echo "${conn_string}"$'\t'"${warehouse_name}"
}

# ══════════════════════════════════════════════════════════════
# Execute SQL via pyodbc with ActiveDirectoryServicePrincipal
# This is the proven working pattern for SP SQL connections
# to Fabric Warehouse — sqlcmd does not work reliably with SPs
# ══════════════════════════════════════════════════════════════

run_sql_init() {
    local server="$1"
    local database="$2"

    if [[ ! -f "$SQL_FILE" ]]; then
        echo -e "${RED}[✗]${NC} SQL file not found: ${SQL_FILE}"
        exit 1
    fi

    echo ""
    echo -e "${BOLD}Installing pyodbc and running warehouse_init.sql...${NC}"
    echo "─────────────────────────────────────────────────────────────────"

    pip install pyodbc --quiet --break-system-packages

    python3 << PYEOF
import pyodbc
import sys
import os

server   = "${server}"
database = "${database}"
client_id     = os.environ["AZURE_CLIENT_ID"]
client_secret = os.environ["AZURE_CLIENT_SECRET"]

conn_str = (
    "Driver={ODBC Driver 18 for SQL Server};"
    f"Server={server},1433;"
    f"Database={database};"
    "Encrypt=Yes;"
    "TrustServerCertificate=No;"
    "Authentication=ActiveDirectoryServicePrincipal;"
    f"UID={client_id};"
    f"PWD={client_secret};"
)

print(f"[INFO] Connecting to {server} / {database}")

try:
    conn = pyodbc.connect(conn_str, timeout=30)
    conn.autocommit = True
    cursor = conn.cursor()
    print("[✓] Connected successfully")
except Exception as e:
    print(f"[✗] Connection failed: {e}", file=sys.stderr)
    sys.exit(1)

# Read and split SQL file on GO batch separators
with open("${SQL_FILE}", "r") as f:
    sql_content = f.read()

import re
batches = [b.strip() for b in re.split(r'^\s*GO\s*$', sql_content, flags=re.MULTILINE | re.IGNORECASE)]
batches = [b for b in batches if b]  # remove empty

print(f"[INFO] Executing {len(batches)} SQL batches...")

for i, batch in enumerate(batches, 1):
    # Skip comment-only batches
    stripped = re.sub(r'--[^\n]*', '', batch).strip()
    if not stripped:
        continue
    try:
        cursor.execute(batch)
        print(f"[✓] Batch {i}/{len(batches)} OK")
    except pyodbc.Error as e:
        # 2714 = object already exists — safe to ignore (idempotent)
        if "2714" in str(e) or "already exists" in str(e).lower():
            print(f"[~] Batch {i}/{len(batches)} skipped (already exists)")
        else:
            print(f"[✗] Batch {i}/{len(batches)} FAILED: {e}", file=sys.stderr)
            sys.exit(1)

cursor.close()
conn.close()
print("[✓] All batches executed successfully")
PYEOF

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
    details=$(bootstrap_fabric_token "$fabric_token")
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