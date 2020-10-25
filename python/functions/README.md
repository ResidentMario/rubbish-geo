# python/functions

This directory contains the cloud functions defining the `rubbish-geo` functional API. Any client authenticated to the Rubbish GCP project can use this API to read from and write to the Rubbish geospatial service.

## installation

Installing the packages required by `rubbish-geo-admin` in `[develop]` mode installs everything you need for testing functions as well. See the `README` in the `python/` folder for details.

## testing

The functional API and database listener integration tests can be run via:

```bash
$ /scripts/run_local_integration_tests.sh
```
