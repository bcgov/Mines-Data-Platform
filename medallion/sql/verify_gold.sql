-- Verify the gold build via the warehouse (reliable; no SQL-endpoint lag).
SELECT node_name, gold_object, status,
       CAST(rows AS bigint) AS rows,
       LEFT(CAST(detail AS varchar(4000)), 180) AS detail
FROM app.gold_run_log
ORDER BY node_name;
GO

-- Gold-layer diagnostics (incl. captured runMultiple transform results).
SELECT entity, LEFT(CAST(error_message AS varchar(8000)), 600) AS error_message, created_date
FROM app.error_log
WHERE layer = 'gold'
ORDER BY created_date DESC;
GO
