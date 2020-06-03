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

# initialize a clean copy of the database
pg_ctl -D /usr/local/var/postgres stop &>/dev/null || true
pg_ctl -D /usr/local/var/postgres start || (echo "Could not start Postgres, are you sure it's installed?" && exit 1)
CONNSTR=postgresql://$(whoami)@localhost/postgres
psql $CONNSTR -c "DROP DATABASE rubbish;" &>/dev/null
psql $CONNSTR -c "CREATE DATABASE rubbish;" &>/dev/null

# run the database migrations
psql $CONNSTR -c "CREATE EXTENSION postgis;" &>/dev/null || true
pushd ../ && RUBBISH=$(PWD) && popd
# NOTE: uses "|"" as delimiter character because CONNSTR includes "/" characters,
# Cf. https://backreference.org/2010/02/20/using-different-delimiters-in-sed/
cat $RUBBISH/python/rubbish/common/alembic.ini |
    sed -E "s|sqlalchemy.url = [a-zA-Z:/_0-9@\.-]*|sqlalchemy.url = $CONNSTR|" > $RUBBISH/python/rubbish/common/test_alembic.ini
cd $RUBBISH/python/rubbish/common && alembic -c test_alembic.ini upgrade head ||
    echo "Failed to run migration, are you sure Alembic is installed?"
cd $RUBBISH/scripts/
