resource "azurerm_private_endpoint" "this" {
  name                = var.endpoint_name
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.subnet_id

  private_service_connection {
    name                           = var.connection_name
    private_connection_resource_id = var.resource_id
    is_manual_connection           = false
    subresource_names              = var.subresource_names
  }
}

resource "time_sleep" "wait_for_dns" {
  depends_on      = [azurerm_private_endpoint.this]
  create_duration = "700s"
}

# resource "null_resource" "poll_private_endpoint" {
#   provisioner "local-exec" {
#     command = <<-EOF
#       #!/bin/sh
#       echo "Polling Private Endpoint at http://${azurerm_private_endpoint.this.private_service_connection[0].private_ip_address}..."

#       for i in $(seq 1 12); do
#         HTTP_CODE=$(curl -s -o /dev/null -w "%%{http_code}" "http://${azurerm_private_endpoint.this.private_service_connection[0].private_ip_address}")
#         if [ "$$HTTP_CODE" = "200" ]; then
#           echo "Endpoint is available (HTTP $$HTTP_CODE). Proceeding..."
#           exit 0
#         fi
#         echo "Attempt $$i/12: Received HTTP $$HTTP_CODE. Retrying in 10 seconds..."
#         sleep 10
#       done

#       echo "Endpoint did not become available after 12 attempts."
#       exit 1
#     EOF
#   }
# }