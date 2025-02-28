resource "azurerm_key_vault_secret" "jumpboxadminuser" {
  name         = "jumpboxadminuser"
  value        = "mdpadmin"
  key_vault_id = azurerm_key_vault.kv.id
  depends_on   = [azurerm_private_endpoint.kv]
}

resource "random_password" "jumpboxadminpassword" {
  length     = 16
  special    = true
  depends_on = [azurerm_private_endpoint.kv]
}

resource "azurerm_key_vault_secret" "jumpboxadminpassword" {
  name         = "jumpboxadminpassword"
  value        = random_password.jumpboxadminpassword.result
  key_vault_id = azurerm_key_vault.kv.id
  depends_on   = [azurerm_private_endpoint.kv]
}