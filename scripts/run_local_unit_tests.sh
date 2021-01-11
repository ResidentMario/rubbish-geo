#!/bin/bash
# Runs the unit tests locally.
set -e

./reset_local_postgis_db.sh

echo "Running Python unit tests..."
pushd ../ 1>&0 && export RUBBISH_BASE_DIR=$(echo $PWD) && popd 1>&0
pytest $RUBBISH_BASE_DIR/python/rubbish_geo_common/tests/tests.py
pytest $RUBBISH_BASE_DIR/python/rubbish_geo_client/tests/tests.py
pytest $RUBBISH_BASE_DIR/python/rubbish_geo_admin/tests/tests.py

echo "Stopping PostGIS container."
docker stop rubbish-db-container