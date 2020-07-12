# python/functions

This directory contains the cloud functions defining the private `rubbish-geo` API. Any client authenticated to the Rubbish GCP project can use this API to read from and write to the Rubbish geospatial service.

## installation

If you haven't already, install the `rubbish` package (see the `README` in the `python/rubbish` folder for details).

```bash
$ pip install -r requirements.txt
```

## testing

Testing uses the functions emulator provided by the `functions-framework` package. Make sure you have a PostGIS database up and listening on port 5432 (see the `README` in `python/rubbish` for instructions) and have either exported the connection string as an envar (`export RUBBISH_POSTGIS_CONNSTR=$CONNSTR`) or have already saved it to disk via `rubbish-admin set-db $CONNSTR`. Then, run:

```bash
$ functions-framework --target POST_pickups --debug
```

Note that the functions emulator can only target a single function at a time (`target` only accepts a single argument). Replace `--target POST_pickups` with the name of the function you want to test. Then, to run the tests locally:

```bash
pytest tests/tests.py -k POST_pickups
```

You can also try submitting payloads to the cloud functions directly:

```bash
# assuming POST_pickups is listening
$ curl -X POST -H "Content-Type: application/json" -d '{}' localhost:8080
{"status": 200}
```
