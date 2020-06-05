"""
Methods useful for testing used in both admin and client tests.
"""
import sqlalchemy as sa
import geopandas as gpd
from datetime import datetime, timedelta
import getpass

import unittest
from unittest.mock import patch, call, Mock, ANY
import pytest

import rubbish
from rubbish.common.db_ops import reset_db, db_sessionmaker

get_db = lambda: f"postgresql://{getpass.getuser()}@localhost/postgres"

def reset_auto_increment():
    with patch('rubbish.common.db_ops.get_db', new=get_db):
        engine = db_sessionmaker()().bind
        engine.execute('ALTER SEQUENCE zones_id_seq RESTART WITH 1;')
        engine.execute('ALTER SEQUENCE zone_generations_id_seq RESTART WITH 1;')
        engine.execute('ALTER SEQUENCE blockface_statistics_id_seq RESTART WITH 1;')
        engine.execute('ALTER SEQUENCE pickups_id_seq RESTART WITH 1;')
        engine.execute('ALTER SEQUENCE sectors_id_seq RESTART WITH 1;')
        engine.execute('ALTER SEQUENCE centerlines_id_seq RESTART WITH 1;')

def clean_db(f):
    def inner(*args, **kwargs):
        with patch('rubbish.common.db_ops.get_db', new=get_db):
            reset_db()
            reset_auto_increment()
            f(*args, **kwargs)
            reset_db()
            reset_auto_increment()
    return inner

def alias_test_db(f):
    def inner(*args, **kwargs):
        with patch('rubbish.common.db_ops.get_db', new=get_db), \
            patch('rubbish.admin.ops.get_db', new=get_db):
            f(*args, **kwargs)
    return inner
