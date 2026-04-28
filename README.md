# Fabric CD Repository

Fabric deployment pipeline managing workspaces, Git integration, variable libraries, and warehouse initialization across dev / test / prod environments.

## Repository structure

```
.
├── .github/
│   ├── CODEOWNERS
│   └── workflows/
│       ├── main.yml                      # Main deployment orchestrator
│       ├── create-fabric-workspace.yml   # Reusable: create workspace + git
│       ├── create-gitflow-pr.yml         # Reusable: create PR with auto-merge
│       ├── delete-workspace.yml          # Reusable: delete a workspace
│       ├── update-workspace-git.yml      # Reusable: sync workspace git state
│       ├── initialize-warehouse.yml      # Manual: initialize warehouse schemas
│       ├── scripts/
│       │   ├── spn_evaluator.sh          # Test SPN permissions
│       │   ├── create_workspace.sh       # Create workspace via Fabric API
│       │   ├── update_variables.sh       # Sync GitHub vars → Fabric variable library
│       │   ├── add_ws_admin.sh           # Add admin to workspace
│       │   └── delete_workspace.sh       # Delete workspace via Fabric API
│       └── setup/
│           └── setup.sh                  # Bootstrap repo secrets and variables
└── initialize/
    ├── README.md                          # Usage instructions
    ├── warehouse_init.sh                  # Run initialization script
    └── warehouse_init.sql                 # SQL: schemas + app control objects
```

## Deployment flow

```
feature/** push
    │
    ├─ 0. Validate SPN permissions
    ├─ 1. Create feature workspace
    ├─ 2. Update Dev variables
    ├─ 3. Deploy to Dev
    ├─ 4. Wait for approval
    ├─ 5. Update Test variables
    ├─ 6. Create PR feature → test  (manual merge)
    │
PR merged feature → test
    ├─ 7. Deploy to Test
    └─ 8. Create PR test → main    (manual merge)

PR merged test → main
    ├─ 9.  Update Prod variables
    └─ 10. Deploy to Production
```

## Required GitHub secrets

| Secret                | Description                        |
|-----------------------|------------------------------------|
| `AZURE_TENANT_ID`     | Entra tenant ID                    |
| `AZURE_CLIENT_ID`     | Service principal client ID        |
| `AZURE_CLIENT_SECRET` | Service principal secret           |
| `AZURE_CREDENTIALS`   | JSON credentials for azure/login   |
| `GH_PAT`              | GitHub PAT for variable operations |

## Required GitHub variables

| Variable              | Description                              |
|-----------------------|------------------------------------------|
| `DEV_CAPACITY_ID`     | Fabric capacity ID for dev               |
| `TEST_CAPACITY_ID`    | Fabric capacity ID for test              |
| `PROD_CAPACITY_ID`    | Fabric capacity ID for prod              |
| `DEV_WORKSPACE_ID`    | Fabric workspace ID for dev              |
| `TEST_WORKSPACE_ID`   | Fabric workspace ID for test             |
| `PROD_WORKSPACE_ID`   | Fabric workspace ID for prod             |
| `DEV_WAREHOUSE_ID`    | Fabric warehouse ID for dev              |
| `TEST_WAREHOUSE_ID`   | Fabric warehouse ID for test             |
| `PROD_WAREHOUSE_ID`   | Fabric warehouse ID for prod             |
| `FABRIC_CONNECTION_ID`| GitHub-Fabric configured connection ID  |
| `WORKSPACE_ADMIN_ID`  | Admin user object ID for workspaces      |

## Bootstrap

Run once to configure secrets and variables:

```bash
chmod +x .github/workflows/setup/setup.sh
.github/workflows/setup/setup.sh \
  --repo "owner/repo" \
  --tenant-id "<tenant-id>" \
  --client-id "<client-id>" \
  --client-secret "<client-secret>" \
  --dev-cap "<dev-capacity-id>" \
  --test-cap "<test-capacity-id>" \
  --prod-cap "<prod-capacity-id>" \
  --dev-ws "<dev-workspace-id>" \
  --test-ws "<test-workspace-id>" \
  --prod-ws "<prod-workspace-id>" \
  --fabric-conn "<fabric-connection-id>" \
  --admin-id "<admin-object-id>"
```

## Warehouse initialization

Run once per environment after the warehouse is provisioned by Terraform. Triggers manually from **Actions → Initialize Warehouse → Run workflow**.

Creates: `bronze`, `silver`, `gold`, `app` schemas and the following app control objects: `pipeline_control`, `pipeline_log`, `config`, `error_log`, `schema_registry`.

See [initialize/README.md](initialize/README.md) for details.
