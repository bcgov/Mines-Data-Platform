#!/bin/bash
ENVIRONMENT=$1
LICENSE_PLATE="ef74b0"

if [ -z "$ENVIRONMENT" ]; then
  echo "ERROR: Environment must be specified as the first command line parameter."
  exit 1
fi

RESOURCE_GROUP_NAME="rg-mdp-unmanaged-$ENVIRONMENT-ca"
STORAGE_ACCOUNT_NAME="stgmdptfstate${ENVIRONMENT}ca"
CONTAINER_NAME="tfstate"
SUBSCRIPTION_NAME=$LICENSE_PLATE-$ENVIRONMENT
SUBSCRIPTION_ID=$(az account list --query "[?name=='$SUBSCRIPTION_NAME'].id" -o tsv)

ACCOUNT_TYPE=$(az account show --query user.type -o tsv)
echo $ACCOUNT_TYPE
echo $()

if [ -z "$ACCOUNT_TYPE" ]; then
  echo "No Azure login found, please log in with 'az login --scope https://graph.microsoft.com//.default'"
  exit 1
fi

echo "Creating backend resources..."

# Check if resource group exists
if [ $(az group show --name $RESOURCE_GROUP_NAME &> /dev/null; echo $?) -eq 0 ]; then
  echo "Resource group $RESOURCE_GROUP_NAME already exists. Skipping creation"
else
  # Create resource group
  az group create --name $RESOURCE_GROUP_NAME --location canadacentral
fi

sleep 2

# Check if storage account exists
if [ $(az storage account show --name $STORAGE_ACCOUNT_NAME --resource-group $RESOURCE_GROUP_NAME &> /dev/null; echo $?) -eq 0 ]; then

  echo "Storage account $STORAGE_ACCOUNT_NAME already exists. Skipping creation"
  # Check if network rule exists
  CURRENT_IP=$(curl -s https://api.ipify.org)
  sleep 2
  az storage account network-rule add --resource-group $RESOURCE_GROUP_NAME --account-name $STORAGE_ACCOUNT_NAME --ip-address $CURRENT_IP

else
  # Create storage account with soft delete off
  az storage account create --name $STORAGE_ACCOUNT_NAME --resource-group $RESOURCE_GROUP_NAME --location canadacentral --sku Standard_LRS --kind BlobStorage --access-tier Hot --allow-blob-public-access false --default-action Deny --bypass AzureServices --min-tls-version TLS1_2 --allow-shared-key-access false
  CURRENT_IP=$(curl -s https://api.ipify.org)
  sleep 2
  az storage account network-rule add --resource-group $RESOURCE_GROUP_NAME --account-name $STORAGE_ACCOUNT_NAME --ip-address $CURRENT_IP
  
fi

sleep 2

# Check if container exists
if [ $(az storage container show --name $CONTAINER_NAME --account-name $STORAGE_ACCOUNT_NAME &> /dev/null; echo $?) -eq 0 ]; then
  echo "Container $CONTAINER_NAME already exists. Skipping creation"
else
  # Create container
  az storage container create --name $CONTAINER_NAME --account-name $STORAGE_ACCOUNT_NAME --auth-mode login --public-access off
fi

sleep 2

# Check if the current Azure credentials have Storage Blob Data Contributor role on the storage account
if [[ $ACCOUNT_TYPE = "user" ]]; then
  echo "Current login is of type USER"
  ASSIGNEE_OBJECT_ID=$(az ad signed-in-user show --query id -o tsv)
fi

if [[ $ACCOUNT_TYPE = "servicePrincipal" ]]; then
  echo "Current login is of type SERVICE_PRINCIPAL"
  ASSIGNEE_APP_ID=$(az account show --query user.name -o tsv)
  ASSIGNEE_OBJECT_ID=$(az ad sp show --id $ASSIGNEE_APP_ID --query id -o tsv)
fi

echo "Current user: $ASSIGNEE_OBJECT_ID"

ROLE_NAME="Storage Blob Data Contributor"
ROLE_ID="ba92f5b4-2d11-453d-a403-e96b0029c9fe"

# Debugging below
# echo $(az role assignment list --assignee $ASSIGNEE_OBJECT_ID --query "[].roleDefinitionId") #-o tsv)

ROLE_ASSIGNMENTS=$(az role assignment list --assignee $ASSIGNEE_OBJECT_ID --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP_NAME/providers/Microsoft.Storage/storageAccounts/$STORAGE_ACCOUNT_NAME" --query "[].roleDefinitionName" -o tsv)

if [[ $ROLE_ASSIGNMENTS =~ $ROLE_NAME ]]; then
  echo "Current user already has '$ROLE_NAME' role on the storage account."
else
  echo "Current user does not have '$ROLE_NAME' role on the storage account. Assigning role..."
  az role assignment create --assignee $ASSIGNEE_OBJECT_ID --role "$ROLE_NAME" --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP_NAME/providers/Microsoft.Storage/storageAccounts/$STORAGE_ACCOUNT_NAME"
fi

echo "Done"