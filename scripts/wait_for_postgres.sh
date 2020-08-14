#!/bin/bash
# Waits until the PostGIS database is ready.
while ! pg_isready -h localhost -p 5432 -q -U rubbish-test-user; do
  >&2 echo "Postgres is unavailable - sleeping"
  # docker ps
  sleep 1
done