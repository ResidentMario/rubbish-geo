#!/bin/bash
# Run this script to deploy or redeploy the database listener.
set -e

# Check that jq is installed; we use this tool to outputs.
jq --help >/dev/null || (echo "jq is not installed, 'brew install jq' to get it." && exit 1)

echo "Checking functional API environment configuration...🏠"
GCP_PROJECT=$(gcloud config get-value project)
pushd ../js && FUNCTIONAL_API_ENV_CONFIG=$(firebase functions:config:get | jq '.functional_api') && popd
if [[ "$FUNCTIONAL_API_ENV_CONFIG" == "null" ]]; then
    echo "Functional API configuration secrets not set, creating now..."
    REGION=us-central1  # currently a hardcoded value
    POST_PICKUPS_URL=https://$REGION-$GCP_PROJECT.cloudfunctions.net/POST_pickups
    pushd ../js && firebase functions:config:set functional_api.post_pickups_url=$POST_PICKUPS_URL && popd
else
    echo "Functional API configuration secrets already set."
fi

echo "Checking Firebase service account...🔧"
pushd ../ 1>&0 && RUBBISH_BASE_DIR=$(echo $PWD) && popd 1>&0
if [[ ! -f "$RUBBISH_BASE_DIR/js/serviceAccountKey.json" ]]; then
    echo "Firebase service account key file js/serviceAccountKey.json not available locally, you "
    echo "need to download that first. See https://firebase.google.com/docs/database/admin/start."
fi
echo "Firebase service account already configured."

echo "Deploy firebase functions...⚙️"
pushd ../js && firebase deploy --only functions:proxy_POST_PICKUPS && popd

echo "All done! To see the functions deployed visit "
echo "https://console.firebase.google.com/project/$GCP_PROJECT/functions/list."