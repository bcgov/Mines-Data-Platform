RESOURCE_GROUP_NAME=$1
STORAGE_ACCOUNT_NAME=$2

echo "Adding firewall rule for storage account $STORAGE_ACCOUNT_NAME in resource group $RESOURCE_GROUP_NAME"

if [ -z "$1" ] || [ -z "$2" ]; then
  echo "ERROR: Both resource group name and storage account name must be specified as arguments"
  exit 1
fi

CURRENT_IP=$(curl -s https://api.ipify.org)
  az storage account network-rule add --resource-group $RESOURCE_GROUP_NAME --account-name $STORAGE_ACCOUNT_NAME --ip-address $CURRENT_IP