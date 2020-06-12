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
from rubbish.common.db_ops import reset_db, db_sessionmaker
from rubbish.common.orm import Pickup, BlockfaceStatistic
from rubbish.common.test_utils import get_db, clean_db, alias_test_db
from rubbish.common.consts import RUBBISH_TYPES
from rubbish.client.ops import write_pickups
from rubbish.admin.ops import update_zone

def valid_pickups_from_geoms(geoms, curb=None):
    return [{
        'firebase_id': hash(i),
        'type': random.choice(RUBBISH_TYPES),
        'timestamp': str(datetime.now().replace(tzinfo=timezone.utc).timestamp()),
        'curb': random.choice(['left', 'right']) if curb is None else curb,
        'geometry': str(geom)  # as WKT
    } for i, geom in enumerate(geoms)]

class TestWritePickups(unittest.TestCase):
    def setUp(self):
        with patch('rubbish.common.db_ops.get_db', new=get_db):
            self.session = db_sessionmaker()()
        self.grid = gpd.read_file("fixtures/grid.geojson")

    @clean_db
    @alias_test_db
    def testWriteZeroPickups(self):
        update_zone("Grid City, California", "Grid City, California", centerlines=self.grid)
        write_pickups(gpd.GeoDataFrame({}))
        pickups = self.session.query(Pickup).all()
        assert len(pickups) == 0

    @clean_db
    @alias_test_db
    def testWritePickupsOnSegment(self):
        update_zone("Grid City, California", "Grid City, California", centerlines=self.grid)

        # Pickups with no missing values on a segment.
        input = valid_pickups_from_geoms([Point(0.1, 0), Point(0.9, 0)], curb='left')
        write_pickups(input)

        pickups = self.session.query(Pickup).all()
        blockface_statistics = self.session.query(BlockfaceStatistic).all()

        assert len(pickups) == 2
        assert pickups[0].centerline_id == pickups[1].centerline_id
        assert len(blockface_statistics) == 1
        assert blockface_statistics[0].curb == 0
        assert blockface_statistics[0].num_runs == 1

    @clean_db
    @alias_test_db
    def testWritePickupsNearSegment(self):
        update_zone("Grid City, California", "Grid City, California", centerlines=self.grid)

        # Pickups with no missing values on a segment.
        input = valid_pickups_from_geoms([Point(0.1, 0.0001), Point(0.9, 0.0001)], curb='left')
        write_pickups(input)

        pickups = self.session.query(Pickup).all()
        blockface_statistics = self.session.query(BlockfaceStatistic).all()

        assert len(pickups) == 2
        assert pickups[0].centerline_id == pickups[1].centerline_id
        assert len(blockface_statistics) == 1
        assert blockface_statistics[0].curb == 0
        assert blockface_statistics[0].num_runs == 1

    @clean_db
    @alias_test_db
    def testWritePickupsNearSegmentBothSides(self):
        update_zone("Grid City, California", "Grid City, California", centerlines=self.grid)

        # Pickups with no missing values on a segment.
        input = (
            valid_pickups_from_geoms([Point(0.1, 0.0001), Point(0.9, 0.0001)], curb='left') +
            valid_pickups_from_geoms([Point(0.1, 0.0001), Point(0.9, 0.0001)], curb='right')
        )
        write_pickups(input)

        pickups = self.session.query(Pickup).all()
        blockface_statistics = self.session.query(BlockfaceStatistic).all()

        assert len(pickups) == 4
        assert len({p.centerline_id for p in pickups}) == 1
        assert len(blockface_statistics) == 2
        assert {b.curb for b in blockface_statistics} == {0, 1}
        assert blockface_statistics[0].num_runs == 1
        assert blockface_statistics[1].num_runs == 1

    @clean_db
    @alias_test_db
    def testWritePickupsIncompleteRun(self):
        update_zone("Grid City, California", "Grid City, California", centerlines=self.grid)

        input = valid_pickups_from_geoms([Point(0.4, 0.0001), Point(0.6, 0.0001)], curb='left')
        write_pickups(input)

        blockface_statistics = self.session.query(BlockfaceStatistic).all()
        assert len(blockface_statistics) == 0

    @clean_db
    @alias_test_db
    def testWritePickupsWithPriorRun(self):
        update_zone("Grid City, California", "Grid City, California", centerlines=self.grid)

        input = valid_pickups_from_geoms([Point(0.1, 0.0001), Point(0.9, 0.0001)], curb='left')
        write_pickups(input)
        input = valid_pickups_from_geoms(
            [Point(0.1, 0.0001), Point(0.2, 0.0001), Point(0.8, 0.0001), Point(0.9, 0.0001)],
            curb='left'
        )
        write_pickups(input)

        blockface_statistics = self.session.query(BlockfaceStatistic).all()
        assert len(blockface_statistics) == 1

# Pickups with no missing values near a segment.
# TODO

# Pickups on a single street missing cardinality.
# TODO

# Pickups with no missing values spanning multiple segments.
# TODO

# Pickups spanning multiple streets and missing cardinality.
# TODO

# Pickups spanning multiple streets partially missing cardinality.
# TODO
