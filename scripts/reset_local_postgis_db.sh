#!/bin/bash
# Helper script that resets the local PostGIS database image.
set -e

POSTGRES_DB_IS_UP=$(docker ps \
    --filter "name=rubbish-db-container" --filter "status=running" \
    --format "{{.Ports}}")
if [[ ! -z "$POSTGRES_DB_IS_UP" ]]; then
    echo "Removing existing PostGIS database container..."
    docker stop rubbish-db-container
    docker rm rubbish-db-container
fi
echo "Starting new PostGIS database container..."
docker run -d \
    --name rubbish-db-container \
    -e POSTGRES_DB=rubbish \
    -e POSTGRES_USER=rubbish-test-user \
    -e POSTGRES_PASSWORD=polkstreet \
    -p 5432:5432 rubbish-db:latest
./wait_for_postgres.sh
pushd ../python/migrations && \
    docker exec -it rubbish-db-container alembic -c test_alembic.ini upgrade head && \
    popd
./wait_for_postgres.sh
pushd ../python/migrations && \
    docker exec -it rubbish-db-container alembic -c test_alembic.ini upgrade head && \
    popd
echo "PostGIS ready!"
