-- Columns of the team's ingestion tables.
SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, ORDINAL_POSITION
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA='app' AND TABLE_NAME IN ('pipeline_control','schema_registry','config','pipeline_log')
ORDER BY TABLE_NAME, ORDINAL_POSITION;
GO
-- Row counts.
SELECT 'pipeline_control' AS tbl, COUNT(*) AS rows FROM app.pipeline_control
UNION ALL SELECT 'schema_registry', COUNT(*) FROM app.schema_registry
UNION ALL SELECT 'config', COUNT(*) FROM app.config
UNION ALL SELECT 'pipeline_log', COUNT(*) FROM app.pipeline_log;
GO
-- Samples.
SELECT TOP 8 * FROM app.pipeline_control;
GO
SELECT TOP 8 * FROM app.schema_registry;
GO
