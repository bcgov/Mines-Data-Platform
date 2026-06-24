# Medallion — Worklog & Findings (branch record)

> This file lives on branch `medallion/dev` as the durable record of *how we work*, what's deployed, and open issues — so the next person knows how to evolve it. Design/analysis docs are kept local under `docs/_local/` (gitignored) by project decision.

## Working model (decided 2026-06-23)

- **Build directly in the Fabric workspace** `mines-data-platform-fabricws-dev-1` (`8f380f88-5ce5-48d1-9fa5-fbbfbe2685a0`) via the **service principal** (GitHub Actions → Fabric REST), acting like a Fabric developer working in the workspace.
- **This branch (`medallion/dev`) stores the code + this worklog** — it is NOT git-synced into the workspace. We do **not** merge into the team's pipeline; the workspace → `feature/mines_dataplatform_dev` git commit (their existing flow) happens later, **from the Fabric side**, by the team.
- **Never use a `feature/**` branch** for our work — the team's `Fabric Deployment Pipeline` (`main.yml`) triggers on `feature/**` and auto-creates a per-feature workspace, which we cannot back with capacity. Use `medallion/**` (ignored by `main.yml`) and `chore/**` for ops.

## Why (constraints)

- **No capacity to assign** → we cannot use the ephemeral per-feature-workspace GitFlow; must use the one capacity-backed dev workspace.
- **Git→Fabric sync is painful right now** → deploy items directly via SPN/REST instead of relying on workspace git integration.

## Deployed so far

- ✅ Lakehouses (schema-enabled) in `8f380f88`, via `provision-medallion-lakehouses.yml` (SPN):
  - bronze `mines_data_platform_lh1` = `8cd34a44-500a-47d9-aa2d-5ad0c2149858`
  - silver `lh_silver` = `a0190e0e-c2f5-4740-ab90-a2f29b6e6991`
  - gold `lh_gold` = `5e43f78b-2156-4469-980e-bffda0295fac`

## To deploy (direct-to-workspace, via SPN)

- [x] `app.*` warehouse tables (object/field/transform registry, dq_rule, dq_result, error_log_bronze/silver/gold) → **DEPLOYED 2026-06-23** into warehouse `mines-data-platform-fabwh1` (id `9ed9a608-33e5-408b-bd51-adc2dad1e7ab`) via `deploy-app-tables.yml` + `medallion/sql/app_registry_tables.sql`. Verified: all 8 tables present.
- [x] `nb_util_paths`, `nb_smoke_foundation` notebooks → **DEPLOYED + SMOKE PASSED 2026-06-23** via Fabric Items API (`deploy-notebooks.yml`). nb_util_paths=`dda18b0c…`, nb_smoke_foundation=`52270d1d…`. Smoke job status=Completed → cross-lakehouse OneLake Delta write/read validated as the SPN.

## Deploy mechanism that works (reusable)

`deploy-app-tables.yml` (push on `medallion/**`) → `deploy_app_tables.sh`: SPN `az login` → Fabric REST resolves the warehouse by displayName → gets `.properties.connectionString` → acquires a `https://database.windows.net/` token → `medallion/sql/run_sql.py` (pyodbc, ODBC Driver 18, `SQL_COPT_SS_ACCESS_TOKEN`) executes the SQL split on `GO`. This is the template for any future direct-to-warehouse SQL.

## Findings (Fabric Warehouse T-SQL — verified empirically 2026-06-23)

- **F1:** Fabric Warehouse **rejects `IDENTITY`** in CREATE TABLE. Surrogate ids must be loader-populated.
- **F2:** Fabric Warehouse **rejects the `PRIMARY KEY`/constraint keyword in CREATE TABLE** (error 24584). No inline PK/UNIQUE/CHECK. (PK NOT ENFORCED, if ever needed, must go via `ALTER TABLE` and may still be unsupported in this edition.)
- **F3:** `sqlcmd -G` (ODBC) **cannot authenticate as a service principal** (defaults to ActiveDirectoryIntegrated → "authenticate the user ''"). Use **pyodbc + access-token** instead. The repo's `initialize/warehouse_init.sh` uses bare `-G` and would fail for SP — and its `Initialize Warehouse` workflow has never run.
- **F4:** Therefore the committed `*.Warehouse/app/Tables/*.sql` files (which use `bigint IDENTITY`) and `initialize/warehouse_init.sql` (IDENTITY/DEFAULT/CHECK/computed/PK) are **NOT deployable to this Fabric Warehouse as-is**. `medallion/sql/app_registry_tables.sql` is the deployable, Fabric-safe truth.
- **F5:** Our `app.*` tables were deployed into the **shared dev warehouse** `mines-data-platform-fabwh1` (alongside the team's existing `app` objects), per the direct-to-workspace working model.
- **F6:** Notebook deploy = Fabric Items API `POST /workspaces/{ws}/notebooks` (create) / `…/{id}/updateDefinition` (update), parts = `.platform` + `notebook-content.py` (InlineBase64, no `format` field) — works. Run = `POST /items/{id}/jobs/instances?jobType=RunNotebook` → poll `Location`. **A notebook run job needs a default lakehouse attached in its metadata** (`dependencies.lakehouse`) to run reliably; the first smoke (no lakehouse, `%run`, Tables-path write) failed with a generic `System_Cancelled_Session_Statements_Failed`. Robust pattern: attach a default lakehouse, write to an absolute `Files` OneLake path, avoid relying on `%run` for the critical assert. GUIDs are injected into the notebook source at deploy time.

## Open issues / findings

- **ISSUE-1:** Team `main.yml` has a stale `FABRIC_CONNECTION_ID` (`1c0b62c0-…`) → `ConnectionNotFound (HTTP 404)` on git-connect when it creates a feature workspace. Their bug to fix; we avoid it by not using `feature/**`.
- **ISSUE-2:** An orphan workspace `feat-feature-medallion_architecture` (`0c186e4e-…`) was auto-created by that pipeline on our first push; **deleted** via `fabric-ops-delete-workspace.yml` (HTTP 200).
- **NOTE:** `chore/**` push runs the ops delete workflow; `medallion/**` push triggers no team workflow (verified).
