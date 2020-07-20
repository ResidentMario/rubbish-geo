# rubbish-geo

## overview

The `rubbish-geo` service provides a geospatial backend for the [Rubbish App](https://www.rubbish.love/).

Rubbish users perform "Rubbish runs", using the Rubbish grabber to clean up street curbs and logging the pickups in the Rubbish app. The `rubbish-geo` service slices provides statistical assays of this data that enables building reports and generating insights from what was found.

We hope to use it to eventually build out a community "trash map", helping organizations like welfare groups and business improvement districts better understand and prioritize cleanups efforts in their community.

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
│   ├── deploy_private_api.sh <- Deploys the cloud function private API.
│   ├── deploy_private_api.sh <- Deploys the cloud function private API.
│   └── deploy_auth_proxy.sh  <- Deploys the firebase functions auth proxy.
├── js/
│   └── functions/            <- Authentication proxy function code.
├── Dockerfile.database       <- Dockerfile bundling the local test db.
├── .travis.yml               <- Automated CI tests.
└── Dockerfile.database       <- Dockerfile bundling the local test db.
```

See the corresponding folders for setup instructions.

## architecture

![](https://i.imgur.com/a5Y5wQH.png)

The [Rubbish iOS application](https://apps.apple.com/us/app/rubbish-love-where-you-live/id1374702632) (the **client application**) is deployed via [Cloud Firestore](https://firebase.google.com/docs/firestore/), using a Firestore Firebase NoSQL database as its primary system of record. The client application is written in Swift, and the backend tooling in Node.JS. The Firebase SDK is used for handling authentication between the client and the backend services.

A [Firebase function](https://firebase.google.com/docs/functions/), the **authentication proxy**, listens for new run writes to the database. This function proxies a request to a [Cloud Function](https://console.cloud.google.com/functions/) **private API**, written in Python. The function (actually a thin wrapper over the `rubbish-geo` **client library**) processes the data and inserts it into the **rubbish-geo database**, a PostGIS database.

Adminstrative tasks are performed using the `rubbish-admin` CLI application.

The `rubbish-geo` service uses PostGIS, with client logic implemented in Python (taking full advantage of the great Python geospatial ecosystem: `geopandas`, `shapely`, `osmnx`). These services use GCP authentication for applications outside the VPC, such as the `rubbish-admin` database management CLI tool.

To bridge these two worlds&mdash;GCP services in Python, Firebase services in Node.JS&mdash;an authentication proxy is used. A [Firebase function](https://firebase.google.com/docs/functions/) listens for newly completed rubbish runs getting written into Firebase. This function, written in Node.JS, proxies a request to a [Cloud Function](https://console.cloud.google.com/functions/) based private API, written in Python. The function (actually a thin wrapper over the `rubbish-geo` cleint library) processes the data and inserts it into the database.

This design has several advantages:

* It allows us to continue to use only Firebase authentication for the client. A direct client-database connection would require sideloading mobile client authentication via GCP. This is a hard problem that the Firebase SDK solves for us!
* It makes maximal use of the functionless paradigm. Rubbish's application traffic is low-volume, but bursty, so using FaaS is more cost-effective and easier to manage than setting up dedicated services.
* Firebase functions do not support Python. Although Cloud Functions support for Firestore event listeners is in beta (which potentially eliminates the need for an auth proxy), it is difficult to test these locally. HTTP endpoints, on the other hand, are easily tested in the local environment using the `functions-framework` package.

This design has one notable disadvantage:

* Using a passthrough function like this introduces additional latency to the request.

## deployment

To deploy the services for the first time, make sure you are authenticated to the project you are deploying to, and have all of the things you need installed. Then run the following:

```bash
$ cd scripts/
# set these to the passwords you will use for the "postgres" (default) and "read_write" users in
# the database
$ export RUBBISH_GEO_POSTGRES_USER_PASSWORD=$1 RUBBISH_GEO_READ_WRITE_USER_PASSWORD=$1
# set this to 'dev' or 'prod', depending on what environment you are deploying into
$ export RUBBISH_GEO_ENV=prod
$ ./deploy_postgis_db.sh
# the connection string is output from the previous step.
$ export RUBBISH_POSTGIS_CONNSTR=$1
$ ./deploy_private_api.sh
# make sure you are authenticated to the right firebase project!
# TODO: what does this mean though?
$ ./deploy_auth_proxy.sh
```

Deploy scripts are idempotent, so you can easily deploy just one part of the stack if needed. This is useful if you're working on just one part of the stack and need to update just that part (for example, you need to run the database migrations again).

## testing

Instructions on how to run local tests for each of the major components are included in `README` files in the project subdirectories, refer to those for more details on that.

PRs are automatically tested using Travis CI (though this is currently disabled unfortunately).

This section discusses the (manual) integration test.

Make sure you have [a Firestore admin SDK token](https://firebase.google.com/docs/admin/setup#initialize-sdk) written to the `serviceAccountKey.json` file in the `js/` directory; you will need to this to connect to Firestore from your local machine. Then navigate to the `js/` directory and run `npm run-script test:dev`. This will write a test run to the database; to make sure that it did what you wanted it to do, check the logs in the GCP web console.
