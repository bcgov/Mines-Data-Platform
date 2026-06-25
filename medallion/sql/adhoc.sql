-- Verify the latest gold build: per-node status/rows, plus any gold errors in last 15 min.
SELECT node_name, gold_object, status, rows, run_ts, LEFT(detail,200) AS detail
FROM app.gold_run_log
ORDER BY run_ts DESC, node_name;
GO
SELECT entity, target_table, LEFT(error_message,300) AS error_message, created_date
FROM app.error_log
WHERE layer='gold' AND created_date >= DATEADD(minute, -15, SYSUTCDATETIME())
ORDER BY created_date DESC;
GO
