//TODO: integrate this through variables
data "azurerm_virtual_network" "vnet" {
  name                = ""
  resource_group_name = ""
}

output "virtual_network_id" {
  value = data.azurerm_virtual_network.example.id
}