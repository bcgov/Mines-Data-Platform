-- Did the materialized-stg build succeed end to end?
SELECT node_name, gold_object, status, rows, LEFT(detail,120) AS detail, run_ts
FROM app.gold_run_log ORDER BY run_ts DESC, node_name;
GO
-- runMultiple transform results from the latest run (proves the notebook-name->stg.<obj>
-- derivation ran under runMultiple); exception should be None.
SELECT TOP 4 entity, LEFT(error_message,200) AS transform_result, created_date
FROM app.error_log
WHERE layer='gold' AND entity LIKE 'runMultiple%'
ORDER BY created_date DESC;
GO
-- Any real gold errors in the last 15 min?
SELECT entity, target_table, LEFT(error_message,200) AS err, created_date
FROM app.error_log
WHERE layer='gold' AND entity NOT LIKE 'runMultiple%'
  AND created_date >= DATEADD(minute,-15,SYSUTCDATETIME())
ORDER BY created_date DESC;
GO
