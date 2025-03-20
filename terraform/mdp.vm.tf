resource "azurerm_windows_virtual_machine" "shir" {
  name                = "vm-${var.projectNameAbbr}-shir-${var.environment}-${var.locationAbbr}"
  resource_group_name = azurerm_resource_group.core.name
  computer_name       = "vm-${var.projectNameAbbr}-jump"
  location            = azurerm_resource_group.core.location
  size                = var.jumpbox_SKU
  admin_username      = azurerm_key_vault_secret.jumpboxadminuser.value
  admin_password      = azurerm_key_vault_secret.jumpboxadminpassword.value
  network_interface_ids = [
    azurerm_network_interface.shir.id,
  ]
  patch_assessment_mode = "AutomaticByPlatform"

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
  lifecycle {
    ignore_changes = [
      tags,
      identity
    ]
  }
}