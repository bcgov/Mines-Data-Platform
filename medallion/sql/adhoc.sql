-- What connection metadata do we have to even reach the source?
SELECT config_key, LEFT(config_value,120) AS config_value, config_group, is_secret FROM app.config;
GO
-- Is the source connection string / KV populated in pipeline_control, or is it all via Key Vault?
SELECT
  COUNT(*) AS total,
  SUM(CASE WHEN source_connection_string IS NOT NULL THEN 1 ELSE 0 END) AS has_conn_str,
  SUM(CASE WHEN key_vault_url IS NOT NULL THEN 1 ELSE 0 END) AS has_kv,
  MAX(key_vault_url) AS sample_kv,
  MAX(source_system) AS sample_source_system
FROM app.pipeline_control;
GO
