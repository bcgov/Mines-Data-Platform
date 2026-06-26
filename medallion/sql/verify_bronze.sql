-- Verify Bronze via the Bronze lakehouse SQL analytics endpoint.
SELECT COUNT(*) AS bronze_tables FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='bronze';
GO
-- Load summary (latest run): entities loaded/skipped/failed + files.
SELECT [status], COUNT(*) AS entities, SUM(CAST(files_loaded AS bigint)) AS files
FROM bronze.load_summary GROUP BY [status];
GO
-- Integrity: bronze.permit carries OUR audit columns and NOT the old bronze_load_ts.
SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA='bronze' AND TABLE_NAME='permit'
  AND COLUMN_NAME IN ('dl_load_ts','bronze_load_ts','bronze_file_name','bronze_file_timestamp','dl_rowhash');
GO
SELECT COUNT(*) AS permit_rows, COUNT(DISTINCT bronze_file_name) AS permit_files FROM bronze.permit;
GO
SELECT COUNT(*) AS manifest_files, COUNT(DISTINCT entity) AS manifest_entities FROM bronze.load_manifest;
GO
