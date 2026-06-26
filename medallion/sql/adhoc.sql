-- What app.* tables exist (incl. team's ADF ingestion control tables)?
SELECT s.name AS sch, t.name AS tbl
FROM sys.tables t JOIN sys.schemas s ON t.schema_id=s.schema_id
WHERE s.name='app' ORDER BY t.name;
GO
-- Are the registries populated?
SELECT 'object_registry' AS tbl, COUNT(*) AS rows FROM app.object_registry
UNION ALL SELECT 'field_registry', COUNT(*) FROM app.field_registry;
GO
-- Sample object_registry (if any)
SELECT TOP 10 object_id, source_entity, bronze_schema, bronze_table, silver_schema, silver_table,
       load_type, primary_key, is_active FROM app.object_registry ORDER BY object_id;
GO
