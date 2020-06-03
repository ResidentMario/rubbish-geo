"""
Admin client tests. Be sure to run scripts/init_test_db.sh first.
"""
import sqlalchemy as sa
import geopandas as gpd
from datetime import datetime, timedelta

import unittest
from unittest.mock import patch, call, Mock, ANY
import pytest

import rubbish
from rubbish.common.db import reset_db, db_sessionmaker
from rubbish.common.orm import Zone, ZoneGeneration
from rubbish.admin.zones import update_zone

import getpass
get_db = lambda: f"postgresql://{getpass.getuser()}@localhost/postgres"

def reset_auto_increment():
    with patch('rubbish.common.db.get_db', new=get_db):
        engine = db_sessionmaker()().bind
        engine.execute('ALTER SEQUENCE zones_id_seq RESTART WITH 1;')
        engine.execute('ALTER SEQUENCE zone_generations_id_seq RESTART WITH 1;')

def clean_db(f):
    def inner(*args, **kwargs):
        with patch('rubbish.common.db.get_db', new=get_db):
            reset_db()
            reset_auto_increment()
            f(*args, **kwargs)
            reset_db()
            reset_auto_increment()
    return inner

def alias_test_db(f):
    def inner(*args, **kwargs):
        with patch('rubbish.common.db.get_db', new=get_db), \
            patch('rubbish.admin.zones.get_db', new=get_db):
            f(*args, **kwargs)
    return inner

# psql -U alekseybilogur -h localhost postgres
class TestUpdateZone(unittest.TestCase):
    def setUp(self):
        with patch('rubbish.common.db.get_db', new=get_db):
            self.session = db_sessionmaker()()
        self.centerlines = gpd.read_file("fixtures/piedmont.geojson", driver='GeoJSON')

    @clean_db
    @alias_test_db
    def testNewZoneWrite(self):
        update_zone("Piedmont, California", "Foo, Bar", centerlines=self.centerlines)

        zones = self.session.query(Zone).all()
        assert len(zones) == 1
        assert zones[0].id == 1
        assert zones[0].name == "Foo, Bar"
        assert zones[0].osmnx_name == "Piedmont, California"

        zone_generations = self.session.query(ZoneGeneration).all()
        assert len(zone_generations) == 1
        assert zone_generations[0].id == 1
        assert zone_generations[0].generation == 0
        assert zone_generations[0].final_timestamp > datetime.now() - timedelta(hours=1)
        assert zone_generations[0].zone_id == zones[0].id

    @clean_db
    @alias_test_db
    def testExistingZoneIdempotentWrite(self):
        # idempotent in the sense that none of the centerlines have actually changed
        update_zone("Piedmont, California", "Foo, Bar", centerlines=self.centerlines)
        update_zone("Piedmont, California", "Foo, Bar", centerlines=self.centerlines)

        zones = self.session.query(Zone).all()
        assert len(zones) == 1

        zone_generations = self.session.query(ZoneGeneration).all()
        assert len(zone_generations) == 2
        assert zone_generations[0].id == 1
        assert zone_generations[1].id == 2
