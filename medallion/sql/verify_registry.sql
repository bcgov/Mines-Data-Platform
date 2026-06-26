-- Registry now sourced from the pg_catalog dump (true PKs + all columns + unlanded tables).
SELECT 'object_registry' AS tbl, COUNT(*) AS rows, SUM(CASE WHEN is_active=1 THEN 1 ELSE 0 END) AS active
FROM app.object_registry
UNION ALL SELECT 'field_registry', COUNT(*), NULL FROM app.field_registry;
GO
-- True composite PKs (the thing bronze introspection / pipeline_control could not give).
SELECT TOP 12 bronze_table, primary_key FROM app.object_registry WHERE primary_key LIKE '%,%' ORDER BY bronze_table;
GO
-- Key tables incl. the previously-unlanded 'mine' hub — now registered with its true PK.
SELECT bronze_table, primary_key, load_type, is_active
FROM app.object_registry
WHERE bronze_table IN ('mine','permit','permit_amendment','mine_incident','bond_permit_xref')
ORDER BY bronze_table;
GO
-- Field sample for 'mine'.
SELECT TOP 15 entity, column_name, spark_type, nullable, is_pk, ordinal
FROM app.field_registry WHERE entity='mine' ORDER BY ordinal;
GO
