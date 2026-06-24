-- Verify Silver via the run log written to the Bronze lakehouse (Bronze SQL endpoint
-- syncs fast). First query discovers the real bronze table name(s) for 'mine'.
SELECT TABLE_NAME
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = 'bronze' AND TABLE_NAME LIKE '%mine%'
ORDER BY TABLE_NAME;
GO

SELECT entity, status,
       CAST(bronze_rows AS bigint)      AS bronze_rows,
       CAST(silver_rows AS bigint)      AS silver_rows,
       CAST(quarantined_rows AS bigint) AS quarantined_rows,
       LEFT(CAST(error AS varchar(4000)), 200) AS error
FROM bronze.silver_run_log
ORDER BY entity;
GO
