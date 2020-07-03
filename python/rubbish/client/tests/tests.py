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
from rubbish.common.test_utils import get_db, clean_db, alias_test_db, insert_grid
from rubbish.common.consts import RUBBISH_TYPES
from rubbish.client.ops import (
    write_pickups, run_get, coord_get, nearest_centerline_to_point, point_side_of_centerline
)
from rubbish.admin.ops import update_zone

def valid_pickups_from_geoms(geoms, firebase_run_id='foo', curb=None):
    return [{
        'firebase_id': str(abs(hash(i))),
        'firebase_run_id': firebase_run_id,
        'type': random.choice(RUBBISH_TYPES),
        'timestamp': str(datetime.now().replace(tzinfo=timezone.utc).timestamp()),
        'curb': curb,
        'geometry': geom
    } for i, geom in enumerate(geoms)]

class TestWritePickups(unittest.TestCase):
    def setUp(self):
        with patch('rubbish.common.db_ops.get_db', new=get_db):
            self.session = db_sessionmaker()()

    @clean_db
    @alias_test_db
    @insert_grid
    def testWriteZeroPickups(self):
        write_pickups(gpd.GeoDataFrame({}))
        pickups = self.session.query(Pickup).all()
        assert len(pickups) == 0

    @clean_db
    @alias_test_db
    @insert_grid
    def testWritePickupsOnSegment(self):
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
    @insert_grid
    def testWritePickupsNearSegment(self):
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
    @insert_grid
    def testWritePickupsNearSegmentBothSides(self):
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
    @insert_grid
    def testWritePickupsIncompleteRun(self):
        input = valid_pickups_from_geoms([Point(0.4, 0.0001), Point(0.6, 0.0001)], curb='left')
        with pytest.raises(ValueError):
            write_pickups(input)

    @clean_db
    @alias_test_db
    @insert_grid
    def testWritePickupsWithPriorRun(self):
        input = valid_pickups_from_geoms([Point(0.1, 0.0001), Point(0.9, 0.0001)], curb='left')
        write_pickups(input)
        input = valid_pickups_from_geoms(
            [Point(0.1, 0.0001), Point(0.2, 0.0001), Point(0.8, 0.0001), Point(0.9, 0.0001)],
            curb='left'
        )
        write_pickups(input)

        blockface_statistics = self.session.query(BlockfaceStatistic).all()
        assert len(blockface_statistics) == 1

    @clean_db
    @alias_test_db
    @insert_grid
    def testWritePickupsInputValidation(self):
        input = valid_pickups_from_geoms([Point(0.1, 0.0001), Point(0.9, 0.0001)], curb='left')
        input[0]['geometry'] = LineString([(0, 0), (1, 1)])
        with pytest.raises(ValueError):
            write_pickups(input)

        input = valid_pickups_from_geoms([Point(0.1, 0.0001), Point(0.9, 0.0001)], curb='left')
        input[0]['curb'] = 'INVALID'
        with pytest.raises(ValueError):
            write_pickups(input)

        input = valid_pickups_from_geoms([Point(0.1, 0.0001), Point(0.9, 0.0001)], curb='left')
        input[0]['timestamp'] = 10**10
        with pytest.raises(ValueError):
            write_pickups(input)

        input = valid_pickups_from_geoms([Point(0.1, 0.0001), Point(0.9, 0.0001)], curb='left')
        input[0]['type'] = 'INVALID'
        with pytest.raises(ValueError):
            write_pickups(input)

    @clean_db
    @alias_test_db
    @insert_grid
    def testWritePickupsDealWithScatter(self):
        # GH#5 case 4
        # Run on a single centerline with points scattering near adjacent centerlines. Expected
        # behavior is that the scattered points (located out of position due to GPS inaccuracy)
        # will get consolidated onto the target centerline.
        geoms = [Point(0.1, 0), Point(0.9, 0), Point(0, 0.1), Point(1, 0.1)]
        input = valid_pickups_from_geoms(geoms, curb='left')
        write_pickups(input, check_distance=True)
        blockface_statistics = self.session.query(BlockfaceStatistic).all()
        assert len(blockface_statistics) == 1

    @clean_db
    @alias_test_db
    @insert_grid
    def testWritePickupsDealWithHeavyScatter(self):
        # GH#5 case 4
        # In this case there is a point that is reported that is very far away. Robustness check.
        geoms = [Point(0.1, 0), Point(0.9, 0), Point(2, 2)]
        input = valid_pickups_from_geoms(geoms, curb='left')
        write_pickups(input, check_distance=True)
        blockface_statistics = self.session.query(BlockfaceStatistic).all()
        assert len(blockface_statistics) == 1

    @clean_db
    @alias_test_db
    @insert_grid
    def testWritePickupsMissingCurbAllLeftSimple(self):
        # GH#5 case 5
        geoms = [Point(0.2, 0.11), Point(0.5, 0.1), Point(0.8, 0.09)]
        input = valid_pickups_from_geoms(geoms, curb=None)
        write_pickups(input, check_distance=True)
        blockface_statistics = self.session.query(BlockfaceStatistic).all()
        assert len(blockface_statistics) == 1
        assert blockface_statistics[0].curb == 0

    @clean_db
    @alias_test_db
    @insert_grid
    def testWritePickupsMissingCurbAllRightSimple(self):
        # GH#5 case 5
        geoms = [Point(0.2, -0.11), Point(0.5, -0.1), Point(0.8, -0.09)]
        input = valid_pickups_from_geoms(geoms, curb=None)
        write_pickups(input, check_distance=True)
        blockface_statistics = self.session.query(BlockfaceStatistic).all()
        assert len(blockface_statistics) == 1
        assert blockface_statistics[0].curb == 1

    # Crafting a simple test case that triggers this logic is proving troublesome!
    # @clean_db
    # @alias_test_db
    # @insert_grid
    # def testWritePickupsMissingCurbBothSidesSimple(self):
    #     # GH#5 case 5
    #     geoms = [
    #         Point(0.2, -0.1), Point(0.2, -0.1), Point(0.2, -0.1), Point(0.2, -0.1),
    #         Point(0.8, -0.1), Point(0.8, -0.1), Point(0.8, -0.1), Point(0.8, -0.1),
    #         Point(0.2, 0.1), Point(0.2, 0.1), Point(0.2, 0.1), Point(0.2, 0.1),
    #         Point(0.8, 0.1), Point(0.8, 0.1), Point(0.8, 0.1), Point(0.8, 0.1),
    #     ]
    #     input = valid_pickups_from_geoms(geoms, curb=None)
    #     write_pickups(input, check_distance=True)
    #     blockface_statistics = self.session.query(BlockfaceStatistic).all()
    #     import pdb; pdb.set_trace()
    #     assert len(blockface_statistics) == 2

    # TODO: test curb imputation behavior using sample points drawn from gaussian distriutions

class TestPointSideOfCenterline(unittest.TestCase):
    def testLeft(self):
        expected = 0
        actual = point_side_of_centerline(Point(0, 0), LineString([(1, -1), (1, 1)]))
        assert expected == actual

    def testRight(self):
        expected = 1
        actual = point_side_of_centerline(Point(0, 0), LineString([(-1, -1), (-1, 1)]))
        assert expected == actual

    def testOn(self):
        expected = 0
        actual = point_side_of_centerline(Point(0, 0), LineString([(0, -1), (0, 1)]))
        assert expected == actual

# TODO: point assignment logic integration tests (use the preexisting run data)
# TODO: test blockface distance calculation logic

class TestNearestCenterlineToPoint(unittest.TestCase):
    def setUp(self):
        with patch('rubbish.common.db_ops.get_db', new=get_db):
            self.session = db_sessionmaker()()

    @clean_db
    @alias_test_db
    def testEmpty(self):
        with pytest.raises(ValueError):
            nearest_centerline_to_point(Point(0, 0), self.session, rank=0)

    @clean_db
    @alias_test_db
    @insert_grid
    def testRankOverCutoff(self):
        with pytest.raises(ValueError):
            nearest_centerline_to_point(Point(0, 0), self.session, rank=1000)

    @clean_db
    @alias_test_db
    @insert_grid
    def testRankTooHigh(self):
        # raises because there are only 12 centerlines in the database
        with pytest.raises(ValueError):
            nearest_centerline_to_point(Point(0, 0), self.session, rank=13)

    @clean_db
    @alias_test_db
    @insert_grid
    def testFirstResult(self):
        centerline = nearest_centerline_to_point(
            Point(0, 0.5), self.session, rank=0, check_distance=True
        )
        assert centerline.name == "0_0_0_1 Street"

    @clean_db
    @alias_test_db
    @insert_grid
    def testSecondResult(self):
        centerline = nearest_centerline_to_point(
            Point(0.1, 0.4), self.session, rank=1, check_distance=True
        )
        assert centerline.name == "0_0_1_0 Street"

class TestRunGet(unittest.TestCase):
    def setUp(self):
        with patch('rubbish.common.db_ops.get_db', new=get_db):
            self.session = db_sessionmaker()()

    @clean_db
    @alias_test_db
    @insert_grid
    def testRunGet(self):
        with pytest.raises(ValueError):
            run_get("BAD_HASH")

        # case 1: left run inserted only
        input = valid_pickups_from_geoms(
            [Point(0.1, 0.0001), Point(0.9, 0.0001)], firebase_run_id='foo', curb='left'
        )
        write_pickups(input)
        result = run_get('foo')
        assert len(result) == 1
        assert result[0]['statistics'][0] is not None and result[0]['statistics'][1] is None

        # case 2: left and right runs inserted separately
        input = valid_pickups_from_geoms(
            [Point(0.1, -0.0001), Point(0.9, -0.0001)], firebase_run_id='bar', curb='right'
        )
        write_pickups(input)
        result = run_get('foo')
        assert len(result) == 1
        assert result[0]['statistics'][0] is not None and result[0]['statistics'][1] is None

        result = run_get('bar')
        assert len(result) == 1
        assert result[0]['statistics'][0] is None and result[0]['statistics'][1] is not None

class TestCoordGet(unittest.TestCase):
    def setUp(self):
        with patch('rubbish.common.db_ops.get_db', new=get_db):
            self.session = db_sessionmaker()()

    @clean_db
    @alias_test_db
    @insert_grid
    def testCoordGetIncludeNA(self):
        # case 1: no statistics so stats is empty
        result = coord_get((0.1, 0.0001), include_na=True)
        assert set(result.keys()) == {'centerline', 'statistics'}
        assert result['centerline'] is not None
        assert result['statistics'][0] is None and result['statistics'][1] is None

        # case 2: no right statistics so stats only has left stats
        input = valid_pickups_from_geoms(
            [Point(0.1, 0.0001), Point(0.9, 0.0001)], firebase_run_id='foo', curb='left'
        )
        write_pickups(input)
        result = coord_get((0.1, 0.0001), include_na=True)
        assert result['statistics'][0] is not None and result['statistics'][1] is None

        # case 3: both sides have stats, so both sides return
        input = valid_pickups_from_geoms(
            [Point(0.1, -0.0001), Point(0.9, -0.0001)], firebase_run_id='bar', curb='right'
        )
        write_pickups(input)
        result = coord_get((0.1, -0.0001), include_na=True)
        assert result['statistics'][0] is not None and result['statistics'][1] is not None
