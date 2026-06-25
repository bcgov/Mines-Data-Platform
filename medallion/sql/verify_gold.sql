-- Verify the gold build via the warehouse build log (reliable; no SQL-endpoint lag).
SELECT node_name, gold_object, status,
       CAST(rows AS bigint) AS rows,
       LEFT(CAST(detail AS varchar(4000)), 180) AS detail
FROM app.gold_run_log
ORDER BY node_name;
GO
