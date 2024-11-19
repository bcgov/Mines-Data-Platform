output "address_prefixes" {
  value = [for subnet_name in var.subnet_names : 
    cidrsubnet(data.azurerm_virtual_network.vnet.address_space[0], 2, index(var.subnet_names, subnet_name))
  ]
}

output "vnet_id" {
  value = data.azurerm_virtual_network.vnet.id
}

output "vnet_name" {
  value = data.azurerm_virtual_network.vnet.name
}