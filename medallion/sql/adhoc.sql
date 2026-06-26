-- Did entities fail this run, and why? (errors land in app.error_log, layer='silver')
SELECT COUNT(*) AS silver_errors_30min
FROM app.error_log
WHERE layer='silver' AND created_date >= DATEADD(minute,-40,SYSUTCDATETIME());
GO
SELECT TOP 5 entity, LEFT(CAST(error_message AS varchar(4000)), 400) AS error_message, created_date
FROM app.error_log
WHERE layer='silver' AND created_date >= DATEADD(minute,-40,SYSUTCDATETIME())
ORDER BY created_date DESC;
GO
