# deploy

## Initial deploy

Note that it is currently only possible to deploy on macOS.

### Before you begin

1. Install the `gcloud` CLI (see the instructions [here](https://cloud.google.com/sdk/docs/install#installation_instructions)).
2. Authenticate to the [GCP project](https://cloud.google.com/resource-manager/docs/creating-managing-projects) you will deploy to. If you are a member of multiple projects, you can configure which one is currently active using `gcloud config configurations list` and `gcloud config configurations activate $PROJECT_ID`.

   Make sure the account you are logged into has administrator access to the project.
3. Install the `firebase` CLI (see the instructions [here](https://firebase.google.com/docs/cli#install_the_firebase_cli)).
4. Clone this repo.

### Instructions

1. Navigate to the `/js` folder and run `firebase init`. Target the project you will deploy into. When Firebase asks what features to install, select the Firestore, Functions, and Emulator options. Do not overwrite any files that already exist (Firebase will always ask for confirmation before doing so).
2. Navigate to [Project Settings](https://console.firebase.google.com/u/_/project/_/settings/serviceaccounts/adminsdk) in the Firebase web console and find the Firebase service account email (will be something like `firebase-adminsdk-$RANDOM@$PROJECT_ID.iam.gserviceaccount.com`). Click on "Generate new private key" (use default settings). Download the key file and place it at `js/serviceAccountKey.json`.

   Firebase will uses this private key to deploy.
3. If you do not have `jq` ([a CLI string parsing tool](https://stedolan.github.io/jq/)), install it: `brew install jq`.
4. Go to [Project Settings](https://console.firebase.google.com/u/1/project/rubbish-ee2d0/settings/general/ios:com.rubbish.rubbishapp) in the Firebase web console again. Find the web API key. Run `export WEB_API_KEY=$VALUE` in your terminal, replacing `$VALUE` with the web API key value.
5. Run `export RUBBISH_GEO_ENV=$VALUE`, where `$VALUE` is one of `dev` or `prod`, depending on whether this is a dev or a prod deployment.
6. Navigate to the `/scripts` directory in your terminal. Run `RUBBISH_GEO_POSTGRES_USER_PASSWORD=$VALUE1 RUBBISH_GEO_READ_WRITE_USER_PASSWORD=$VALUE2 ./deploy_postgis_db.sh`, replacing `$VALUE1` and `$VALUE2` with your preferred passwords for the `postgres` (default) and `read_write` (application) users, respectively.

    You may need to mark the shell script executable first: `chmod +x deploy_postgis_db.sh`.

    This will deploy the PostGIS database into your project, including any database migrations that are required. This may take a while.
7. Once the database is up, go to the [Cloud SQL](https://console.cloud.google.com/sql/instances) page in the GCP web console and find the Postgres instance you just deployed. Export the instance connection name to your terminal window: `export  RUBBISH_POSTGIS_CONNECTION_NAME=rubbish-ee2d0:us-west1:rubbish-geo-postgis-db-4197`.
8. Run `./deploy_functional_api.sh`. This will deploy the functional API. Again, expect to wait a few minutes before it finishes.

    You can verify that it succeeded by visiting the Cloud Functions page in the GCP web console: this should now have `POST_pickups` and `GET` entries.
9. Run `./deploy_db_listener.sh`. This will deploy the last bit of `rubbish-geo`: the database listener, responsible for keeping the user and analytics databases in sync.

## Upgrade flow

For instructions on upgrades and database migrations, refer to the instructions in [`CONTRIBUTING.md`](CONTRIBUTING.md).
