//TODO: Look: if you tf destroy this, it'll say it's done but it won't do anything
//      because the resource is still there. So you need to delete it manually so that 
//      tf destroy can destroy the NSGs too. This is a known issue with azapi.
resource "azapi_update_resource" "update_vnet" {
  type        = "Microsoft.Network/virtualNetworks@2023-05-01" # Adjust API version as needed
  resource_id = "/subscriptions/${var.subscription_id}/resourceGroups/${data.azurerm_virtual_network.vnet.resource_group_name}/providers/Microsoft.Network/virtualNetworks/${data.azurerm_virtual_network.vnet.name}"

  body = {
    properties = {
      subnets = [
        for subnet_name in var.subnet_names : {
          name       = subnet_name
          properties = {
            addressPrefix = cidrsubnet(data.azurerm_virtual_network.vnet.address_space[0], 2, index(var.subnet_names, subnet_name))
            networkSecurityGroup = {
              id = "/subscriptions/${var.subscription_id}/resourceGroups/rg-${var.projectNameAbbr}-${subnet_name == "AzureBastionSubnet" ? "core" : subnet_name}-${var.environment}-${var.locationAbbr}/providers/Microsoft.Network/networkSecurityGroups/nsg-${var.projectNameAbbr}-${subnet_name}-${var.environment}-${var.locationAbbr}"
            }
          }
        }
      ]
    }
  }

  depends_on = [
    azurerm_network_security_group.bastion_nsg,
    azurerm_network_security_group.core_nsg,
    azurerm_network_security_group.data_nsg,
    azurerm_network_security_group.security_nsg
  ]
}
