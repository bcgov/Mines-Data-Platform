resource "azapi_resource" "publicsubnet" {
  type      = "Microsoft.Network/virtualNetworks/subnets@2024-03-01"
  name      = "sn-${var.projectNameAbbr}-public-${var.environment}-${var.locationAbbr}"
  parent_id = data.azurerm_virtual_network.vnet.id
  locks     = [data.azurerm_virtual_network.vnet.id]
  body = {
    properties = {
      addressPrefix = cidrsubnet(data.azurerm_virtual_network.vnet.address_space[0], 2, 1)
      networkSecurityGroup = {
        id = azurerm_network_security_group.public_nsg.id
      }
      serviceEndpoints = [
        {
          service = "Microsoft.KeyVault"
        },
        {
          service = "Microsoft.Storage"
        }
      ]
    }
  }

  depends_on = [azurerm_network_security_group.public_nsg]
}

resource "azapi_resource" "privatesubnet" {
  type      = "Microsoft.Network/virtualNetworks/subnets@2024-03-01"
  name      = "sn-${var.projectNameAbbr}-private-${var.environment}-${var.locationAbbr}"
  parent_id = data.azurerm_virtual_network.vnet.id
  locks     = [data.azurerm_virtual_network.vnet.id]
  body = {
    properties = {
      addressPrefix = cidrsubnet(data.azurerm_virtual_network.vnet.address_space[0], 2, 2)
      networkSecurityGroup = {
        id = azurerm_network_security_group.private_nsg.id
      }
      serviceEndpoints = [
        {
          service = "Microsoft.KeyVault"
        },
        {
          service = "Microsoft.Storage"
        }
      ]
    }
  }

  depends_on = [azurerm_network_security_group.public_nsg]
}

# data "azurerm_subnet" "privatesubnet" {
#   name                 = "sn-${var.projectNameAbbr}-private-${var.environment}-${var.locationAbbr}"
#   virtual_network_name = data.azurerm_virtual_network.vnet.name
#   resource_group_name  = "${var.licensePlate}-${var.environment}-networking"
# }

resource "azapi_resource" "bastion_subnet" {
  type = "Microsoft.Network/virtualNetworks/subnets@2024-05-01"

  name      = "AzureBastionSubnet"
  parent_id = data.azurerm_virtual_network.vnet.id
  locks = [
    data.azurerm_virtual_network.vnet.id
  ]

  body = {
    properties = {
      addressPrefix = var.bastionSubnetAddressPrefix #bastion takes the priority with /26 subnet size
      networkSecurityGroup = {
        id = azurerm_network_security_group.bastion_nsg.id
      }
      serviceEndpoints = [
        {
          service = "Microsoft.KeyVault"
        },
        {
          service = "Microsoft.Storage"
        }
      ]
    }
  }
  response_export_values = ["*"]
}
