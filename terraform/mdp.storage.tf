resource "azurerm_storage_account" "core" {
  name                            = lower("stg${var.projectNameAbbr}core${var.environment}")
  resource_group_name             = azurerm_resource_group.core.name
  location                        = var.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  account_kind                    = "StorageV2"
  access_tier                     = "Hot"
  public_network_access_enabled   = false
  allow_nested_items_to_be_public = false
  local_user_enabled              = false


  https_traffic_only_enabled = true
  min_tls_version            = "TLS1_2"

  network_rules {
    default_action = "Deny"
    bypass         = ["None"]
    virtual_network_subnet_ids = [
      data.azurerm_subnet.privatesubnet.id,
    ]
  }

  tags = var.tags

  lifecycle {
    ignore_changes = [
      tags,
      network_rules
    ]
  }
}

resource "azurerm_storage_account" "data" {
  name                            = lower("stg${var.projectNameAbbr}data${var.environment}")
  resource_group_name             = azurerm_resource_group.data.name
  location                        = var.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  account_kind                    = "StorageV2"
  access_tier                     = "Hot"
  public_network_access_enabled   = false
  https_traffic_only_enabled      = true
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  local_user_enabled              = false

  network_rules {
    default_action = "Deny"
    bypass         = ["None"]
    virtual_network_subnet_ids = [
      data.azurerm_subnet.privatesubnet.id,
    ]
  }

  tags = var.tags

  lifecycle {
    ignore_changes = [
      tags,
      network_rules
    ]
  }
}