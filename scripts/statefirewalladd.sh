#!/bin/bash
CURRENT_IP=$(curl -s https://api.ipify.org)
  az storage account network-rule add \
    --resource-group $RESOURCE_GROUP_NAME \
    --account-name $STORAGE_ACCOUNT_NAME \
    --ip-address $CURRENT_IP