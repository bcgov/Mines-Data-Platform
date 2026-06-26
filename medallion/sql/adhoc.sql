-- Where are the silver rows? Top tables by count.
SELECT TOP 12 entity, silver_rows FROM app.silver_run_log ORDER BY silver_rows DESC;
GO
SELECT status, COUNT(*) AS objects, SUM(silver_rows) AS total_rows FROM app.silver_run_log GROUP BY status;
GO
-- Active object set by load_type (was 210, now 214).
SELECT load_type, COUNT(*) AS n FROM app.object_registry WHERE is_active=1 GROUP BY load_type;
GO
