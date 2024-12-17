resource "azurerm_windows_virtual_machine" "jumpbox" {
  name                = "vm-${var.projectNameAbbr}-jump-${var.environment}-${var.locationAbbr}"
  resource_group_name = azurerm_resource_group.core.name
  location            = azurerm_resource_group.core.location
  size                = var.jumpbox_SKU
  admin_username      = "adminuser"
  admin_password      = "P@$$w0rd1234!"
  network_interface_ids = [
    azurerm_network_interface.jumpbox.id,
  ]
  
  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {
    publisher = "MicrosoftWindowsServer"
    offer     = "WindowsServer"
    sku       = "2016-Datacenter"
    version   = "latest"
  }
}