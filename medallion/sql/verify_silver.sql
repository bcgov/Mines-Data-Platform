-- Verify the centralized error log (warehouse) received the silver notebook's failures.
-- Warehouse SQL endpoint has no sync lag, so this reads back immediately after the run.
SELECT layer, entity, target_table, error_code,
       LEFT(CAST(error_message AS varchar(4000)), 150) AS error_message,
       run_id, created_date
FROM app.error_log
WHERE layer = 'silver'
ORDER BY created_date DESC;
GO
