# TODO: fail if $RUBBISH_POSTGIS_CONNSTR is unset
# TODO: run this command for all of the functions (bash for loop)
# TODO: automate creating the backing bucket if it doesn't exist already
echo "Deploying cloud functions...⚙️"
gcloud functions deploy POST_pickups \
    --ingress-settings=internal-only \
    --runtime=python37 \
    --source=python/functions/ \
    --stage-bucket=functions-storage \
    --set-env-vars=RUBBISH_POSTGIS_CONNSTR=$RUBBISH_POSTGIS_CONNSTR \
    --trigger-http
