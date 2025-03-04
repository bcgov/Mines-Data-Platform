# resource "azurerm_role_assignment" "datastorageblobcontributor" {
#   scope                = azurerm_storage_account.data.id
#   role_definition_name = "Storage Blob Data Contributor"
#   principal_id         = data.azuread_client_config.current.object_id
# }

# resource "azurerm_role_assignment" "corestorageblobcontributor" {
#   scope                = azurerm_storage_account.core.id
#   role_definition_name = "Storage Blob Data Contributor"
#   principal_id         = data.azuread_client_config.current.object_id
# }

# resource "azurerm_role_assignment" "sp_keyvault_secret_reader" {
#   scope                = azurerm_key_vault.kv.id
#   role_definition_name = "Key Vault Secrets User"
#   principal_id         = data.azuread_client_config.current.object_id
# }