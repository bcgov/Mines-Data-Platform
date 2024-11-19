resource "azurerm_network_security_group" "azurebastionsubnet_nsg" {
  name                = "nsg-${var.projectNameAbbr}-AzureBastionSubnet-${var.environment}-${var.locationAbbr}"
  location            = var.location
  resource_group_name = azurerm_resource_group.core.name

  security_rule {
    name                       = "Allow-443-From-Internet"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_address_prefix      = "Internet"
    destination_address_prefix = "*"
    destination_port_range     = "443"
    source_port_range          = "*"
  }

  security_rule {
    name                       = "Allow-443-From-GatewayManager"
    priority                   = 200
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_address_prefix      = "GatewayManager"
    destination_address_prefix = "*"
    destination_port_range     = "443"
    source_port_range          = "*"
  }

  security_rule {
    name                       = "Allow-8080-5701-From-VirtualNetwork"
    priority                   = 300
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "VirtualNetwork"
    destination_port_ranges    = ["8080", "5701"]
    source_port_range          = "*"
  }

  security_rule {
    name                       = "Allow-443-From-AzureLoadBalancer"
    priority                   = 400
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_address_prefix      = "AzureLoadBalancer"
    destination_address_prefix = "*"
    destination_port_range     = "443"
    source_port_range          = "*"
  }

  # Egress Rules
  security_rule {
    name                       = "Allow-3389-22-To-VirtualNetwork"
    priority                   = 500
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_address_prefix      = "*"
    destination_address_prefix = "VirtualNetwork"
    destination_port_ranges    = ["3389", "22"]
    source_port_range          = "*"
  }

  security_rule {
    name                       = "Allow-8080-5701-To-VirtualNetwork"
    priority                   = 600
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "VirtualNetwork"
    destination_port_ranges    = ["8080", "5701"]
    source_port_range          = "*"
  }

  security_rule {
    name                       = "Allow-443-To-AzureCloud"
    priority                   = 700
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_address_prefix      = "*"
    destination_address_prefix = "AzureCloud"
    destination_port_range     = "443"
    source_port_range          = "*"
  }

  security_rule {
    name                       = "Allow-80-To-Internet"
    priority                   = 800
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_address_prefix      = "*"
    destination_address_prefix = "Internet"
    destination_port_range     = "80"
    source_port_range          = "*"
  }
}

resource "azurerm_network_security_group" "core_nsg" {
  name                = "nsg-${var.projectNameAbbr}-core-${var.environment}-${var.locationAbbr}"
  location            = var.location
  resource_group_name = azurerm_resource_group.core.name
}

resource "azurerm_network_security_group" "data_nsg" {
  name                = "nsg-${var.projectNameAbbr}-data-${var.environment}-${var.locationAbbr}"
  location            = var.location
  resource_group_name = azurerm_resource_group.data.name
}

resource "azurerm_network_security_group" "security_nsg" {
  name                = "nsg-${var.projectNameAbbr}-security-${var.environment}-${var.locationAbbr}"
  location            = var.location
  resource_group_name = azurerm_resource_group.security.name
}
