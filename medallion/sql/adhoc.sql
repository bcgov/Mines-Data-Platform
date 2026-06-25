-- Confirm the type2_full dim path ran clean (delete handling, 0 deletes this run).
SELECT node_name, gold_object, status, rows, LEFT(detail,120) AS detail, run_ts
FROM app.gold_run_log ORDER BY run_ts DESC, node_name;
GO
SELECT entity, target_table, LEFT(error_message,200) AS err, created_date
FROM app.error_log
WHERE layer='gold' AND entity NOT LIKE 'runMultiple%'
  AND created_date >= DATEADD(minute,-20,SYSUTCDATETIME())
ORDER BY created_date DESC;
GO
