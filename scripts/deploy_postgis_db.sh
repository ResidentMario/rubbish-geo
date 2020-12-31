#!/bin/bash
# Run this script to deploy or redeploy the PostGIS database.
set -e

# Check that jq is installed; we use this tool to parse gcloud outputs.
jq --help >/dev/null || (echo "jq is not installed, 'brew install jq' to get it." && exit 1)

# Set this to the postgres user password.
if [[ -z "$RUBBISH_GEO_POSTGRES_USER_PASSWORD" ]]; then
    echo "RUBBISH_GEO_POSTGRES_USER_PASSWORD environment variable not set, exiting." && exit 1
fi
# Set this to the read_write user password.
if [[ -z "$RUBBISH_GEO_READ_WRITE_USER_PASSWORD" ]]; then
    echo "RUBBISH_GEO_READ_WRITE_USER_PASSWORD environment variable not set, exiting." && exit 1
fi
# Set this to the Rubbish environment, one of {dev, prod}. This value is used to ensure bucket
# name uniqueness.
if [[ -z "$RUBBISH_GEO_ENV" ]]; then
    echo "RUBBISH_GEO_ENV environment variable not set, exiting." && exit 1
fi

echo "Checking databases...💽"
SQL_INSTANCES=$(gcloud sql instances list)
echo $SQL_INSTANCES | grep "rubbish-geo-postgis-db" 1>&0 && INSTANCE_EXISTS=0 || INSTANCE_EXISTS=1
if [[ INSTANCE_EXISTS -eq 0 ]]; then
    echo "Database instance already exists, skipping ahead to configuration."
    INSTANCE_NAME=$(gcloud sql instances list --format=json | \
        jq -r '.[] | .name' | grep rubbish-geo-postgis-db)
else
    echo "Database instance does not exist yet, creating now (this will take some time)..."
    INSTANCE_NAME="rubbish-geo-postgis-db-$RANDOM"
    gcloud sql instances create $INSTANCE_NAME \
        --database-version=POSTGRES_12 \
        --tier db-g1-small \
        --region="us-west1"
    gcloud sql users set-password postgres --instance=$INSTANCE_NAME \
        --password=$RUBBISH_GEO_POSTGRES_USER_PASSWORD
    # NOTE(aleksey): instance names are reserved for a while even after deletion, thus the $RANDOM
    # to avoid collisions.
fi

echo "Configuring connection to the database instance...🔌"
MY_IP=$(curl -s ifconfig.me)
gcloud sql instances patch $INSTANCE_NAME --authorized-networks=$MY_IP --quiet
INSTANCE_IP=$(gcloud sql instances describe $INSTANCE_NAME --format=json | \
    jq -r '.ipAddresses[0].ipAddress')
POSTGRES_DB_CONNSTR=postgresql://postgres:$RUBBISH_GEO_POSTGRES_USER_PASSWORD@$INSTANCE_IP/postgres
RUBBISH_DB_CONNSTR=postgresql://postgres:$RUBBISH_GEO_POSTGRES_USER_PASSWORD@$INSTANCE_IP/rubbish
RW_RUBBISH_DB_CONNSTR=postgresql://read_write:$RUBBISH_GEO_READ_WRITE_USER_PASSWORD@$INSTANCE_IP/rubbish

echo "Checking if the instance has a Rubbish database...🗄️"
INSTANCE_DBS=$(gcloud sql databases list --instance $INSTANCE_NAME --format=json | \
    jq -r '.[] | .name')
echo $INSTANCE_DBS | grep "rubbish" 1>&0 && DB_EXISTS=0 || DB_EXISTS=1
if [[ DB_EXISTS -eq 0 ]]; then
    echo "Rubbish database already exists, skipping ahead to migrations."
else
    echo "Rubbish database does not exist yet, creating now..."
    psql $POSTGRES_DB_CONNSTR -c "CREATE DATABASE rubbish;"
    psql $RUBBISH_DB_CONNSTR -c "CREATE EXTENSION postgis;"
    psql $RUBBISH_DB_CONNSTR -c "CREATE USER read_write WITH PASSWORD '$RUBBISH_GEO_READ_WRITE_USER_PASSWORD';"
fi

echo "Running database migrations...💩"
pushd ../ 1>&0 && RUBBISH_BASE_DIR=$(echo $PWD) && popd 1>&0
TMPDIR=$(mktemp -d /tmp/rubbish_geo_functional_api.XXXXXX)
cp -rf $RUBBISH_BASE_DIR/python/migrations/ $TMPDIR/migrations
cp $RUBBISH_BASE_DIR/python/alembic.ini $TMPDIR/alembic.ini
cat $TMPDIR/alembic.ini | \
    sed -E "s|sqlalchemy.url = [a-zA-Z:/_0-9@\.-]*|sqlalchemy.url = $RW_RUBBISH_DB_CONNSTR|" > \
    $TMPDIR/remote_alembic.ini
pushd $TMPDIR && alembic -c remote_alembic.ini upgrade head && popd

# NOTE(aleksey): connecting to this instance requires cloud_sql_proxy.
echo "Adding this database to your local database profiles...✏️"
CONNAME=$(gcloud sql instances describe $INSTANCE_NAME --format=json | jq -r '.connectionName')
rubbish-admin set-db \
    $RUBBISH_GEO_ENV \
    postgresql://read_write:$RUBBISH_GEO_READ_WRITE_USER_PASSWORD@localhost:5432/rubbish \
    gcp \
    --conname $CONNAME

echo "Done! If this database is local you can now connect to it by running: "
echo "\$ rubbish-admin connect --profile $RUBBISH_GEO_ENV"
echo "To connect directly, use the following database connection string: $RW_RUBBISH_DB_CONNSTR."
echo "If this database is on GCP you will need to deploy the GCP SQL Proxy first. See futher: "
echo "https://cloud.google.com/sql/docs/postgres/sql-proxy"