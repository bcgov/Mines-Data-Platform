#!/bin/bash

# Variables (customize these)
RESOURCE_GROUP="myResourceGroup"
LOCATION="eastus"
VNET_NAME="myVNet"
SUBNET_NAME="mySubnet"
VNET_ADDRESS_SPACE="10.0.0.0/16"
SUBNET_ADDRESS_PREFIX="10.0.1.0/24"

# Create a subnet
echo "Creating subnet..."
az network vnet subnet create \
  --name $SUBNET_NAME \
  --resource-group $RESOURCE_GROUP \
  --vnet-name $VNET_NAME \
  --address-prefix $SUBNET_ADDRESS_PREFIX

echo "Virtual network and subnet created successfully!"
