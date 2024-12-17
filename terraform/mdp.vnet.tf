resource "azapi_resource" "coresubnet" {
  type      = "Microsoft.Network/virtualNetworks/subnets@2024-03-01"
  name      = "core"
  parent_id = data.azurerm_virtual_network.vnet.id
  locks     = [data.azurerm_virtual_network.vnet.id]
  body = {
    properties = {
      addressPrefix = cidrsubnet(data.azurerm_virtual_network.vnet.address_space[0], 2, 0)
      networkSecurityGroup = {
        id = azurerm_network_security_group.core_nsg.id
      }
    }
  }

  depends_on = [azurerm_network_security_group.core_nsg]
}



resource "azapi_resource" "datasubnet" {
  type      = "Microsoft.Network/virtualNetworks/subnets@2024-03-01"
  name      = "data"
  parent_id = data.azurerm_virtual_network.vnet.id
  locks     = [data.azurerm_virtual_network.vnet.id]
  body = {
    properties = {
      addressPrefix = cidrsubnet(data.azurerm_virtual_network.vnet.address_space[0], 2, 1)
      networkSecurityGroup = {
        id = azurerm_network_security_group.data_nsg.id
      }
    }
  }

  depends_on = [azurerm_network_security_group.data_nsg]
}


resource "azapi_resource" "securitysubnet" {
  type      = "Microsoft.Network/virtualNetworks/subnets@2024-03-01"
  name      = "security"
  parent_id = data.azurerm_virtual_network.vnet.id
  locks     = [data.azurerm_virtual_network.vnet.id]
  body = {
    properties = {
      addressPrefix = cidrsubnet(data.azurerm_virtual_network.vnet.address_space[0], 2, 2)
      networkSecurityGroup = {
        id = azurerm_network_security_group.security_nsg.id
      }
    }
  }

  depends_on = [azurerm_network_security_group.security_nsg]
}

resource "azapi_resource" "azurebastionsubnet" {
  type      = "Microsoft.Network/virtualNetworks/subnets@2024-03-01"
  name      = "AzureBastionSubnet"
  parent_id = data.azurerm_virtual_network.vnet.id
  locks     = [data.azurerm_virtual_network.vnet.id]
  body = {
    properties = {
      addressPrefix = cidrsubnet(data.azurerm_virtual_network.vnet.address_space[0], 2, 3)
      networkSecurityGroup = {
        id = azurerm_network_security_group.azurebastionsubnet_nsg.id
      }
    }
  }

  depends_on = [azurerm_network_security_group.azurebastionsubnet_nsg]
}

