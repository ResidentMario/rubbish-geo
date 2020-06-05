"""
Admin client tests. Be sure to run scripts/init_test_db.sh first.
"""
import sqlalchemy as sa
import geopandas as gpd
from datetime import datetime, timedelta

import unittest
from unittest.mock import patch
import pytest

import rubbish
from rubbish.common.db_ops import reset_db, db_sessionmaker
from rubbish.common.orm import Zone, ZoneGeneration, Centerline
from rubbish.common.test_utils import get_db, clean_db, alias_test_db
from rubbish.admin.ops import update_zone

class TestUpdateZone(unittest.TestCase):
    def setUp(self):
        with patch('rubbish.common.db_ops.get_db', new=get_db):
            self.session = db_sessionmaker()()
        self.grid = gpd.read_file("fixtures/grid.geojson", driver='GeoJSON')

    @clean_db
    @alias_test_db
    def testNewZoneWrite(self):
        update_zone("Grid City, California", "Foo, Bar", centerlines=self.grid)

        zones = self.session.query(Zone).all()
        assert len(zones) == 1
        assert zones[0].id == 1
        assert zones[0].name == "Foo, Bar"
        assert zones[0].osmnx_name == "Grid City, California"

        zone_generations = self.session.query(ZoneGeneration).all()
        assert len(zone_generations) == 1
        assert zone_generations[0].id == 1
        assert zone_generations[0].generation == 0
        # NOTE(aleksey): using timedelta of -1hr in case of clock skew
        assert zone_generations[0].final_timestamp > datetime.now() - timedelta(hours=1)
        assert zone_generations[0].zone_id == zones[0].id

        centerlines = self.session.query(Centerline).all()
        assert len(centerlines) == 12
        assert all(pytest.approx(100000, 20000) == l.length_in_meters for l in centerlines)

    @clean_db
    @alias_test_db
    def testExistingZoneIdempotentWrite(self):
        update_zone("Grid City, California", "Foo, Bar", centerlines=self.grid)
        update_zone("Grid City, California", "Foo, Bar", centerlines=self.grid)

        zones = self.session.query(Zone).all()
        assert len(zones) == 1

        zone_generations = self.session.query(ZoneGeneration).all()
        assert len(zone_generations) == 2
        assert zone_generations[0].id == 1
        assert zone_generations[1].id == 2
