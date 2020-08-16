#!/bin/bash
# Run this script to deploy or redeploy the private API.
set -e

# Set this to the PostGIS database URI. This value will be read by rubbish.common.db_ops.get_db
# at function runtime.
if [[ -z "$RUBBISH_POSTGIS_CONNSTR" ]]; then
    echo "RUBBISH_POSTGIS_CONNSTR environment variable not set, exiting." && exit 1
fi
# Set this to the Rubbish environment, one of {dev, prod}. This value is used to ensure bucket
# name uniqueness.
if [[ -z "$RUBBISH_GEO_ENV" ]]; then
    echo "RUBBISH_GEO_ENV environment variable not set, exiting." && exit 1
fi

# Create the following folder structure defining the cloud function:
#
# rubbish_geo_private_api.[0-9]{6}/
# ├── main.py
# ├── rubbish_geo_common
# ├── rubbish_geo_client
# └── requirements.txt
#
# The Rubbish-specific libraries are vendored into the function. Cf.
# https://cloud.google.com/functions/docs/writing/specifying-dependencies-python
echo "Creating temporary directory...📁"
pushd ../ 1>&0 && RUBBISH_BASE_DIR=$(echo $PWD) && popd 1>&0
TMPDIR=$(mktemp -d /tmp/rubbish_geo_private_api.XXXXXX)
for PKGNAME in rubbish_geo_common rubbish_geo_client
do
    cp -rf $RUBBISH_BASE_DIR/python/$PKGNAME/$PKGNAME $TMPDIR/
done
cp $RUBBISH_BASE_DIR/python/functions/main.py $TMPDIR/main.py
cp $RUBBISH_BASE_DIR/python/functions/requirements.txt $TMPDIR/requirements.txt
cp $RUBBISH_BASE_DIR/python/functions/.gcloudignore $TMPDIR/.gcloudignore

# Deploying cloud functions from the local filesystem in this manner requires creating a backing
# bucket on GCS and writing the contents to there. If this bucket doesn't already exist, we need
# to create it first.
echo "Checking buckets...🍯"
GCS_STAGE_BUCKET=gs://rubbish-private-api-stage-bucket-$RUBBISH_GEO_ENV
GCS_BUCKETS=$(gsutil ls)
echo $GCS_BUCKETS | grep $GCS_STAGE_BUCKET 1>&0 && GCS_STAGE_BUCKET_EXISTS=0 ||
    GCS_STAGE_BUCKET_EXISTS=1
if [[ GCS_STAGE_BUCKET_EXISTS -eq 0 ]]; then
    echo "Using existing bucket for functions storage."
else
    echo "The backing bucket does not exist yet, creating now..."
    gsutil mb $GCS_STAGE_BUCKET
fi

# Finally we are ready to deploy our functions.
echo "Deploying cloud functions...⚙️"
GOOGLE_APPLICATION_CREDENTIALS=$RUBBISH_BASE_DIR/js/serviceAccountKey.json
SERVICE_ACCOUNT=$(cat $GOOGLE_APPLICATION_CREDENTIALS | jq -r '.client_email')
gcloud functions deploy POST_pickups \
    --ingress-settings=internal-only \
    --runtime=python37 \
    --source=$TMPDIR \
    --stage-bucket=$GCS_STAGE_BUCKET \
    --set-env-vars=RUBBISH_POSTGIS_CONNSTR=$RUBBISH_POSTGIS_CONNSTR \
    --service-account=$SERVICE_ACCOUNT \
    --trigger-http
echo "Deployed function POST_pickups successfully. ✔️"

# NOTE(aleksey): this function will be called by clients (application end users) that have
# firebase perms but no GCP perms. We disable VPC access control (ACL) (--ingress-settings=all)
# and IAM access control (RBAC) (add-iam-policy-binding GET --member=allUsers) to turn off GCP
# permissions boundaries. Authentication is handled instead within the function using the
# firebase user identity token verification flow instead.
#
# TODO: It might be possible to enable both GCP auth and Firebase auth.
gcloud functions deploy GET \
    --ingress-settings=all \
    --runtime=python37 \
    --source=$TMPDIR \
    --stage-bucket=$GCS_STAGE_BUCKET \
    --set-env-vars=RUBBISH_POSTGIS_CONNSTR=$RUBBISH_POSTGIS_CONNSTR \
    --service-account=$SERVICE_ACCOUNT \
    --trigger-http
gcloud functions add-iam-policy-binding GET --member=allUsers --role=roles/cloudfunctions.invoker
echo "Deployed function GET successfully. ✔️"
echo "All done! To see the functions deployed visit https://console.cloud.google.com/functions/."