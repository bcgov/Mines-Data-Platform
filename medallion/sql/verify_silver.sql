-- Registry population (auto-derived from pipeline_control + bronze schemas).
SELECT 'object_registry' AS tbl, COUNT(*) AS rows,
       SUM(CASE WHEN is_active=1 THEN 1 ELSE 0 END) AS active
FROM app.object_registry
UNION ALL SELECT 'field_registry', COUNT(*), NULL FROM app.field_registry;
GO
-- Silver build outcome per object (latest run).
SELECT status, COUNT(*) AS objects, SUM(silver_rows) AS silver_rows
FROM app.silver_run_log GROUP BY status ORDER BY status;
GO
-- Any failures this run?
SELECT TOP 30 entity, LEFT(CAST(error AS varchar(4000)), 200) AS error
FROM app.silver_run_log WHERE status='FAILED' ORDER BY entity;
GO
-- Centralized error log (warehouse), silver layer.
SELECT TOP 30 entity, target_table, LEFT(CAST(error_message AS varchar(4000)), 150) AS error_message, created_date
FROM app.error_log WHERE layer='silver' ORDER BY created_date DESC;
GO
