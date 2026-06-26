-- Verify Bronze via the Bronze lakehouse SQL analytics endpoint.
SELECT COUNT(*) AS bronze_tables FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='bronze';
GO
-- Load summary (latest run): entities loaded/skipped/failed + files.
SELECT [status], COUNT(*) AS entities, SUM(CAST(files_loaded AS bigint)) AS files
FROM bronze.load_summary GROUP BY [status];
GO
-- Integrity: bronze.permit must carry OUR audit columns and NOT the old bronze_load_ts.
SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA='bronze' AND TABLE_NAME='permit'
  AND COLUMN_NAME IN ('dl_load_ts','bronze_load_ts','bronze_file_name','bronze_file_timestamp','dl_rowhash');
GO
-- Integrity: row count, distinct source files, and exact-duplicate rows (0 = clean, no concurrent double-load).
SELECT COUNT(*) AS rows,
       COUNT(DISTINCT bronze_file_name) AS source_files,
       COUNT(*) - COUNT(DISTINCT CONCAT(CAST(bronze_file_name AS varchar(200)),'|',CAST(dl_rowhash AS varchar(100)))) AS exact_dups
FROM bronze.permit;
GO
-- Manifest populated (one row per loaded file).
SELECT COUNT(*) AS manifest_files, COUNT(DISTINCT entity) AS manifest_entities FROM bronze.load_manifest;
GO
