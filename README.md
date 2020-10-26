# rubbish-geo

## overview

The `rubbish-geo` service provides a geospatial backend for the [Rubbish App](https://www.rubbish.love/).

Rubbish users perform "Rubbish runs", using the Rubbish grabber to clean up street curbs and logging the pickups in the Rubbish app. The `rubbish-geo` service slices provides statistical assays of this data that enables building reports and generating insights from what was found.

We hope to use it to eventually build out a community "trash map", helping organizations like welfare groups and business improvement districts better understand and prioritize cleanups efforts in their community.

## contents

```markdown
├── README.md
├── CONTRIBUTING.md
├── DEPLOY.md
├── python/
│   ├── rubbish_geo_client/   <- Python package encapsulating client logic.
│   ├── rubbish_geo_admin/    <- Python package encapsulating database admin.
│   ├── rubbish_geo_common/   <- Python package for shared code and fixtures.
│   ├── functions/            <- Functional API functions code.
│   └── migrations/           <- Database migrations.
├── scripts/                  <- Administrative scripts.
│   ├── deploy_postgis_db.sh  <- Database deploy and/or migration script.
│   ├── deploy_functional_api.sh        <- Deploys the functional API.
│   ├── deploy_db_listener.sh           <- Deploys the database listener.
│   ├── run_local_unit_tests.sh         <- Runs unit tests locally.
│   ├── run_dev_integration_tests.sh    <- Runs integration tests in dev.
│   └── run_local_integration_tests.sh  <- Runs integration tests locally.
├── js/
│   └── functions/            <- Database listener function code.
├── Dockerfile.database       <- Dockerfile bundling the local test db.
├── .travis.yml               <- Automated CI tests.
└── Dockerfile.database       <- Dockerfile bundling the local test db.
```

## architecture

![](https://i.imgur.com/eh3bvgC.png)

The [Rubbish iOS application](https://apps.apple.com/us/app/rubbish-love-where-you-live/id1374702632) (the **client application**) is deployed via [Cloud Firestore](https://firebase.google.com/docs/firestore/), using a Firestore Firebase NoSQL database as its primary system of record. The client application is written in Swift, and the backend tooling in NodeJS. The Firebase SDK is used for handling authentication between the client and the backend services.

A [Firebase function](https://firebase.google.com/docs/functions/) **database listener** listens for new run writes to the database. This function proxies the new data to a `POST_pickups` [Cloud Function](https://console.cloud.google.com/functions/), part of this service's **functional API**, written in Python. The function processes the data and inserts it into the **rubbish-geo database**, a PostGIS database.

On the read side, clients make `GET` requests to a *functional API* endpoint. Authentication is performed using a Firebase bearer token in the request header. Assuming the request passes the security check, the cloud function (actually a thin wrapper over the `rubbish-geo` **client library**) queries the database for the relevant records, performs some processing, and returns the result to the client. Future services (e.g. the aforementioned "trash map" community view) will communicate with the functional API similarly.

Adminstrative tasks are performed using the `rubbish-admin` **admin CLI**. The most common administrative task is writing new zones (street grids, via [OSMNX](https://github.com/gboeing/osmnx), e.g. "San Francisco, California") or sectors (polygonal areas of interest, e.g. "Lower Polk Community Benefit District") to the database.

The `rubbish-geo` service uses PostGIS, with client logic implemented in Python (taking full advantage of the great Python geospatial ecosystem: `geopandas`, `shapely`, `osmnx`). These services use GCP authentication for applications outside the VPC, such as the `rubbish-admin` database management CLI tool.

This two-step design, using both Cloud Functions and Firestore Functions, has several advantages:

* The client API is completely serverless, which makes scaling easy and helps keep costs down.
* The client only needs Firebase authentication credentials, e.g. they don't need any awareness of the GCP VPC.
* It enables the API logic to be written in Python (Firestore Functions are NodeJS-only), allowing us to use Python's rich geospatial tools for the backend logic and the middleware.
* It maximizes local testability. The `GET` API is testable using `functions-framework`, the `POST` API using the [Firestore Emulator Suite](https://firebase.google.com/docs/emulator-suite).

## deploy

See `DEPLOY.md` for first-deploy instructions.

## develop

See `CONTRIBUTING.md` for development notes.
