"""
Methods useful for testing used in both admin and client tests.
"""
from unittest.mock import patch
from datetime import datetime, timezone
import random
import os
import pathlib
import shutil

from shapely.geometry import LineString

from rubbish_geo_common.db_ops import reset_db
from rubbish_geo_common.consts import RUBBISH_TYPES

TEST_APP_DIR_TMPDIR = "/tmp/.rubbish_test_app_dir"

def get_app_dir():
    tmpdir = TEST_APP_DIR_TMPDIR
    if not os.path.exists(tmpdir):
        os.mkdir(tmpdir)
    return pathlib.Path(tmpdir)

def reset_app_dir(f):
    def inner(*args, **kwargs):
        tmpdir = TEST_APP_DIR_TMPDIR
        if os.path.exists(tmpdir):
            shutil.rmtree(tmpdir, ignore_errors=True)  # S0#303225
        f(*args, **kwargs)
    return inner

def get_db(profile=None):
    if 'RUBBISH_GEO_ENV' not in os.environ or os.environ['RUBBISH_GEO_ENV'] == 'local':
        return f"postgresql://rubbish-test-user:polkstreet@localhost:5432/rubbish", "local", "unset"
    elif os.environ['RUBBISH_GEO_ENV'] == 'dev':
        if 'RUBBISH_POSTGIS_CONNSTR' not in os.environ:
            raise ValueError(
                f"The 'RUBBISH_GEO_ENV' environment variable is set to non 'local' value "
                f"{os.environ['RUBBISH_GEO_ENV']!r}, but the 'RUBBISH_POSTGIS_CONNSTR' value "
                f"is unset. Set this value to the correct PostGIS instance connection string."
            )
        if 'RUBBISH_POSTGIS_CONNECTION_NAME' not in os.environ:
            raise ValueError(
                f"The 'RUBBISH_GEO_ENV' environment variable is set to non 'local' value "
                f"{os.environ['RUBBISH_GEO_ENV']!r}, but the 'RUBBISH_POSTGIS_CONNECTION_NAME' "
                f"value is unset. Set this value to the correct GCP connection name."
            )
        return (
            os.environ['RUBBISH_POSTGIS_CONNSTR'], "gcp",
            os.environ['RUBBISH_POSTGIS_CONNECTION_NAME']
        )
    else:
        raise ValueError(
            f"'RUBBISH_GEO_ENV' must be set to one of 'local' or 'dev', but found value "
            f"{os.environ['RUBBISH_GEO_ENV']!r} instead."
        )

def clean_db(f):
    """
    Wrapper function that resets the database, dropping all data and resetting all ID sequences.
    """
    def inner(*args, **kwargs):
        with patch('rubbish_geo_common.db_ops.get_db', new=get_db):
            reset_db('local')
            f(*args, **kwargs)
    return inner

def alias_test_db(f):
    """
    Wrapper function that overwrites database connection string methods to point to the local test
    database.
    """
    def inner(*args, **kwargs):
        with patch('rubbish_geo_common.db_ops.get_db', new=get_db):
            f(*args, **kwargs)
    return inner

def get_grid():
    # NOTE(aleksey): importing this here and not at the top level in order to avoid making
    # geopandas a package dependency. This is important because we need this package to be
    # installable inside a Cloud Function, which can only use pip for its dependencies. geopandas
    # has a dependency on rtree, which annoyingly can *only* be installed using conda, not pip.
    # Since geopandas is only used in test utilities, we can sidestep the problem by making it a
    # function-scoped import instead of a module import.
    import geopandas as gpd
    return gpd.GeoDataFrame(
        {
            'osmid': range(12),
            'name': [
                "0_0_0_1 Street", "0_1_0_2 Street", "0_0_1_0 Street", "1_0_2_0 Street",
                "2_0_2_1 Street", "2_1_2_2 Street", "2_2_1_2 Street", "1_2_0_2 Street",
                "1_0_1_1 Street", "0_1_1_1 Street", "1_2_1_1 Street", "2_1_1_1 Street"
            ],
            'zone_id': [1] * 12,
            'first_zone_generation': [1] * 12,
            'last_zone_generation': [None] * 12
        },
        geometry=[
            LineString([[0, 0], [0, 1]]),
            LineString([[0, 1], [0, 2]]),
            LineString([[0, 0], [1, 0]]),
            LineString([[1, 0], [2, 0]]),
            LineString([[2, 0], [2, 1]]),
            LineString([[2, 1], [2, 2]]),
            LineString([[2, 2], [1, 2]]),
            LineString([[1, 2], [0, 2]]),
            LineString([[1, 0], [1, 1]]),
            LineString([[0, 1], [1, 1]]),
            LineString([[1, 2], [1, 1]]),
            LineString([[2, 1], [1, 1]])
        ],
        crs="epsg:4326"
    )

def insert_grid(f):
    """
    Wrapper function that inserts the basic street grid centerline data into the database.
    """
    from rubbish_geo_admin import update_zone
    grid = get_grid()
    def inner(*args, **kwargs):
        with patch('rubbish_geo_common.db_ops.get_db', new=get_db):
            update_zone(
                "Grid City, California", "Grid City, California", 'local', centerlines=grid
            )
        f(*args, **kwargs)
    return inner

def valid_pickups_from_geoms(geoms, firebase_run_id='foo', curb=None):
    return [{
        'firebase_id': str(abs(hash(i))),
        'firebase_run_id': firebase_run_id,
        'type': random.choice(RUBBISH_TYPES),
        'timestamp': str(datetime.now().replace(tzinfo=timezone.utc).timestamp()),
        'curb': curb,
        'geometry': geom
    } for i, geom in enumerate(geoms)]
