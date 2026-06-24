-- Verify Silver build via the Silver lakehouse SQL analytics endpoint.
SELECT TABLE_SCHEMA, TABLE_NAME
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA IN ('silver', 'quarantine')
ORDER BY TABLE_SCHEMA, TABLE_NAME;
GO

SELECT entity, status,
       CAST(bronze_rows AS bigint)      AS bronze_rows,
       CAST(silver_rows AS bigint)      AS silver_rows,
       CAST(quarantined_rows AS bigint) AS quarantined_rows
FROM silver.load_summary
ORDER BY entity;
GO
