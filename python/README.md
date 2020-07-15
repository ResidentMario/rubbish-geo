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

You will need to have Docker installed and running locally. Then, run the following from repo root to initialize a local DB instance:

```bash
$ docker build --file Dockerfile.database --tag rubbish-db .
$ docker run -d \
    --name rubbish-db-container \
    -e POSTGRES_DB=rubbish \
    -e POSTGRES_USER=rubbish-test-user \
    -e POSTGRES_PASSWORD=polkstreet \
    -p 5432:5432 rubbish-db:latest
$ docker exec -it rubbish-db-container alembic -c test_alembic.ini upgrade head
```

This creates a PostGIS database listening on the port 5432 and runs the database migration on it to populate the database.

Assuming you have `psql` installed locally, you can verify that things are working as expected by running:

```bash
$ psql -U rubbish-test-user -h localhost -p 5432 rubbish
```

Finally, to run the tests:

```bash
$ cd python/rubbish/admin/tests
$ pytest tests.py
```

```bash
$ cd python/rubbish/client/tests
$ pytest tests.py
```

Note: you will need to rebuild the container (with `--no-cache` set) every time you update the database migrations.
