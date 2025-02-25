package terrascan.azure

deny[msg] {
  input.resource_type == "azurerm_storage_account"
  input.config.public_network_access == "Enabled"
  msg := "Failing pipeline: Azure Storage Account has public access enabled."
}
