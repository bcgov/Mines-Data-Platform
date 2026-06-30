-- Confirm PKs + active flag for the demo gold objects: type2 dim (party), type1 dim
-- (a small reference table), and the join-based dim (permit_amendment + permit).
SELECT bronze_table, primary_key, load_type, is_active, schema_name
FROM app.object_registry
WHERE bronze_table IN ('party','permit','permit_amendment','municipality','project',
  'variance','equipment','party_business_role_appt','minespace_user')
ORDER BY bronze_table;
GO
-- Verify the join + business-key columns actually exist in silver field_registry.
SELECT entity, column_name FROM app.field_registry
WHERE (entity='party'             AND column_name IN ('party_guid','party_type_code','first_name','party_name','email'))
   OR (entity='permit'            AND column_name IN ('permit_id','permit_no','mine_guid'))
   OR (entity='permit_amendment'  AND column_name IN ('permit_amendment_id','permit_id','permit_amendment_status_code'))
ORDER BY entity, column_name;
GO
