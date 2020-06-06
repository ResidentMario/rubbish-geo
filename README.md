# rubbish-api-service

`rubbish-api-service` contains all of the code used for interacting with the Rubbish analytics service.

## overview

The Rubbish analytics service backend is a Postgres database with the PostGIS extension enabled. Rubbish pickups are backfilled (from the Firestore application database) at the end of every rubbish run. Client applications can in turn query the database (via the Rubbish analytics API) to retrieve useful geospatial information from the service.

This repo contains the following service components:

* `python/rubbish/admin`&mdash;a `rubbish-admin` CLI usable for common database operations: configuring the database connection, connecting to the database directly (by shelling out to `psql`), reseting the database, and writing street grids (e.g. `San Francisco`) into the database.
* `python/rubbish/client`&mdash;a Python module (`import rubbish`) containing library functions for sending pickup data and exfiltrating pickup analytics.
* `python/functions`&mdash;cloud functions definitions used for Firebase to Postgres and client to Postgres communication.

See the corresponding folders for setup instructions.
