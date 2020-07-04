# js

This directory contains the Firebase Firestore and Firebase Cloud Functions code handling data.

## Installation

First, configure the environment:

```bash
$ npm install --dev
$ npm install --global firebase-cli
$ firebase init
$ export FIRESTORE_EMULATOR_HOST="localhost:8080"
```

To start the emulators (need Firestore and Functions):

```bash
$ firebase emulators:start
```

For now you can test everything is working by running `node test.js`.
