-- True PKs + active flag for candidate demo tables.
SELECT bronze_table, primary_key, load_type, is_active FROM app.object_registry
WHERE bronze_table IN ('party','permit','permit_amendment','mine_party_appt','mine_incident',
  'now_application_identity','bond','bond_permit_xref','mine_status','mine_type') ORDER BY bronze_table;
GO
-- Small active reference tables = good type1 dimension candidates.
SELECT TOP 15 entity, silver_rows FROM app.silver_run_log
WHERE status='OK' AND silver_rows BETWEEN 3 AND 400 ORDER BY silver_rows DESC;
GO
-- Confirm join/key columns exist.
SELECT entity, column_name FROM app.field_registry
WHERE (entity='permit_amendment' AND column_name IN ('permit_id','permit_amendment_id'))
   OR (entity='party' AND column_name LIKE '%guid%')
   OR (entity='mine_party_appt' AND column_name IN ('party_guid','mine_guid','mine_party_appt_id'))
ORDER BY entity, column_name;
GO
