#!/bin/bash

#TODO: TEST THIS

# Set variables
vmName="github-runner"
vmSize="Standard_DS2_v2"
adminUsername="adminuser"
adminPassword=$(az ad sp create-for-rbac --name $vmName --role contributor --scopes /subscriptions/$(az account show --query id -o tsv) --query password -o tsv)

# Create the VM
az vm create \
  --name $vmName \
  --resource-group $(az group show --query name -o tsv) \
  --image UbuntuLTS \
  --size $vmSize \
  --admin-username $adminUsername \
  --admin-password $adminPassword \
  --generate-ssh-keys \
  --public-ip-address "" \
  --vnet-name $(az network vnet show --query name -o tsv) \
  --subnet $(az network vnet subnet list --resource-group $(az group show --query name -o tsv) --vnet-name $(az network vnet show --query name -o tsv) --query "[0].name" -o tsv) \
  --assign-identity --identity $(az identity create --name $vmName --resource-group $(az group show --query name -o tsv) --query id -o tsv)

# Configure the VM
az vm extension set \
  --resource-group $(az group show --query name -o tsv) \
  --vm-name $vmName \
  --name CustomScriptExtension \
  --publisher Microsoft.Azure.Extensions \
  --version 2.0 \
  --settings '{"commandToExecute": "apt-get update && apt-get install -y docker.io && systemctl start docker && systemctl enable docker && docker run -d --restart=always -e GITHUB_TOKEN=${GITHUB_TOKEN} -e GITHUB_REPOSITORY=${GITHUB_REPOSITORY} -e GITHUB_RUNNER_NAME=${vmName} -e GITHUB_RUNNER_GROUP=private --name github-runner docker:latest entrypoint.sh"}'
