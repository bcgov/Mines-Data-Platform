resource "azapi_resource" "publicsubnet" {
  type      = "Microsoft.Network/virtualNetworks/subnets@2024-03-01"
  name      = "subnet-${var.projectNameAbbr}-public-${var.environment}-${var.locationAbbr}"
  parent_id = data.azurerm_virtual_network.vnet.id
  locks     = [data.azurerm_virtual_network.vnet.id]
  body = {
    properties = {
      addressPrefix = cidrsubnet(data.azurerm_virtual_network.vnet.address_space[0], 2, 0)
      networkSecurityGroup = {
        id = azurerm_network_security_group.public_nsg.id
      }
    }
  }

  depends_on = [azurerm_network_security_group.public_nsg]
}



resource "azapi_resource" "privatesubnet" {
  type      = "Microsoft.Network/virtualNetworks/subnets@2024-03-01"
  name      = "private"
  parent_id = data.azurerm_virtual_network.vnet.id
  locks     = [data.azurerm_virtual_network.vnet.id]
  body = {
    properties = {
      addressPrefix = cidrsubnet(data.azurerm_virtual_network.vnet.address_space[0], 2, 1)
      networkSecurityGroup = {
        id = azurerm_network_security_group.private_nsg.id
      }
    }
  }

  depends_on = [azurerm_network_security_group.private_nsg]
}