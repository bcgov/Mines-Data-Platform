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