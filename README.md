# rubbish-api-service

This repository contains the code comprising Rubbish's PostGIS backend.

## admin

The admin CLI (`python/admin`) is used for performing administrative tasks on the database. Use `pip install python/admin` to get it. You will also need a version of `geopandas` off of master (one with [GH#1248](https://github.com/geopandas/geopandas/pull/1248) merged), which you can get with e.g.:

```bash
pip install git+https://github.com/geopandas/geopandas.git@3cba9
```

Once you have it run `rubbish-admin --help` to see the available options.

## client

The client (`python/client`) is used by the API service to interact with the database.
