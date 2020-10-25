# js

This directory contains the `rubbish-geo` authentication proxy. This [Firebase Function](https://firebase.google.com/docs/functions/get-started) serves two purposes:

1. It listens to writes to the `RubbishRunStory` collection in Firestore, handing off data to the `POST_pickups` cloud function for processing and writing into the `rubbish-geo` PostGIS database.
2. In the future, it will act as an intermediary between the iOS client and the `rubbish-geo` service.

## installation

```bash
$ npm install --dev
$ npm install --global firebase-cli
$ firebase init
```

## configuration

This function uses Firebase's [environment configuration](https://firebase.google.com/docs/functions/config-env) toolchain to pass in the URL of the functional API endpoint this function will call into.

Any HTTPS-triggered cloud functions you stand up in a GCP project are assigned an HTTPS address with a name like `https://$REGION-$GCP_PROJECT.cloudfunctions.net/$FUNCTION_NAME` (see the [Cloud Functions page](https://console.cloud.google.com/functions/list) in the web console for exact details). The first time you configure this service in an account, you will need to add this address as a Firebase environment secret by running:

```bash
$ firebase functions:config:set functional_api.post_pickups_url=https://$REGION-$GCP_PROJECT.cloudfunctions.net/POST_pickups
$ firebase functions:config:get > .runtimeconfig.json
```

This environment secret is visible to all authorized users (run `firebase functions:config:get`) and retained for the lifetime of the project. Critically, this environment secret is passed into your Firebase Functions as well&mdash;we use it to configure functional API access from within the function.

You should only need to run this once.

## testing

Testing the function locally requires:

* Firebase Functions and Firestore emulators up and running; the Firestore emulator must be listening on port 8081 (since port 8080 is served for the cloud functions emulator).
* The functional API cloud functions emulator up and running and listening on port 8080.
* A PostGIS database up and running and listening on port 5432.

To start the emulators:

```bash
$ npm run-script emulators:start
```

For instructions on starting the functional API emulator refer to the `README` in the `python/functions` folder.

For instructions on starting the test PostGIS database refer to the `README` in the `python` folder.

Assuming these conditions are satisfied, you can run the tests locally by executing `npm run-script test`.
