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

## Phase 2 — Bronze (2026-06-24)

- ✅ **`nb_bronze_load`** (append-only, idempotent-per-file, control columns `dl_load_id/bronze_file_name/bronze_file_timestamp/bronze_load_date/dl_load_ts/dl_rowhash`, partition by `bronze_load_date`) deployed + run via `deploy-run-bronze.yml` (notebook id `b7092009…`).
- ✅ **228 `bronze.*` tables populated from raw** — verified via the Bronze lakehouse SQL endpoint (`INFORMATION_SCHEMA.TABLES`). The raw landing in `Files/raw` is the **full MDS `public` schema** (incl. `etl_*`/`celery_*`/`tmp*` noise — filtered later in silver).
- 🔎 **Positive gap finding:** several gap-analysis tables flagged "not in raw" (G2–G5: `compliance_article`, `article_act_code`, status/code tables, etc.) ARE present in raw and now in bronze. Re-scope the gap doc: the main remaining hard gap is **G1 inspection targets** (NRIS-side; not in the `public` parquet). Confirm NRIS (`nris.*`) coverage separately — the bronze tables seen are all `public.*`.
- **F7:** The **lakehouse SQL analytics endpoint lags** newly-written Delta tables — a just-created table (`bronze.load_summary`) was not queryable within a 3-min retry window even though the 228 older tables were. Verify steps that read freshly-written lakehouse tables need a longer/again-later poll, or should query each table independently (don't fail the whole verify if one table hasn't synced). The Bronze load is confirmed by the table list regardless.

## Phase 3 — Silver (2026-06-24)

- ✅ `nb_silver_build` (standardize + cleanse + dedup-latest-per-PK + not-null DQ→quarantine + `silver.v_*` views) deployed + run via `deploy-run-silver.yml`. Silver LH default; reads Bronze cross-lakehouse via abfss.
- ✅ Working for 3 v1 entities → `silver.mine_incident`, `silver.permit`, `silver.permit_amendment` (+ `silver.load_summary`). 0 quarantined (PKs all non-null).
- 🔎 **GAP:** the conformed **`mine` hub is absent from bronze** — `public.mine` (and `mine_summary_view`) did NOT land in `Files/raw` (228 bronze tables, 60 mine-* tables, but no plain `mine`). Blocks `dim_mine`. Removed from V1; resolve with the raw-landing owner.
- **F8:** Fabric schema-enabled lakehouses do **NOT auto-create schemas** on `saveAsTable` (`SCHEMA_NOT_FOUND`) — must `CREATE SCHEMA IF NOT EXISTS` first. (Bronze worked only because its `bronze` schema pre-existed.)
- **F9 (verification):** notebook-job stdout is NOT retrievable via API, and lakehouse SQL endpoints **lag fresh tables** (even reads of a just-overwritten table can return a stale snapshot). Reliable readback = **OneLake DFS file listing** (`fabric-ops-list-tables`, exists-only) or the **warehouse** via synapsesql (no lag). Portal cell-output is the fastest way to see a notebook error.

## Error logging — unified (decision 2026-06-24)

Reshaped `app.error_log` into ONE Spark-shaped table for all phases, discriminated by a **`layer`** column (`bronze | silver | gold | ingest`): `error_id, layer, run_id, entity, target_table, error_message, error_context, stack_trace, created_date`. Dropped the per-phase `app.error_log_bronze/_silver/_gold`. Rationale (team feedback): `pipeline_log` already owns pipeline/run logging, so a single `error_log` + `layer` is cleaner than three tables, and the legacy ADF-shaped error_log (error_number/severity/procedure/line) didn't fit Spark errors. Reshape is idempotent (re-shapes only if the `pipeline_name` column is absent). Deployed via `deploy-app-tables.yml`. **2026-06-24:** added `log_id` + `pipeline_name` (nullable) for pipeline lineage — when a pipeline invokes the notebook we record the triggering pipeline + its `pipeline_log.log_id`; null for direct runs. Final cols: `error_id, layer, log_id, pipeline_name, run_id, entity, target_table, error_message, error_context, stack_trace, created_date`.

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
