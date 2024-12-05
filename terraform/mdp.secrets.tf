resource "azurerm_key_vault_secret" "jumpboxadminuser" {
  name         = "jumpboxadminuser"
  value        = "mdpadmin"
  key_vault_id = azurerm_key_vault.kv.id
}

resource "random_password" "jumpboxadminpassword" {
  length  = 16
  special = true
}

resource "azurerm_key_vault_secret" "jumpboxadminpassword" {
  name         = "jumpboxadminpassword"
  value        = random_password.jumpboxadminpassword.result
  key_vault_id = azurerm_key_vault.kv.id
}