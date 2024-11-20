//TODO: Look: if you tf destroy this, it'll say it's done but it won't do anything
//      because the resource is still there. So you need to delete it manually so that 
//      tf destroy can destroy the NSGs too. This is a known issue with azapi.

# TODO: Create subnets dynamically based off subnet names list
# resource "azapi_resource" "subnets" {
#   for_each = toset(var.subnet_names)

#   type     = "Microsoft.Network/virtualNetworks/subnets@2024-03-01"
#   name     = each.key
#   parent_id = data.azurerm_virtual_network.vnet.id
#   location = data.azurerm_virtual_network.vnet.location

#   body = jsonencode({
#     addressPrefix = cidrsubnet(data.azurerm_virtual_network.vnet.address_space[0], 2, index(var.subnet_names, each.key))
#     networkSecurityGroup = {
#       id = azapi_resource.nsgs[each.key].id
#     }
#   })
# }

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

