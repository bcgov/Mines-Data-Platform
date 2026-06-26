SELECT COUNT(*) AS silver_errors_30min FROM app.error_log
WHERE layer='silver' AND created_date >= DATEADD(minute,-30,SYSUTCDATETIME());
GO
SELECT TOP 3 entity, LEFT(CAST(error_message AS varchar(4000)),350) AS err, created_date
FROM app.error_log WHERE layer='silver' AND created_date >= DATEADD(minute,-30,SYSUTCDATETIME())
ORDER BY created_date DESC;
GO
