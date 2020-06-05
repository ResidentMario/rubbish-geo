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
from rubbish.common.db import reset_db, db_sessionmaker
from rubbish.common.orm import Zone, ZoneGeneration
from rubbish.common.testing import get_db, reset_auto_increment, clean_db, alias_test_db
from rubbish.admin.zones import update_zone

# psql -U alekseybilogur -h localhost postgres
class TestUpdateZone(unittest.TestCase):
    def setUp(self):
        with patch('rubbish.common.db.get_db', new=get_db):
            self.session = db_sessionmaker()()
        self.centerlines = gpd.read_file("../../common/fixtures/grid.geojson", driver='GeoJSON')

    @clean_db
    @alias_test_db
    def testNewZoneWrite(self):
        update_zone("Grid City, California", "Foo, Bar", centerlines=self.centerlines)

        zones = self.session.query(Zone).all()
        assert len(zones) == 1
        assert zones[0].id == 1
        assert zones[0].name == "Foo, Bar"
        assert zones[0].osmnx_name == "Grid City, California"

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
        update_zone("Grid City, California", "Foo, Bar", centerlines=self.centerlines)
        update_zone("Grid City, California", "Foo, Bar", centerlines=self.centerlines)

        zones = self.session.query(Zone).all()
        assert len(zones) == 1

        zone_generations = self.session.query(ZoneGeneration).all()
        assert len(zone_generations) == 2
        assert zone_generations[0].id == 1
        assert zone_generations[1].id == 2
