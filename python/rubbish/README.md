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

To test you will need to have Postgres and PostGIS running locally, and have some other bits correctly sell as well. Unfortunately this is currently much more complicated than it needs to be because of environment issues. But see `scripts/init_test_db.sh` for some hints.

Assuming you have everything set up correctly you can then:

```bash
cd python/rubbish/admin/tests
pytest tests.py
```

```bash
cd python/rubbish/client/tests
pytest tests.py
```
