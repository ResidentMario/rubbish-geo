# contributing

## Project setup

Follow the instructions in `DEPLOY.md` to set up the CLI tools (`gcloud`, `firebase`, `jq`) and environment secrets (service accounts keys) that you will need.

## Python library development

These instructions refer to the project's Python libraries (`rubbish_geo_{common, client, admin}`).

### installation

Note that you can currently only complete the required setup using `conda`.

The `rubbish_geo_common` module is a peer dependency of both the admin and the client modules, so you'll want to first install that by running:

```bash
$ pip install git+https://github.com/ResidentMario/rubbish-api-service#subdirectory=python/rubbish_geo_common
```

Then to install the `rubbish_geo_client` module (this contains all of the library functions defining the `rubbish-geo` GET and PUT APIs):

```bash
$ pip install git+https://github.com/ResidentMario/rubbish-api-service#subdirectory=python/rubbish_geo_client
```

Unfortunately `rubbish_geo_admin` is a little trickier to install due to its dependency on `rtree`, which is *not* `pip`-installable (see [rtree GH#147](https://github.com/Toblerity/rtree/issues/147) for context). At this time you can only successfully install this package from inside of a `conda` environment:

```bash
$ conda install -c conda-forge rtree
$ pip install git+https://github.com/ResidentMario/rubbish-api-service#subdirectory=python/rubbish_geo_admin
```

To test that this installed successfully, try running `rubbish-admin --help`&mdash;this should list the options available in the CLI.

### testing

Before you can run the tests for the first time, you will first need to build the database Docker image:

```bash
# PWD=rubbish-geo
$ docker build --file Dockerfile.database --tag rubbish-db .
```

After this you can run the Python unit tests via:

```bash
# PWD=rubbish-geo/scripts
$ ./run_local_unit_tests.sh
```

This script will launch (or restart) the database container the container automatically, so no `docker run` is necessary.

### migrations

Database migrations using Alembic are located in the `migrations` subfolder. These are performed for you automatically when running tests.

### ci

CI is currently disabled [due to an outstanding bug](https://github.com/ResidentMario/rubbish-geo/issues/51).

### deployment

Changes to the libraries that affect the functional API will require redeploying it (see the next section for details).

## Python function development

The functional API is a cloud function written in Python.

### installation

If you've installed `rubbish_geo_admin[develop]`, you already have all of the packages you need to develop on the functions.

### testing

The function API can be tested locally using a set of integration tests using the [functions-framework-python](https://github.com/GoogleCloudPlatform/functions-framework-python). To run these tests:

```bash
# PWD=rubbish-geo/scripts
$ RUBBISH_GEO_ENV=local \
    WEB_API_KEY=$KEY \
    ./run_local_integration_tests.sh
```

There are also remote integration tests, which use the `dev` environment:

```bash
# PWD=rubbish-geo/scripts
$ RUBBISH_GEO_ENV=dev \
    RUBBISH_POSTGIS_CONNECTION_NAME=$NAME \
    RUBBISH_GEO_READ_WRITE_USER_PASSWORD=$PWD \
    WEB_API_KEY=$KEY \
    ./run_dev_integration_tests.sh
```

### deployment

Deployment is via:

```bash
# PWD=rubbish-geo/scripts
$ RUBBISH_GEO_ENV=$env \
    RUBBISH_GEO_READ_WRITE_USER_PASSWORD=$PWD \
    RUBBISH_POSTGIS_CONNECTION_NAME=$NAME \
    ./deploy_functional_api.sh
```

This will replace the prior version of the functions with the new ones.

## Database management

### migrations

To perform remote database migrations, rerun the database deploy script:

```bash
# PWD=rubbish-geo/scripts
RUBBISH_GEO_POSTGRES_USER_PASSWORD=$PWD \
    RUBBISH_GEO_READ_WRITE_USER_PASSWORD=$PWD \
    RUBBISH_GEO_ENV=$ENV \
    ./deploy_postgis_db.sh
```

## JS function development

The database listener that keeps the user and analytics databases in sync is a Firebase function written in JavaScript.

### installation

Navigate to the `js/` folder and run `npm install --develop`.

### testing

To run local integration tests (uses the [Firestore Emulator](https://firebase.google.com/docs/rules/emulator-setup)):

```bash
# PWD=rubbish-geo/scripts
$ RUBBISH_GEO_ENV=local \
    WEB_API_KEY=$KEY \
    ./run_local_integration_tests.sh
```

To run the remote tests:

```bash
# PWD=rubbish-geo/scripts
$ RUBBISH_GEO_ENV=dev \
    RUBBISH_POSTGIS_CONNECTION_NAME=$NAME \
    RUBBISH_GEO_READ_WRITE_USER_PASSWORD=$PWD \
    WEB_API_KEY=$KEY \
    ./run_dev_integration_tests.sh
```

### deployment

Rerun the deploy script to upgrade the listener to the latest version:

```bash
# PWD=rubbish-geo/scripts
$ ./deploy_db_listener.sh
```
