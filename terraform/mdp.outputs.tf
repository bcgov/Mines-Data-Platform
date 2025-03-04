output "bastion" {
  value = module.azure_bastion
}

output "public_ip_address" {
  value = azurerm_public_ip.bastion_public_ip.ip_address
}

output "vnet_id" {
  value = data.azurerm_virtual_network.vnet.id
}

output "vnet_name" {
  value = data.azurerm_virtual_network.vnet.name
}