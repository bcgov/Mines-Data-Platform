resource "azurerm_key_vault" "kv" {
  name                        = "kv-${var.projectNameAbbr}-${var.environment}-${var.locationAbbr}"
  location                    = azurerm_resource_group.security.location
  resource_group_name         = azurerm_resource_group.security.name
  enabled_for_disk_encryption = true
  tenant_id                   = var.tenant_id
  soft_delete_retention_days  = 7
  enabled_for_deployment      = true
  purge_protection_enabled    = false


  network_acls {
    default_action = "Deny"
    bypass         = "AzureServices"
    // For local development below, please remove ip_rules when appropriate
    # ip_rules = ["${chomp(data.http.myip.response_body)}/32"]
    ip_rules = []
  }

  sku_name = "standard"

  # access_policy {
  #   tenant_id = var.tenant_id
  #   object_id = var.

  #   key_permissions = [
  #     "Get",
  #   ]

  #   secret_permissions = [
  #     "Get",
  #   ]

  #   storage_permissions = [
  #     "Get",
  #   ]
  # }
}

resource "azurerm_monitor_diagnostic_setting" "kv-diag" {
  name                       = "diag-${var.projectNameAbbr}-${var.environment}-${var.locationAbbr}"
  target_resource_id         = azurerm_key_vault.kv.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.law.id

  enabled_log {
    category = "AuditEvent"
  }

  metric {
    category = "AllMetrics"
  }
}