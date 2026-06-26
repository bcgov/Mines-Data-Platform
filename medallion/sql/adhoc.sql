-- Inactive objects (registered but skipped by silver build): operational or not-landed.
SELECT bronze_table, load_type, primary_key FROM app.object_registry WHERE is_active=0 ORDER BY bronze_table;
GO
-- Did the key gold-feeding tables build this run? (from app.silver_run_log)
SELECT entity, status, silver_rows, quarantined_rows
FROM app.silver_run_log
WHERE entity IN ('permit','permit_amendment','mine_incident','mine')
ORDER BY entity;
GO
-- Active objects by load_type.
SELECT load_type, COUNT(*) AS n FROM app.object_registry WHERE is_active=1 GROUP BY load_type;
GO
