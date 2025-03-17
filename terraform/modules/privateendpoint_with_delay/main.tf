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

# resource "time_sleep" "wait_for_dns" {
#   depends_on      = [azurerm_private_endpoint.this]
#   create_duration = "30s"
# }

resource "null_resource" "poll_private_endpoint" {
  depends_on = [azurerm_private_endpoint.this]

  provisioner "local-exec" {
    command = <<-EOT
      #!/bin/bash
      set -e

      # Extract Private IP address of the endpoint
      PRIVATE_IP="${azurerm_private_endpoint.this.private_service_connection[0].private_ip_address}"
      URL="http://$PRIVATE_IP"

      echo "Polling Private Endpoint at $URL..."

      MAX_RETRIES=20
      SLEEP_INTERVAL=60
      retry=0

      while [ $retry -lt $MAX_RETRIES ]; do
        HTTP_CODE=$(curl -s -o /dev/null -w "%%{http_code}" "$URL")
        if [ "$HTTP_CODE" == "200" ]; then
          echo "Endpoint is available (HTTP $${HTTP_CODE}). Proceeding..."
          exit 0
        fi
        echo "Attempt $((retry+1))/$${MAX_RETRIES}: Received HTTP $${HTTP_CODE}. Retrying in $${SLEEP_INTERVAL} seconds..."
        sleep $SLEEP_INTERVAL
        retry=$((retry+1))
      done

      echo "Endpoint did not become available after $#{MAX_RETRIES} attempts."
      exit 1
    EOT
  }
}
