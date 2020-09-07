#!/bin/bash
# Runs the integration tests in dev.
set -e

# Set this to the PostGIS database URI. This value will be read by rubbish.common.db_ops.get_db
# at function runtime.
# if [[ -z "$RUBBISH_POSTGIS_CONNSTR" ]]; then
#     echo "RUBBISH_POSTGIS_CONNSTR environment variable not set, exiting." && exit 1
# fi

echo "Setting environment variables..."
pushd ../ 1>&0 && RUBBISH_BASE_DIR=$(echo $PWD) && popd 1>&0
export GOOGLE_APPLICATION_CREDENTIALS=$RUBBISH_BASE_DIR/js/serviceAccountKey.json
export RUBBISH_GEO_ENV=dev
GCP_PROJECT=$(gcloud config get-value project)
REGION=us-central1  # currently a hardcoded value
POST_PICKUPS_URL=https://$REGION-$GCP_PROJECT.cloudfunctions.net/POST_pickups
GET_URL=https://$REGION-$GCP_PROJECT.cloudfunctions.net/GET

echo $GET_URL

echo "Running private API integration tests..."
# NOTE(aleksey): POST_pickups only allows internal traffic, so we can't test it directly like
# we can with GET.
# PRIVATE_API_HOST=$POST_PICKUPS_URL \
#     pytest $RUBBISH_BASE_DIR/python/functions/tests/tests.py -k POST_pickups
PRIVATE_API_HOST=$GET_URL \
    pytest $RUBBISH_BASE_DIR/python/functions/tests/tests.py -k GET
