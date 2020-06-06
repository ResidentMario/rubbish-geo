#!/bin/bash
set -e

# prerequisite to running this script is having postgres and postgis installed locally
# on macOS this can be done via:
# > brew install postgres; brew install postgis
# TODO: move these instructions to a README
# TODO: why is /dev/null redirection not working as expected?

# HACK(aleksey): running this script while inside of a conda environment causes the PostGIS loading
# process to fail because PostGIS looks for its init files in the wrong place. Very weird
# interaction. However, we still need to have alembic installed to be able to perform the
# migration. And we can't init into a conda environment either because running a script in a shell
# is non-interactive. So for now you just have to run the alembic upgrade head line manually.

# initialize Postgres
# PGDATA envvar is required by pg_ctl status
RUBBISH_PGSTATUS=$(pg_ctl status -D /usr/local/var/postgres) || true
echo $RUBBISH_PGSTATUS
if [[ $RUBBISH_PGSTATUS == *"PID"* ]]; then
    echo "Postgres is already running, skipping initialization..."
else
    pg_ctl -D /usr/local/var/postgres start ||
    (echo "Could not start Postgres, are you sure it's installed?" && exit 1)
fi
echo "FOO"

# initialize Rubbish database
CONNSTR=postgresql://$(whoami)@localhost/postgres
psql $CONNSTR -c "DROP DATABASE IF EXISTS rubbish;"
psql $CONNSTR -c "CREATE DATABASE rubbish;"
CONNSTR=postgresql://$(whoami)@localhost/rubbish

# enable postgis and set up migration script
POSTGIS_ENABLED=$(psql -qtAX $CONNSTR -c "SELECT extname FROM pg_extension WHERE extname LIKE 'postgis';")
if [[ $POSTGIS_ENABLED != "postgis" ]]; then
    psql $CONNSTR -c "CREATE EXTENSION postgis;"
fi

pushd ../ && RUBBISH=$(PWD) && popd
# NOTE(aleksey): uses "|"" as delimiter character because CONNSTR includes "/" characters
cat $RUBBISH/python/rubbish/common/alembic.ini |
    sed -E "s|sqlalchemy.url = [a-zA-Z:/_0-9@\.-]*|sqlalchemy.url = $CONNSTR|" > $RUBBISH/python/rubbish/common/test_alembic.ini
cd $RUBBISH/scripts/

# NOTE(aleksey): cannot run alembic op from here due to weird interactions with conda.
# cd $RUBBISH/python/rubbish/common && alembic -c test_alembic.ini upgrade head ||
#     echo "Failed to run migration, are you sure Alembic is installed?"
echo "Almost done! To finish setup navigate to common and run alembic -c test_alembic.ini upgrade head."
