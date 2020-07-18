# rubbish-geo

## overview

The `rubbish-geo` service provides a geospatial backend for the [Rubbish App](https://www.rubbish.love/). We hope to use it to eventually build out a community "trash map", helping neighborhood organizations like welfare and business improvement districts better understand and prioritize their impact and cleanups.

## architecture

![](https://i.imgur.com/FYMNKGz.png)

The [Rubbish iOS application](https://apps.apple.com/us/app/rubbish-love-where-you-live/id1374702632) is deployed via [Cloud Firestore](https://firebase.google.com/docs/firestore/), using a Firestore Firebase NoSQL database as its primary system of record. The client application is written in Swift, and the backend tooling in Node.JS. Importantly, the Firebase SDK is used for handling authentication between the client and the backend services.

The `rubbish-geo` service uses PostGIS, with client logic implemented in Python (taking full advantage of the great Python geospatial ecosystem: `geopandas`, `shapely`, `osmnx`). These services use GCP authentication for applications outside the VPC, such as the `rubbish-admin` database management CLI tool.

To bridge these two worlds&mdash;GCP services in Python, Firebase services in Node.JS&mdash;an authentication proxy is used. A [Firebase function](https://firebase.google.com/docs/functions/) listens for newly completed rubbish runs getting written into Firebase. This function, written in Node.JS, proxies a request to a [Cloud Function](https://console.cloud.google.com/functions/) based private API, written in Python. The function (actually a thin wrapper over the `rubbish-geo` cleint library) processes the data and inserts it into the database.

This design has several advantages:

* It allows us to continue to use only Firebase authentication for the client. A direct client-database connection would require sideloading mobile client authentication via GCP. This is a hard problem that the Firebase SDK solves for us!
* It makes maximal use of the functionless paradigm. Rubbish's application traffic is low-volume, but bursty, so using FaaS is more cost-effective and easier to manage than setting up dedicated services.
* Although Cloud Functions support for Firestore event listeners is in beta (which potentially eliminates the need for an auth proxy), it is still currently not possible to test this locally. HTTP endpoints, on the other hand, are easily tested in the local environment using the `functions-framework` package.

This design has one notable disadvantage:

* Using a passthrough function like this introduces additional latency.

## contents

```markdown
├── LICENSE
├── README.md                 <- You're reading it!
├── python/
│   ├── rubbish_geo_client/   <- Python package encapsulating client logic.
│   ├── rubbish_geo_admin/    <- Python package encapsulating database admin.
│   ├── rubbish_geo_common/   <- Python package for shared code, e.g. test utils.
│   ├── functions/            <- Private API functions code.
│   └── migrations/           <- Database migrations (managed with alembic).
├── scripts/                  <- Administrative scripts.
│   ├── deploy_postgis_db.sh  <- Database deploy and/or migration script.
│   └── deploy_private_api.sh <- Deploys the cloud function private API.
├── js/                       <- Cloud functions (TODO).
├── Dockerfile.database       <- Dockerfile bundling the local test db.
├── .travis.yml               <- Automated CI tests.
└── Dockerfile.database       <- Dockerfile bundling the local test db.
```

See the corresponding folders for setup instructions.
