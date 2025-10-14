data "azurerm_virtual_network" "vnet" {
  name                = "${var.licensePlate}-${var.environment}-vwan-spoke"
  resource_group_name = "${var.licensePlate}-${var.environment}-networking"
}

# data "azurerm_subnet" "containerappsubnet" {
#   name                 = "sn-${var.projectNameAbbr}-containerapp-${var.environment}-${var.locationAbbr}"
#   virtual_network_name = data.azurerm_virtual_network.vnet.name
#   resource_group_name  = data.azurerm_virtual_network.vnet.resource_group_name
# }

# data "azurerm_subnet" "containerinstancesubnet" {
#   name                 = "sn-${var.projectNameAbbr}-containerinstance-${var.environment}-${var.locationAbbr}"
#   virtual_network_name = data.azurerm_virtual_network.vnet.name
#   resource_group_name  = data.azurerm_virtual_network.vnet.resource_group_name
# }


data "azuread_client_config" "current" {}
data "azurerm_subscription" "current" {}