#!/bin/bash
# Runs the integration tests in dev.
set -e

# Set this to the read_write user password.
if [[ -z "$RUBBISH_GEO_READ_WRITE_USER_PASSWORD" ]]; then
    echo "RUBBISH_GEO_READ_WRITE_USER_PASSWORD environment variable not set, exiting." && exit 1
fi
# The connection name will be a string in the format "PROJECT:REGION:INSTANCE". It is available
# on the "Overview" page in the Cloud SQL web console.
if [[ -z "$RUBBISH_POSTGIS_CONNECTION_NAME" ]]; then
    echo "RUBBISH_POSTGIS_CONNECTION_NAME environment variable not set, exiting." && exit 1
fi

# Stand up the Cloud SQL Proxy.
echo "Starting cloud sql proxy..."
# Use port 5433 to avoid collisions with any local Postgres instance (which default to 5432)
PORT_IN_USE=$(nc -z 127.0.0.1 5433 && echo "IN USE" || echo "FREE")
if [[ "$PORT_IN_USE" == "IN USE" ]]; then
    echo "Could not start script: port 5433 unavailable."
    exit 1
fi
pushd ../ 1>&0 && RUBBISH_BASE_DIR=$(echo $PWD) && popd 1>&0
ls $RUBBISH_BASE_DIR | grep cloud_sql_proxy && CLOUD_SQL_PROXY_INSTALLED=0 || \
    CLOUD_SQL_PROXY_INSTALLED=1
if [[ CLOUD_SQL_PROXY_INSTALLED -eq 1 ]]; then
    echo "Downloading cloud sql proxy..."
    # NOTE: this URL assumes you are on a macOS machine, for a Linux link refer to
    # https://cloud.google.com/sql/docs/postgres/quickstart-proxy-test
    curl -o $RUBBISH_BASE_DIR/cloud_sql_proxy \
        https://dl.google.com/cloudsql/cloud_sql_proxy.darwin.amd64
    chmod +x $RUBBISH_BASE_DIR/cloud_sql_proxy
fi
$RUBBISH_BASE_DIR/cloud_sql_proxy -instances=$RUBBISH_POSTGIS_CONNECTION_NAME=tcp:5433 &
RUBBISH_POSTGIS_CONNSTR=postgresql://read_write:$RUBBISH_GEO_READ_WRITE_USER_PASSWORD@localhost:5433/rubbish

# Set this to the Firebase project's web API key:
# https://console.firebase.google.com/project/_/settings/general.
if [[ -z "$WEB_API_KEY" ]]; then
    echo "WEB_API_KEY environment variable not set, exiting." && exit 1
fi

echo "Setting environment variables..."
pushd ../ 1>&0 && RUBBISH_BASE_DIR=$(echo $PWD) && popd 1>&0
export GOOGLE_APPLICATION_CREDENTIALS=$RUBBISH_BASE_DIR/js/serviceAccountKey.json
export RUBBISH_GEO_ENV=dev
GCP_PROJECT=$(gcloud config get-value project)
REGION=us-central1  # currently a hardcoded value
# POST_PICKUPS_URL=https://$REGION-$GCP_PROJECT.cloudfunctions.net/POST_pickups
GET_URL=https://$REGION-$GCP_PROJECT.cloudfunctions.net/GET

echo "Running private API integration tests..."
# NOTE(aleksey): POST_pickups only allows internal traffic, so we can't test it directly like
# we can with GET.
# PRIVATE_API_HOST=$POST_PICKUPS_URL \
#     pytest $RUBBISH_BASE_DIR/python/functions/tests/tests.py -k POST_pickups
PRIVATE_API_HOST=$GET_URL RUBBISH_POSTGIS_CONNSTR=$RUBBISH_POSTGIS_CONNSTR \
    pytest $RUBBISH_BASE_DIR/python/functions/tests/tests.py -k GET

echo "Shutting down cloud sql proxy..."
kill -s SIGSTOP %1