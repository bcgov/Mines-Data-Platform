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

## Phase 4 — Gold (DAG-driven dim/fact builder) (2026-06-25)

- ✅ **End-to-end validated.** DAG-driven gold builder runs the full medallion tail: silver→stg transform→merge→gold.
- **Config-driven DAG:** `app.gold_build_dag` (one row per gold object: `object_type DIM/FACT`, `scd_type`, `fact_type`, `surrogate_key`, `business_keys`, `non_historized_columns`, `watermark_column`, `last_n_days`, `transform_notebook`, `source_view`, `depends_on`, `load_order`, `is_active`). Seeded: `dim_permit` (SCD2, NK `permit_id`) → `fact_permit_amendment` (`fact_type 1`, `depends_on dim_permit`).
- **Orchestrator** `nb_gold_orchestrator`: reads the DAG via synapsesql, computes **Kahn topological levels** (independent nodes share a level → run in parallel), per level runs the transform notebooks via `mssparkutils.notebook.runMultiple` (creates `stg.v_*` views from silver), then the orchestrator **does the merge** by calling the builder utility. Writes per-node results to `app.gold_run_log` and failures to `app.error_log` (layer=`gold`).
- **Builder utility** `nb_util_gold` (`%run` into orchestrator): `build_dimension(...)` (SCD1/2, surrogate keys via `row_number()+max_sk` — no IDENTITY) and `build_fact(...)` (type-1 full rebuild / type-2 rolling-`last_n_days`, grain test). Wheel path kept open.
- **Transform notebooks** `nb_gold_tf_dim_permit`, `nb_gold_tf_fact_permit_amendment` (gold LH default): build `stg.v_*` from silver via abfss; fact joins `gold.dim_permit` for `Permit_SK`.
- **Validation run (RUN 2026-06-25 03:50):** L0 `dim_permit` → `gold.dim_permit` OK `no-change` (SCD2 idempotent, 8610 rows from prior); L1 `fact_permit_amendment` → `gold.fact_permit_amendment` OK **24,750 rows** `rebuilt`. Both `runMultiple` transforms returned `exception: None`; correct DAG ordering; no gold errors.
- **2026-06-25 — split gold config into two tables + table_type enum.** `app.gold_build_dag` is gone, replaced by **`app.gold_build`** (one row per gold object: node_name, gold_object, object_type, transform_notebook, `source_table` [renamed from source_view], `table_type`, surrogate_key, business_keys, non_historized_columns, watermark_column, last_n_days, is_active) and **`app.gold_dependency`** (node_name + `depends_on` comma-list of parent node_names; chosen over an edge table for input ease — builder splits the CSV, so an edge table is a trivial swap later). `scd_type`+`fact_type` collapsed into one **`table_type`** enum the builder dispatches on: `type1_dimension` / `type2_dimension` → `build_dimension(scd 1|2)`; `append_only_fact` (insert new business keys only) / `upsert_fact` (MERGE update+insert) / `reload_fact` (full drop+rebuild, deletes vanished rows) → rewritten `build_fact(mode=...)`. `load_order` dropped (topological order + node_name sort suffices). Orchestrator reads both tables, builds Kahn levels from gold_dependency, dispatches on table_type. **Verified live:** dim_permit (type2_dimension) OK no-change; fact_permit_amendment (reload_fact) OK 24,750 rows action=`reloaded`; runMultiple L0→L1 correct order, exception None.
- **2026-06-25 — stg materialized as TABLES + standard transform template.** Transforms now write a real `stg.<object>` Delta table (drop + full overwrite each run) instead of a `CREATE OR REPLACE VIEW`; the orchestrator merges from that table. `nb_gold_tf_dim_permit` is the canonical **5-cell template** (1 imports+Spark props, 2 derive target + register sources, 3 drop stg table, 4 SparkSQL business logic→df, 5 write df→table); `nb_gold_tf_fact_permit_amendment` follows it (adds the `gold.dim_permit` join). **Naming convention:** a notebook `nb_gold_tf_<object>` targets `stg.<object>`, derived at runtime from `mssparkutils.runtime.context['currentNotebookName']` — **verified working under `runMultiple`** (both transforms returned `exception: None`; merges produced dim_permit OK / fact 24,750 rebuilt). DAG `source_view` repointed `stg.v_*`→`stg.*` (seed + idempotent UPDATE). Drop-each-run handles build-to-build schema drift.
- **F11:** Fabric `%run` magic **cannot share a cell with any other code or comment** (`MagicUsageError`). The `%run nb_util_gold` cell must be alone — even a leading comment breaks it (also retroactively explains the first gold smoke failure).
- **F12:** Source has **pre-1900 timestamps** (e.g. `permit_amendment`) → Spark Parquet write fails `INCONSISTENT_BEHAVIOR_CROSS_VERSION.WRITE_ANCIENT_DATETIME`. Fix: set `spark.sql.parquet.{datetime,int96}RebaseModeInWrite/Read = LEGACY` in **both** `nb_silver_build` and `nb_gold_orchestrator`. Diagnosed via the ad-hoc warehouse SQL runner (`fabric-ops-adhoc-sql.yml`) reading the full stack trace from `app.error_log`.

## Centralized error logging framework (2026-06-24)

Goal (client): ONE queryable error table for pipeline AND notebook errors. Delivered:
- **(1)** `app.error_log` is the centralized error store. Final shape: `error_id (GUID varchar36), layer, log_id, pipeline_name, run_id, entity, target_table, error_message, error_code, error_context, stack_trace, created_date`. `error_id` is a writer-minted GUID (no IDENTITY in Fabric); `error_code` holds ADF's code (null for notebooks). `pipeline_log` stays the run-history table; join `error_log.run_id = pipeline_log.run_id` for context.
- **(2)** Notebooks write failures to `app.error_log` via the **synapsesql** connector — `nb_silver_build.log_error(...)` (warehouse attached in metadata). **Validated**: a run captured `mine` + `permit_amendment` failures as rows. The same `log_error()` helper drops into the Gold notebook (Phase 4).
- **(3)** ADF hand-off drafted: `medallion/handoff/adf-error-log-change.md` — one `NonQuery` INSERT into `app.error_log` (`layer='ingest'`) added to the existing `Log_Failure` activity. (User applies.)
- **F10:** the warehouse-write method needs `from com.microsoft.spark.fabric import Constants` to register `DataFrameWriter.synapsesql` — without it the write silently no-ops (caught).
- **Anomaly captured:** `permit_amendment` had a Spark `saveAsTable` stage failure ("Task failed 4×") on the latest run though it built in earlier runs — looks transient; now visible in `app.error_log` rather than lost. Re-run to confirm; dig if it recurs.

## Error logging — unified (decision 2026-06-24)

Reshaped `app.error_log` into ONE Spark-shaped table for all phases, discriminated by a **`layer`** column (`bronze | silver | gold | ingest`): `error_id, layer, run_id, entity, target_table, error_message, error_context, stack_trace, created_date`. Dropped the per-phase `app.error_log_bronze/_silver/_gold`. Rationale (team feedback): `pipeline_log` already owns pipeline/run logging, so a single `error_log` + `layer` is cleaner than three tables, and the legacy ADF-shaped error_log (error_number/severity/procedure/line) didn't fit Spark errors. Reshape is idempotent (re-shapes only if the `pipeline_name` column is absent). Deployed via `deploy-app-tables.yml`. **2026-06-24:** added `log_id` + `pipeline_name` (nullable) for pipeline lineage — when a pipeline invokes the notebook we record the triggering pipeline + its `pipeline_log.log_id`; null for direct runs. Final cols: `error_id, layer, log_id, pipeline_name, run_id, entity, target_table, error_message, error_context, stack_trace, created_date`.

**2026-06-25 — restored the SQL TRY/CATCH columns.** The legacy columns dropped at unification turned out to be needed by *other* (non-medallion, SQL-based) processes that write into this shared table. Added back `error_number, error_severity, error_state, error_procedure, error_line` (the `ERROR_NUMBER()`/`ERROR_SEVERITY()`/… `CATCH`-block fields). Notebooks don't populate them (always null). Migration is **non-destructive**: `app_registry_tables.sql` now (1) drops only the pre-unification shape (no `error_code`), (2) `ALTER TABLE ADD`s the five cols when the current unified shape lacks them, (3) `CREATE`s the full shape on fresh deploy. ALTER appends at the end, so the cols are **trailing** (after `created_date`) — the CREATE DDL and both notebook `log_error` helpers were reordered to emit that same physical order, so the synapsesql append aligns by name AND position. **Verified:** `sys.columns` shows all 17 cols (ord 13–17 the new ones); existing rows preserved (rowcount unchanged through the ALTER); a live gold run's `log_error` info rows appended cleanly to the 17-col table with the new cols null. Final cols: `error_id, layer, log_id, pipeline_name, run_id, entity, target_table, error_message, error_code, error_context, stack_trace, created_date, error_number, error_severity, error_state, error_procedure, error_line`.

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
