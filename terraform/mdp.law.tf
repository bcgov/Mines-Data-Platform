# resource "azurerm_monitor_diagnostic_setting" "test" {
#   name               = "example"
#   target_resource_id = "${azurerm_key_vault.test.id}"
#   storage_account_id = "${azurerm_storage_account.test.id}"
#   log_analytics_workspace_id = "${data.azurerm_log_analytics_workspace.test.id}"


#   log {
#     category = "AuditEvent"
#     enabled  = false

#     retention_policy {
#       enabled = false
#     }
#   }

#   metric {
#     category = "AllMetrics"

#     retention_policy {
#       enabled = false
#     }
#   }
# }