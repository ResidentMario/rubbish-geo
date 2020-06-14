"""
Client tests. Be sure to run scripts/init_test_db.sh first.
"""
import sqlalchemy as sa
import geopandas as gpd
import datetime as dt
from datetime import datetime, timedelta, timezone
from shapely.geometry import Point, LineString
import random
import os

import unittest
from unittest.mock import patch
import pytest

import rubbish
from rubbish.common.db_ops import reset_db, db_sessionmaker
from rubbish.common.orm import Pickup, BlockfaceStatistic
from rubbish.common.test_utils import get_db, clean_db, alias_test_db
from rubbish.common.consts import RUBBISH_TYPES
from rubbish.client.ops import write_pickups, run_get, coord_get
from rubbish.admin.ops import update_zone

def valid_pickups_from_geoms(geoms, firebase_run_id='foo', curb=None):
    return [{
        'firebase_id': str(hash(i)).lstrip("-"),
        'firebase_run_id': firebase_run_id,
        'type': random.choice(RUBBISH_TYPES),
        'timestamp': str(datetime.now().replace(tzinfo=timezone.utc).timestamp()),
        'curb': random.choice(['left', 'right']) if curb is None else curb,
        'geometry': str(geom)  # as WKT
    } for i, geom in enumerate(geoms)]

class TestWritePickups(unittest.TestCase):
    def setUp(self):
        with patch('rubbish.common.db_ops.get_db', new=get_db):
            self.session = db_sessionmaker()()
        self.grid = gpd.read_file(
            os.path.dirname(os.path.realpath(__file__)) + "/fixtures/grid.geojson"
        )

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

# TODO: more comprehensive write pickups tests to test the point assignment logic
# TODO: test blockface logic, including distance calculations
# TODO: move away from using the grid.json fixture, define that as a function instead.

class TestRunGet(unittest.TestCase):
    def setUp(self):
        with patch('rubbish.common.db_ops.get_db', new=get_db):
            self.session = db_sessionmaker()()
        self.grid = gpd.read_file(
            os.path.dirname(os.path.realpath(__file__)) + "/fixtures/grid.geojson"
        )

    @clean_db
    @alias_test_db
    def testRunGet(self):
        update_zone("Grid City, California", "Grid City, California", centerlines=self.grid)

        with pytest.raises(ValueError):
            run_get("BAD_HASH")

        # case 1: left run inserted, but it doesn't pass validation rules so it doesn't count
        input = valid_pickups_from_geoms(
            [Point(0.4, 0.0001), Point(0.6, 0.0001)], firebase_run_id='foo', curb='left'
        )
        write_pickups(input)
        result = run_get('foo')
        assert len(result) == 0

        # case 2: left run inserted only
        input = valid_pickups_from_geoms(
            [Point(0.1, 0.0001), Point(0.9, 0.0001)], firebase_run_id='foo', curb='left'
        )
        write_pickups(input)
        result = run_get('foo')
        expected_keys = {
            'centerline_id', 'centerline_geometry', 'centerline_length_in_meters',
            'centerline_name', 'curb', 'rubbish_per_meter', 'num_runs'
        }
        assert len(result) == 1
        assert set(result[0].keys()) == expected_keys

        # case 3: left and right runs inserted, query is for right side so only right is returned
        input = valid_pickups_from_geoms(
            [Point(0.1, -0.0001), Point(0.9, -0.0001)], firebase_run_id='bar', curb='right'
        )
        write_pickups(input)
        result = run_get('foo')
        assert len(result) == 1
        assert result[0]['curb'] == 0
        result = run_get('bar')
        assert len(result) == 1
        assert result[0]['curb'] == 1

class TestCoordGet(unittest.TestCase):
    def setUp(self):
        with patch('rubbish.common.db_ops.get_db', new=get_db):
            self.session = db_sessionmaker()()
        self.grid = gpd.read_file(
            os.path.dirname(os.path.realpath(__file__)) + "/fixtures/grid.geojson"
        )

    @clean_db
    @alias_test_db
    def testCoordGetIncludeNA(self):
        update_zone("Grid City, California", "Grid City, California", centerlines=self.grid)

        # case 1: no statistics so stats is empty
        result = coord_get((0.1, 0.0001), include_na=True)
        assert set(result.keys()) == {'centerline', 'stats'}
        assert result['centerline'] is not None
        assert len(result['stats']) == 0

        # case 2: no right statistics so stats only has left stats
        input = valid_pickups_from_geoms(
            [Point(0.1, 0.0001), Point(0.9, 0.0001)], firebase_run_id='foo', curb='left'
        )
        write_pickups(input)
        result = coord_get((0.1, 0.0001), include_na=True)
        assert len(result['stats']) == 1

        # case 3: both sides have stats, so both sides return
        input = valid_pickups_from_geoms(
            [Point(0.1, -0.0001), Point(0.9, -0.0001)], firebase_run_id='bar', curb='right'
        )
        write_pickups(input)
        result = coord_get((0.1, -0.0001), include_na=True)
        assert len(result['stats']) == 2
