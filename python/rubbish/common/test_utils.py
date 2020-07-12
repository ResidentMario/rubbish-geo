"""
Methods useful for testing used in both admin and client tests.
"""
from unittest.mock import patch
import warnings
from datetime import datetime, timezone
import random

import geopandas as gpd
from shapely.geometry import LineString

import rubbish
from rubbish.common.db_ops import reset_db, db_sessionmaker
from rubbish.admin.ops import update_zone
from rubbish.common.consts import RUBBISH_TYPES

def get_db(profile=None):
    return f"postgresql://rubbish-test-user:polkstreet@localhost:5432/rubbish"

def clean_db(f):
    """
    Wrapper function that resets the database, dropping all data and resetting all ID sequences.
    """
    def inner(*args, **kwargs):
        with patch('rubbish.common.db_ops.get_db', new=get_db):
            reset_db()
            f(*args, **kwargs)
    return inner

def alias_test_db(f):
    """
    Wrapper function that overwrites database connection string methods to point to the local test
    database.
    """
    def inner(*args, **kwargs):
        with patch('rubbish.common.db_ops.get_db', new=get_db), \
            patch('rubbish.admin.ops.get_db', new=get_db):
            f(*args, **kwargs)
    return inner

def get_grid():
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
    grid = get_grid()
    def inner(*args, **kwargs):
        with patch('rubbish.common.db_ops.get_db', new=get_db), \
            patch('rubbish.admin.ops.get_db', new=get_db):
            update_zone("Grid City, California", "Grid City, California", centerlines=grid)
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
