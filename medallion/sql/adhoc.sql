-- Noise check: how many pipeline_control entries look like operational/system tables?
SELECT 'noise_like' AS bucket, COUNT(*) AS n FROM app.pipeline_control
WHERE source_entity LIKE '%django_%' OR source_entity LIKE '%celery_%' OR source_entity LIKE '%auth_%'
   OR source_entity LIKE '%etl_%' OR source_entity LIKE '%spatial_ref%' OR source_entity LIKE '%tmp%'
   OR source_entity LIKE '%_version' OR source_entity LIKE '%_code'
UNION ALL SELECT 'total_active', COUNT(*) FROM app.pipeline_control WHERE is_active=1
UNION ALL SELECT 'total', COUNT(*) FROM app.pipeline_control
UNION ALL SELECT 'null_pk', COUNT(*) FROM app.pipeline_control WHERE primary_key IS NULL OR primary_key=''
UNION ALL SELECT 'composite_pk(has comma)', COUNT(*) FROM app.pipeline_control WHERE primary_key LIKE '%,%';
GO
-- Spread of target tables (first 60 alphabetically) to eyeball noise.
SELECT TOP 60 target_table, primary_key, load_type, is_active
FROM app.pipeline_control ORDER BY target_table;
GO
