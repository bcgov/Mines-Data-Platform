resource "azurerm_key_vault" "kv" {
  name                          = "kv-${var.projectNameAbbr}-${var.environment}-${var.locationAbbr}"
  location                      = azurerm_resource_group.security.location
  resource_group_name           = azurerm_resource_group.security.name
  tenant_id                     = var.tenant_id
  soft_delete_retention_days    = 7
  enabled_for_deployment        = false
  purge_protection_enabled      = true
  public_network_access_enabled = false
  enable_rbac_authorization     = true


  network_acls {
    default_action = "Deny"
    bypass         = "AzureServices"
    virtual_network_subnet_ids = [
      data.azurerm_subnet.privatesubnet.id,
      data.azurerm_subnet.containerinstancesubnet.id,
      data.azurerm_subnet.containerappsubnet.id
    ]
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
  depends_on = [
      data.azurerm_subnet.privatesubnet.id,
      data.azurerm_subnet.containerinstancesubnet.id,
      data.azurerm_subnet.containerappsubnet.id,
      azurerm_resource_group.security
    ]
}

resource "azurerm_monitor_diagnostic_setting" "kv-diag" {
  name                       = "diag-${var.projectNameAbbr}-${var.environment}-${var.locationAbbr}"
  target_resource_id         = azurerm_key_vault.kv.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.law.id
  metric {
    category = "AllMetrics"
  }
}