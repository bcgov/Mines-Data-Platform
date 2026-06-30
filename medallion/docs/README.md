# Mines Data Platform — Onboarding Docs

Start here, in order:

1. **[`01-ELT-FRAMEWORK-design-and-runbook.md`](01-ELT-FRAMEWORK-design-and-runbook.md)** — how the medallion ELT platform is built and how to operate it (technical design + runbook). Covers the environment/access model, the control-plane tables, every layer (source extraction → bronze → registry → silver → gold DAG builder), the deploy/run mechanism, the runbook (how to run each stage, add a table/dim/fact, troubleshoot), testing, and the improvement roadmap.

2. **[`02-SOURCE-DATA-and-GOLD-MODEL.md`](02-SOURCE-DATA-and-GOLD-MODEL.md)** — what we know about the MDS source `public` schema, the proposed star schema, exactly which source table(s) feed each dimension/fact, the rationale, and how to validate the design.

3. **[`03-DEMO-gold-dag.md`](03-DEMO-gold-dag.md)** — demo asset: a metadata-driven multi-level gold DAG (parallel roots, a join-based dimension, SCD1/SCD2, fact upsert/append, multi-parent fan-in) proving the framework's technical capability. Includes the DAG diagram and a live-demo script. Business logic is intentionally artificial.

Then read **[`../WORKLOG.md`](../WORKLOG.md)** — the chronological build log: every decision, the empirically-discovered Fabric constraints (findings F1–F12+), and what was deployed when. It is the authoritative running record.

Deeper background (local, gitignored — ask the team for access if not present): `docs/_local/` holds the original design spec, the legacy Power-BI/MDP-DWH logic inventory + migration plan, and the raw-gap analysis.

> **Most important open item:** the `mine` hub (and ~29 other business tables) are configured in `pipeline_control` but have **not landed in bronze** — they're registered inactive and auto-activate once landed. `dim_mine` and most facts are blocked on this. See doc 02 §7.
