"""
Client tests. Be sure to run scripts/init_test_db.sh first.
"""
import sqlalchemy as sa
import geopandas as gpd
import datetime as dt
from datetime import datetime, timedelta, timezone
from shapely.geometry import Point, LineString
import random

import unittest
from unittest.mock import patch
import pytest

import rubbish
from rubbish.common.db import reset_db, db_sessionmaker
from rubbish.common.orm import Pickup
from rubbish.common.testing import get_db, clean_db, alias_test_db
from rubbish.common.consts import RUBBISH_TYPES
from rubbish.client.io import write_pickups
from rubbish.admin.zones import update_zone

def valid_pickups_from_geoms(geoms):
    return [{
        'firebase_id': i,
        'type': random.choice(RUBBISH_TYPES),
        'timestamp': str(datetime.now().replace(tzinfo=timezone.utc).timestamp()),
        'curb': random.choice(['left', 'right']),
        'geometry': str(geom)  # as WKT
    } for i, geom in enumerate(geoms)]

# psql -U alekseybilogur -h localhost postgres
class TestWritePickups(unittest.TestCase):
    def setUp(self):
        with patch('rubbish.common.db.get_db', new=get_db):
            self.session = db_sessionmaker()()
        self.grid = gpd.read_file("../../common/fixtures/grid.geojson")

    @clean_db
    @alias_test_db
    def testWritePickups(self):
        update_zone("Grid City, California", "Grid City, California", centerlines=self.grid)

        # Zero pickups.
        write_pickups(gpd.GeoDataFrame({}))
        pickups = self.session.query(Pickup).all()
        assert len(pickups) == 0

        # Pickups with no missing values on a segment.
        write_pickups(valid_pickups_from_geoms([
            Point(0.1, 0),
            Point(0.9, 0)
        ]))

        # Pickups with no missing values near a segment.
        # TODO

        # Pickups on intersections (exact match).
        # TODO

        # Pickups on a single street missing cardinality.
        # TODO

        # Pickups with no missing values spanning multiple segments.
        # TODO

        # Pickups spanning multiple streets and missing cardinality.
        # TODO

        # Pickups spanning multiple streets partially missing cardinality.
        # TODO
        pass
