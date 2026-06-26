-- Registry population (auto-derived from source pg_catalog).
SELECT 'object_registry' AS tbl, COUNT(*) AS rows,
       SUM(CASE WHEN is_active=1 THEN 1 ELSE 0 END) AS active
FROM app.object_registry
UNION ALL SELECT 'field_registry', COUNT(*), NULL FROM app.field_registry;
GO
-- Silver build outcome per object (latest run): full vs incremental vs no-change.
SELECT detail, COUNT(*) AS objects, SUM(silver_rows) AS silver_rows, SUM(rows_in) AS rows_in
FROM app.silver_run_log GROUP BY detail ORDER BY objects DESC;
GO
SELECT status, COUNT(*) AS objects FROM app.silver_run_log GROUP BY status;
GO
-- Cursor state (per-entity high-water mark) — top movers.
SELECT TOP 10 entity, last_dl_load_ts, last_run_id, updated_date
FROM app.silver_load_state ORDER BY last_dl_load_ts DESC;
GO
-- Any failures this run?
SELECT TOP 30 entity, LEFT(CAST(detail AS varchar(4000)), 200) AS detail
FROM app.silver_run_log WHERE status='FAILED' ORDER BY entity;
GO
