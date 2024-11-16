resource "azurerm_subnet" "core" {
  name                 = "core"
  resource_group_name  = azurerm_resource_group.core.name
  virtual_network_name = data.azurerm_virtual_network.vnet.name
  address_prefixes     = var.address_prefixes

  enforce_private_link_service_network_policies = true
}

resource "azurerm_subnet" "core" {
  name                 = "AzureBastionSubnet"
  resource_group_name  = azurerm_resource_group.core.name
  virtual_network_name = data.azurerm_virtual_network.vnet.name
  address_prefixes     = var.address_prefixes

  enforce_private_link_service_network_policies = true
}