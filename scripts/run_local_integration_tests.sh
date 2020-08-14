#!/bin/bash
# Runs the integration tests locally.
# TODO: support running these tests remotely as well.
set -e

# Check ports.
for PORT in 5001 8080 8081
do
    PORT_IN_USE=$(nc -z 127.0.0.1 8080 && echo "IN USE" || echo "FREE")
    if [[ "$PORT_IN_USE" == "IN USE" ]]; then
        echo "Could not start script: port $PORT unavailable."
        echo "Before you run this script, ensure that ports 5001, 8080, and 8081 are free."
        exit 1
    fi
done

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

echo "Starting private API POST_pickups emulator..."
pushd ../ 1>&0 && RUBBISH_BASE_DIR=$(echo $PWD) && popd 1>&0
functions-framework --source $RUBBISH_BASE_DIR/python/functions/main.py \
    --port 8081 --target POST_pickups --debug &

echo "Starting authentication API emulator..."
npm run-script --prefix $RUBBISH_BASE_DIR/js/ emulators:start &

echo "Sleeping for five seconds to give the emulators time to start up..."
sleep 5

echo "Running private API integration test..."
pytest $RUBBISH_BASE_DIR/python/functions/tests/tests.py -k POST_pickups || \
    (kill -s SIGSTOP %1 && kill -s SIGSTOP %2 && exit 1)

echo "Running authentication proxy integration test..."
npm run-script --prefix $RUBBISH_BASE_DIR/js/ test:local || \
    (kill -s SIGSTOP %1 && kill -s SIGSTOP %2 && exit 1)

echo "Shutting down emulators..."
kill -s SIGSTOP %1
kill -s SIGSTOP %2