# python

Note that this README is specific to the `rubbish-geo` Python modules. For details on the Python cloud functions refer to the README in the corresponding subfolder.

## installation

The `rubbish_geo_common` module is a peer dependency of both the admin and the client modules, so you'll want to first install that by running:

```bash
$ pip install git+https://github.com/ResidentMario/rubbish-api-service#subdirectory=python/rubbish_geo_common
```

Then to install the `rubbish_geo_client` module (this contains all of the library functions defining the `rubbish-geo` GET and PUT APIs):

```bash
$ pip install git+https://github.com/ResidentMario/rubbish-api-service#subdirectory=python/rubbish_geo_client
```

Unfortunately `rubbish_geo_admin` is a little trickier to install due to its dependency on `rtree`, which is *not* `pip`-installable (see [rtree GH#147](https://github.com/Toblerity/rtree/issues/147) for context). At this time you can only successfully install this package from inside of a `conda` environment:

```bash
$ conda install -c conda-forge rtree
$ pip install git+https://github.com/ResidentMario/rubbish-api-service#subdirectory=python/rubbish_geo_admin
```

To test that this installed successfully, try running `rubbish-admin --help`&mdash;this should list the options available in the CLI.

## testing

Before you can run the tests for the first time, you will first need to build the database Docker image:

```bash
# PWD=rubbish-geo
$ docker build --file Dockerfile.database --tag rubbish-db .
```

After this you can run the Python unit tests via:

```bash
$ /scripts/run_local_unit_tests.sh
```

This script will launch (or restart) the database container the container automatically, so no `docker run` is necessary.

## migrations

Note that you will need to rebuild the container with `--no-cache` set every time you update the database migrations.
