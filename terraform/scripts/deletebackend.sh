#!/bin/bash
ENVIRONMENT="test"
RESOURCE_GROUP_NAME="rg-mdp-unmanaged-$ENVIRONMENT-ca"
STORAGE_ACCOUNT_NAME="stgmdptfstateca"
CONTAINER_NAME="tfstate"

echo "Creating backend resources..."

# Check if resource group exists
if [ $(az group show --name $RESOURCE_GROUP_NAME &> /dev/null; echo $?) -eq 0 ]; then
  echo "Resource group $RESOURCE_GROUP_NAME already exists. Skipping creation"
else
  # Create resource group
  az group create --name $RESOURCE_GROUP_NAME --location canadacentral
fi

# Check if storage account exists
if [ $(az storage account show --name $STORAGE_ACCOUNT_NAME --resource-group $RESOURCE_GROUP_NAME &> /dev/null; echo $?) -eq 0 ]; then

  echo "Storage account $STORAGE_ACCOUNT_NAME already exists. Skipping creation"
  # Check if network rule exists
  CURRENT_IP=$(curl -s https://api.ipify.org)
  az storage account network-rule add --resource-group $RESOURCE_GROUP_NAME --account-name $STORAGE_ACCOUNT_NAME --ip-address $CURRENT_IP

else
  # Create storage account with soft delete off
  az storage account create --name $STORAGE_ACCOUNT_NAME --resource-group $RESOURCE_GROUP_NAME --location canadacentral --sku Standard_LRS --kind BlobStorage --access-tier Hot --allow-blob-public-access false --default-action Deny --bypass AzureServices --min-tls-version TLS1_2 --allow-shared-key-access false
  CURRENT_IP=$(curl -s https://api.ipify.org)
  az storage account network-rule add --resource-group $RESOURCE_GROUP_NAME --account-name $STORAGE_ACCOUNT_NAME --ip-address $CURRENT_IP
  
fi

# Check if container exists
if [ $(az storage container show --name $CONTAINER_NAME --account-name $STORAGE_ACCOUNT_NAME &> /dev/null; echo $?) -eq 0 ]; then
  echo "Container $CONTAINER_NAME already exists. Skipping creation"
else
  # Create container
  az storage container create --name $CONTAINER_NAME --account-name $STORAGE_ACCOUNT_NAME --auth-mode login --public-access off
fi


