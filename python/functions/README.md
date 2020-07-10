# js

This directory contains the cloud function definitions. These functions are used to handle writes to and reads from the PostGIS backend by the Rubbish client application. The current list of functions is:

* `write_pickups`&mdash;Writes a Rubbish run with a list of pickups into the database.

## installation

If you haven't already, install the `rubbish` package (see the `README` in the `python/rubbish` folder for details).

```bash
$ pip install -r requirements.txt
```

## testing

Testing uses the functions emulator provided by the `functions-framework` package. Make sure you have a PostGIS database up and listening on port 5432 (see the `README` in `python/rubbish` for instructions) and have either exported the connection string as an envar (`export RUBBISH_POSTGIS_CONNSTR=$CONNSTR`) or have already saved it to disk via `rubbish-admin set-db $CONNSTR`.

Then, to run the tests locally:

```bash
pytest tests/tests.py
```

You can also try submitting payloads to the cloud functions directly:

```bash
# TODO: replace this with a real payload
$ functions-framework --target write_pickups --debug
$ curl -X POST -H "Content-Type: application/json" -d '{"1": "2"}' localhost:8080
```
