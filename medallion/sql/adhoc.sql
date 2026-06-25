-- gold_build_dag gone? gold_build + gold_dependency present and seeded?
SELECT t.name AS table_name
FROM sys.tables t JOIN sys.schemas s ON t.schema_id=s.schema_id
WHERE s.name='app' AND t.name IN ('gold_build_dag','gold_build','gold_dependency')
ORDER BY t.name;
GO
SELECT node_name, gold_object, object_type, transform_notebook, source_table, table_type,
       surrogate_key, business_keys, is_active
FROM app.gold_build ORDER BY node_name;
GO
SELECT node_name, depends_on FROM app.gold_dependency ORDER BY node_name;
GO
