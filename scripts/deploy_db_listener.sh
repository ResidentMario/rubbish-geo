#!/bin/bash
# Run this script to deploy or redeploy the database listener.
set -e

# Check that jq is installed; we use this tool to outputs.
jq --help >/dev/null || (echo "jq is not installed, 'brew install jq' to get it." && exit 1)

# Set this to the Rubbish environment, one of {dev, prod}.
if [[ -z "$RUBBISH_GEO_ENV" ]]; then
    echo "RUBBISH_GEO_ENV environment variable not set, exiting." && exit 1
fi
# Set this to the Firebase project ID, e.g. rubbishproduction-411a1.
if [[ -z "$FIREBASE_PROJECT" ]]; then
    echo "FIREBASE_PROJECT environment variable not set, exiting." && exit 1
fi

echo "Checking functional API environment configuration...🏠"
GCP_PROJECT=$(gcloud config get-value project)
pushd ../js && \
    FUNCTIONAL_API_ENV_CONFIG=$(firebase --project $FIREBASE_PROJECT functions:config:get | \
        jq '.functional_api') && \
    popd
if [[ "$FUNCTIONAL_API_ENV_CONFIG" == "null" ]]; then
    echo "Functional API configuration secrets not set, creating now..."
    REGION=us-central1  # currently a hardcoded value
    POST_PICKUPS_URL=https://$REGION-$GCP_PROJECT.cloudfunctions.net/POST_pickups
    pushd ../js && \
        firebase --project $FIREBASE_PROJECT functions:config:set \
            functional_api.post_pickups_url=$POST_PICKUPS_URL \
        && popd
else
    echo "Functional API configuration secrets already set."
fi

echo "Checking Firebase service account...🔧"
pushd ../ 1>&0 && RUBBISH_BASE_DIR=$(echo $PWD) && popd 1>&0
if [[ "$RUBBISH_GEO_ENV" == "dev" ]]; then
    SERVICE_ACCOUNT_KEY=$RUBBISH_BASE_DIR/auth/devServiceAccountKey.json
elif [[ "$RUBBISH_GEO_ENV" == "prod" ]]; then
    SERVICE_ACCOUNT_KEY=$RUBBISH_BASE_DIR/auth/prodServiceAccountKey.json
else
    echo "RUBBISH_GEO_ENV value '$RUBBISH_GEO_ENV' not understood, must be one of {dev, prod}."
    exit 1
fi
if [[ ! -f "$SERVICE_ACCOUNT_KEY" ]]; then
    echo "Firebase service account key file $SERVICE_ACCOUNT_KEY not available locally, you "
    echo "need to download that first. See https://firebase.google.com/docs/database/admin/start."
    exit 1
fi
echo "Firebase service account already configured."

echo "Deploy firebase functions...⚙️"
pushd ../js && \
    GOOGLE_APPLICATION_CREDENTIALS=$SERVICE_ACCOUNT_KEY \
        firebase deploy --project $FIREBASE_PROJECT --only functions:proxy_POST_PICKUPS && \
    popd

echo "All done! To see the functions deployed visit "
echo "https://console.firebase.google.com/project/$GCP_PROJECT/functions/list."