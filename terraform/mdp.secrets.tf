resource "azurerm_key_vault_secret" "jumpboxadminuser" {
  name            = "jumpboxadminuser"
  value           = "mdpadmin"
  key_vault_id    = azurerm_key_vault.kv.id
  depends_on      = [azurerm_private_endpoint.kv, azurerm_role_assignment.sp_keyvault_secret_reader]
  expiration_date = timeadd(timestamp(), "2160h")
}

resource "random_password" "jumpboxadminpassword" {
  length     = 16
  special    = true
  depends_on = [azurerm_private_endpoint.kv, azurerm_role_assignment.sp_keyvault_secret_reader]
}

resource "azurerm_key_vault_secret" "jumpboxadminpassword" {
  name            = "jumpboxadminpassword"
  value           = random_password.jumpboxadminpassword.result
  key_vault_id    = azurerm_key_vault.kv.id
  depends_on      = [azurerm_private_endpoint.kv]
  expiration_date = timeadd(timestamp(), "2160h")
}