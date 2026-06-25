-- Confirm app.error_log final column set (ordinal order) after restoring SQL TRY/CATCH fields.
SELECT c.column_id AS ord, c.name AS column_name, ty.name AS data_type, c.max_length, c.is_nullable
FROM sys.columns c
JOIN sys.tables t   ON c.object_id = t.object_id
JOIN sys.schemas s  ON t.schema_id = s.schema_id
JOIN sys.types ty   ON c.user_type_id = ty.user_type_id
WHERE s.name = 'app' AND t.name = 'error_log'
ORDER BY c.column_id;
GO
-- Existing rows preserved (additive ALTER, not drop+recreate)?
SELECT COUNT(*) AS error_log_rowcount FROM app.error_log;
GO
