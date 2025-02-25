#!/bin/bash

# Take the first command line parameter as environment
ENVIRONMENT=$1

# Check that the environment is not empty
if [ -z "$ENVIRONMENT" ]; then
  echo "ERROR: Environment must be specified as the first command line parameter."
  exit 1
fi

# Proceed with the script
echo "Environment is set to $ENVIRONMENT"

# Set variables
export environment=$ENVIRONMENT
export vmName="github-runner"
export vmSize="Standard_DS2_v2"
export adminUsername="adminuser"

# Create resource group
az group create -n rg-mdp-cloudshell-${environment}-ca -l canadacentral

# Create default NSG
az network nsg create --name nsg-mdp-cloudshell-${environment}-ca --resource-group rg-mdp-cloudshell-${environment}-ca --location canadacentral

# Create cloudshell subnet
az network vnet subnet create \
	--name subnet-mdp-cloudshell-${environment}-ca \
    --address-prefixes 10.0.0.0/24 \
	--resource-group ef74b0-${environment}-networking \
	--vnet-name ef74b0-${environment}-vwan-spoke \
	--delegations Microsoft.ContainerInstance/containerGroups \
    --service-endpoints Microsoft.Storage \
    --nsg nsg-mdp-cloudshell-${environment}-ca