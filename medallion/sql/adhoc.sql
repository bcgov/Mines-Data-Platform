-- Proof: the gold orchestrator's synapsesql append still works against the 17-col table.
-- It writes runMultiple_* info rows via log_error on every run; confirm fresh ones landed
-- and that the new SQL TRY/CATCH columns are present (null from notebooks) on those rows.
SELECT TOP 10 entity, layer, target_table,
       error_number, error_severity, error_state, error_procedure, error_line,
       created_date
FROM app.error_log
WHERE created_date >= DATEADD(minute, -15, SYSUTCDATETIME())
ORDER BY created_date DESC;
GO
SELECT COUNT(*) AS rows_written_last_15min
FROM app.error_log
WHERE created_date >= DATEADD(minute, -15, SYSUTCDATETIME());
GO
