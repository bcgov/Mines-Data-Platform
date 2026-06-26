-- Drop the stale-schema silver_run_log so the next incremental run recreates it fresh.
DROP TABLE IF EXISTS app.silver_run_log;
GO
-- Confirm run1 (full) populated the cursor (proves all entities processed + watermarked).
SELECT COUNT(*) AS cursor_entities, MIN(last_dl_load_ts) AS min_ts, MAX(last_dl_load_ts) AS max_ts
FROM app.silver_load_state;
GO
SELECT TOP 6 entity, last_dl_load_ts FROM app.silver_load_state ORDER BY entity;
GO
