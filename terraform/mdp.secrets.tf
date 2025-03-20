resource "azurerm_key_vault_secret" "jumpboxadminuser" {
  name            = "jumpboxadminuser"
  value           = "mdpadmin"
  key_vault_id    = azurerm_key_vault.kv.id
  depends_on      = [azurerm_key_vault.kv, module.private_endpoint_kv]
  expiration_date = timeadd(timestamp(), "2160h")
  lifecycle {
    ignore_changes = [
      tags
    ]
  }
}

resource "random_password" "jumpboxadminpassword" {
  length  = 16
  special = true
}

resource "azurerm_key_vault_secret" "jumpboxadminpassword" {
  name            = "jumpboxadminpassword"
  value           = random_password.jumpboxadminpassword.result
  key_vault_id    = azurerm_key_vault.kv.id
  depends_on      = [azurerm_key_vault.kv, module.private_endpoint_kv]
  expiration_date = timeadd(timestamp(), "2160h")
  lifecycle {
    ignore_changes = [
      tags
    ]
  }
}