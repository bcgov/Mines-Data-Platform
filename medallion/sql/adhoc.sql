-- Config: table_type + new load_strategy column.
SELECT node_name, object_type, table_type, load_strategy, business_keys, is_active
FROM app.gold_build ORDER BY node_name;
GO
-- Build results: dim_permit (type2/full), fact_permit_amendment (upsert/full).
SELECT node_name, gold_object, status, rows, LEFT(detail,120) AS detail, run_ts
FROM app.gold_run_log ORDER BY run_ts DESC, node_name;
GO
-- Any real gold errors in the last 15 min?
SELECT entity, target_table, LEFT(error_message,200) AS err, created_date
FROM app.error_log
WHERE layer='gold' AND entity NOT LIKE 'runMultiple%'
  AND created_date >= DATEADD(minute,-15,SYSUTCDATETIME())
ORDER BY created_date DESC;
GO
