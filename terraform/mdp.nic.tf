resource "azurerm_network_interface" "shir" {
  name                = "nic-${var.projectNameAbbr}-shir-${var.environment}-${var.locationAbbr}"
  resource_group_name = azurerm_resource_group.data.name
  location            = azurerm_resource_group.data.location

  ip_configuration {
    name                          = "internal"
    subnet_id                     = data.azurerm_subnet.privatesubnet.id
    private_ip_address_allocation = "Dynamic"
  }
}