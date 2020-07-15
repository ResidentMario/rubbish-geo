# rubbish

The `rubbish` Python module and `rubbish-admin` CLI application.

## installation

You will need a version of `geopandas` off of master (one with [GH#1248](https://github.com/geopandas/geopandas/pull/1248) merged):

```bash
pip install git+https://github.com/geopandas/geopandas.git@3cba9
```

Then to install directly from GitHub:

```bash
pip install git+https://github.com/ResidentMario/rubbish-api-service#subdirectory=python
```

Depending on your platform, this may not work, or look like it's worked by fail later on due to linking issues in C dependencies. If that happens, you will need to download and install `miniconda` and use `conda install` to get the dependency packages first. Good luck.

Once you have it run `rubbish-admin --help` to see the available options. To import the library in Python do `import rubbish`.

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
cd python/rubbish/admin/tests
pytest tests.py
```

```bash
cd python/rubbish/client/tests
pytest tests.py
```

Note: you will need to rebuild the container (with `--no-cache` set) every time you update the database migrations.
