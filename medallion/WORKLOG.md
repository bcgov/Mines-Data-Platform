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

- [ ] `app.*` warehouse tables (object/field/transform registry, dq_rule, dq_result, error_log_bronze/silver/gold) → into warehouse `mines-data-platform-fabwh1` (reuse the repo's `initialize-warehouse` SPN→SQL pattern).
- [ ] `nb_util_paths`, `nb_smoke_foundation` notebooks → via Fabric Items API; run smoke to validate cross-lakehouse path resolution + Delta I/O.
- [ ] Verify Fabric Warehouse accepts `IDENTITY` on the `app.*` tables (the one compatibility risk).

## Open issues / findings

- **ISSUE-1:** Team `main.yml` has a stale `FABRIC_CONNECTION_ID` (`1c0b62c0-…`) → `ConnectionNotFound (HTTP 404)` on git-connect when it creates a feature workspace. Their bug to fix; we avoid it by not using `feature/**`.
- **ISSUE-2:** An orphan workspace `feat-feature-medallion_architecture` (`0c186e4e-…`) was auto-created by that pipeline on our first push; **deleted** via `fabric-ops-delete-workspace.yml` (HTTP 200).
- **NOTE:** `chore/**` push runs the ops delete workflow; `medallion/**` push triggers no team workflow (verified).
