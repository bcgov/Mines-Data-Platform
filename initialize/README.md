# initialize/

One-time warehouse initialization scripts. Run after the Fabric Warehouse is provisioned by Terraform.

## What it creates

| Schema   | Layer     | Purpose                                              |
|----------|-----------|------------------------------------------------------|
| `bronze` | Raw       | Raw ingested data — no transformations               |
| `silver` | Cleansed  | Business rules applied, conformed types              |
| `gold`   | Curated   | Aggregates and star schema models for reporting      |
| `app`    | App       | Control objects — logging, config, orchestration     |

### App schema objects

| Object                   | Purpose                                                        |
|--------------------------|----------------------------------------------------------------|
| `app.pipeline_control`   | Orchestration config — what to load, how, and in what order   |
| `app.pipeline_log`       | Execution history — every run with row counts and duration     |
| `app.config`             | Key-value configuration store per environment                  |
| `app.error_log`          | Detailed error capture with context for debugging              |
| `app.schema_registry`    | Documents all schemas and their layer — governance reference   |

All scripts are **idempotent** — safe to re-run without side effects.

## Usage

### Prerequisites

```bash
# Install sqlcmd on the runner (ubuntu-latest already has azure-cli)
curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
  | sudo gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg
curl -fsSL https://packages.microsoft.com/config/ubuntu/22.04/prod.list \
  | sudo tee /etc/apt/sources.list.d/msprod.list
sudo apt-get update && sudo ACCEPT_EULA=Y apt-get install -y mssql-tools18 unixodbc-dev
```

### Run manually

```bash
export AZURE_CLIENT_ID="<your-client-id>"
export AZURE_CLIENT_SECRET="<your-client-secret>"
export AZURE_TENANT_ID="<your-tenant-id>"
export WORKSPACE_ID="<fabric-workspace-id>"
export WAREHOUSE_ID="<fabric-warehouse-id>"

chmod +x ./initialize/warehouse_init.sh
./initialize/warehouse_init.sh
```

### Run from GitHub Actions

Add a step to your workflow after the warehouse is provisioned:

```yaml
- name: Initialize Warehouse
  env:
    AZURE_CLIENT_ID:     ${{ secrets.AZURE_CLIENT_ID }}
    AZURE_CLIENT_SECRET: ${{ secrets.AZURE_CLIENT_SECRET }}
    AZURE_TENANT_ID:     ${{ secrets.AZURE_TENANT_ID }}
    WORKSPACE_ID:        ${{ vars.DEV_WORKSPACE_ID }}
    WAREHOUSE_ID:        ${{ vars.DEV_WAREHOUSE_ID }}
  run: |
    sudo ACCEPT_EULA=Y apt-get install -y mssql-tools18 unixodbc-dev -q
    chmod +x ./initialize/warehouse_init.sh
    ./initialize/warehouse_init.sh
```
