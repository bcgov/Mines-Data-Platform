#!/bin/bash

ACCOUNT_TYPE=$(az account show --query user.type -o tsv)

if [ -z "$ACCOUNT_TYPE" ]; then
  echo "No Azure login found, please log in with 'az login --scope https://graph.microsoft.com//.default'"
  exit 1
fi

if [ -z "$1" ]; then
  echo "You must specify the environment as an argument"
  exit 1
fi

# Set variables
ENVIRONMENT=$1
ADDRESS_SPACE=""
vmName="github-runner"
vmSize="Standard_DS2_v2"
adminUsername="adminuser"
admin_password_secret_name="github-runner-admin-password"

LICENSE_PLATE="ef74b0"
SUBSCRIPTION_NAME=$LICENSE_PLATE-$ENVIRONMENT
SUBSCRIPTION_ID=$(az account list --query "[?name=='$SUBSCRIPTION_NAME'].id" -o tsv)

resourcegroup="rg-mdp-runner-${ENVIRONMENT}-ca"
location="canadacentral"

keyvault_name="kv-mdp-runner-${ENVIRONMENT}-ca"


if [[ $ACCOUNT_TYPE = "user" ]]; then
  echo "Current login is of type USER"
  ASSIGNEE_OBJECT_ID=$(az ad signed-in-user show --query id -o tsv)
fi

if [[ $ACCOUNT_TYPE = "servicePrincipal" ]]; then
  echo "Current login is of type SERVICE_PRINCIPAL"
  ASSIGNEE_OBJECT_ID=$(az ad sp show --id $(az account show --query user.name -o tsv) --query id -o tsv)
fi

echo "Creating resource group $resourcegroup in $location"
az group create -n $resourcegroup -l $location
echo "Done"

#TODO: HERE
echo "Creating runner subnet"
az network vnet subnet create \
  --name subnet-mdp-runner-${ENVIRONMENT}-ca \
  --address-prefixes 10.0.1.0/24 \
  --resource-group $resourcegroup \
  --vnet-name ef74b0-${ENVIRONMENT}-vwan-spoke \
  --delegations Microsoft.ContainerService/managedClusters \
  --nsg default

echo "Creating key vault $keyvault_name in $location"
az keyvault create \
  -n $keyvault_name \
  -g $resourcegroup \
  -l $location \
  --enabled-for-deployment True \
  --enabled-for-disk-encryption True \
  --enabled-for-template-deployment True \
  --public-network-access disabled \
  --bypass AzureServices \
  --enable-rbac-authorization True \
  --enable-purge-protection True

wait 3 # Wait for the key vault to be created
echo "Done"

# Generate a random admin password
echo "Generating a random password for the VM and storing it in Key Vault"
admin_password=$(openssl rand -base64 16)

# Store the password as a secret in Key Vault
az keyvault secret set \
  --vault-name $keyvault_name \
  --name $admin_password_secret_name \
  --value $admin_password \
  -o none


# # Retrieve the password from Key Vault during VM creation
admin_password=$(az keyvault secret show \
  --vault-name $keyvault_name \
  --name $admin_password_secret_name \
  --query value -o tsv)

echo "Creating VM $vmName in $resourcegroup"
az vm create -n $vmName -g $resourcegroup --image UbuntuLTS --size $vmSize --admin-username $adminUsername --adminPassword
echo "Done"