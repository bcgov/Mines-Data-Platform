resource "azurerm_network_interface" "jumpbox" {
  name                = "nic-${var.projectNameAbbr}-jump-${var.environment}-${var.locationAbbr}"
  resource_group_name = azurerm_resource_group.core.name
  location            = azurerm_resource_group.core.location

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.core.id
    private_ip_address_allocation = "Dynamic"
  }
}
