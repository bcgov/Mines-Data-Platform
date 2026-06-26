-- Force a full silver pass (bronze rebuilt with dl_load_ts; old bronze_load_ts cursor is stale).
UPDATE app.silver_settings SET force_full_all = 1, updated_date = SYSUTCDATETIME();
GO
DELETE FROM app.silver_load_state;
GO
SELECT force_full_all FROM app.silver_settings;
GO
