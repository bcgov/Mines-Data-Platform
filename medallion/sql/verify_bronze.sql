-- Verify Bronze load via the Bronze lakehouse SQL analytics endpoint.
-- Lists bronze tables and summarizes the latest load run.
SELECT TABLE_SCHEMA, TABLE_NAME
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = 'bronze'
ORDER BY TABLE_NAME;
GO

SELECT [status], COUNT(*) AS file_count, SUM(CAST([rows] AS bigint)) AS total_rows
FROM bronze.load_summary
GROUP BY [status];
GO
