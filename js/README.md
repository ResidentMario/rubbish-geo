# js

This directory contains the Firebase Firestore and Firebase Cloud Functions code handling data.

## installation

```bash
$ npm install --dev
$ npm install --global firebase-cli
$ firebase init
```

## testing

Testing the function locally requires:

* Firebase Functions and Firestore emulators up and running.
* A PostGIS database up and running and listening on port 5432.

To start the emulators:

```bash
$ export FIRESTORE_EMULATOR_HOST="localhost:8080"
$ firebase emulators:start
```

For instructions on starting the test PostGIS database refer to the `README` in the `python` folder.

Assuming these conditions are satisfied, you can run the tests locally by executing `npm run-script test`.
