#TODO: Refine this so that we pull subscription IDs for our environments through az cli
SPN="6cdbb0a3-0fbf-4386-829f-fa2cb5f2f506"

for subscription_id in "53205a1b-0f8d-459e-a424-65f1b39ec648" "d2189515-2427-4198-8c73-0e097c8c28d7" "d2e2f655-7487-471b-84b0-a2bf13e47bb1"
do
    # Set the subscription context
    az account set --subscription $subscription_id

    # Assign a role (e.g., Contributor) to the Service Principal
    az role assignment create \
        --assignee $SPN \
        --role "Contributor" \
        --scope /subscriptions/$subscription_id

    az role assignment create \
        --assignee $SPN \
        --role "Key Vault Contributor" \
        --scope /subscriptions/$subscription_id

    az role assignment create \
        --assignee $SPN \
        --role "Key Vault Secrets Officer" \
        --scope /subscriptions/$subscription_id
done

echo "Assignment Complete!"
