"""
Client tests. For instructions on running these tests, refer to the README.
"""
import warnings
import tempfile

import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon

import unittest
from unittest.mock import patch
import pytest

from rubbish_geo_common.db_ops import db_sessionmaker
from rubbish_geo_common.orm import Pickup, BlockfaceStatistic
from rubbish_geo_common.test_utils import (
    get_db, clean_db, alias_test_db, insert_grid, valid_pickups_from_geoms
)
from rubbish_geo_client.ops import (
    write_pickups, run_get, coord_get, nearest_centerline_to_point, point_side_of_centerline,
    sector_get, radial_get
)

try:
    import rubbish_geo_admin as _
except (ImportError, ModuleNotFoundError):
    raise ValueError(
        "Running `rubbish_geo_client` tests require installing the `rubbish_geo_admin` package "
        "first."
    )

class TestWritePickups(unittest.TestCase):
    def setUp(self):
        with patch('rubbish_geo_common.db_ops.get_db', new=get_db):
            self.session = db_sessionmaker('local')()

    @clean_db
    @alias_test_db
    @insert_grid
    def testWriteZeroPickups(self):
        write_pickups(gpd.GeoDataFrame({}), 'local')
        pickups = self.session.query(Pickup).all()
        assert len(pickups) == 0

    @clean_db
    @alias_test_db
    @insert_grid
    def testWritePickupsOnSegment(self):
        # Pickups with no missing values on a segment.
        input = valid_pickups_from_geoms([Point(0.1, 0), Point(0.9, 0)], curb='left')
        write_pickups(input, 'local')

        pickups = self.session.query(Pickup).all()
        blockface_statistics = self.session.query(BlockfaceStatistic).all()

        assert len(pickups) == 2
        assert pickups[0].centerline_id == pickups[1].centerline_id
        assert len(blockface_statistics) == 1
        assert blockface_statistics[0].curb == 'left'
        assert blockface_statistics[0].num_runs == 1

    @clean_db
    @alias_test_db
    @insert_grid
    def testWritePickupsNearSegment(self):
        # Pickups with no missing values on a segment.
        input = valid_pickups_from_geoms([Point(0.1, 0.0001), Point(0.9, 0.0001)], curb='left')
        write_pickups(input, 'local')

        pickups = self.session.query(Pickup).all()
        blockface_statistics = self.session.query(BlockfaceStatistic).all()

        assert len(pickups) == 2
        assert pickups[0].centerline_id == pickups[1].centerline_id
        assert len(blockface_statistics) == 1
        assert blockface_statistics[0].curb == 'left'
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
        write_pickups(input, 'local')

        pickups = self.session.query(Pickup).all()
        blockface_statistics = self.session.query(BlockfaceStatistic).all()

        assert len(pickups) == 4
        assert len({p.centerline_id for p in pickups}) == 1
        assert len(blockface_statistics) == 2
        assert {b.curb for b in blockface_statistics} == {'left', 'right'}
        assert blockface_statistics[0].num_runs == 1
        assert blockface_statistics[1].num_runs == 1

    @clean_db
    @alias_test_db
    @insert_grid
    def testWritePickupsIncompleteRun(self):
        input = valid_pickups_from_geoms([Point(0.4, 0.0001), Point(0.6, 0.0001)], curb='left')
        with pytest.raises(ValueError):
            write_pickups(input, 'local')

    @clean_db
    @alias_test_db
    @insert_grid
    def testWritePickupsWithPriorRun(self):
        input = valid_pickups_from_geoms([Point(0.1, 0.0001), Point(0.9, 0.0001)], curb='left')
        write_pickups(input, 'local')
        input = valid_pickups_from_geoms(
            [Point(0.1, 0.0001), Point(0.2, 0.0001), Point(0.8, 0.0001), Point(0.9, 0.0001)],
            curb='left'
        )
        write_pickups(input, 'local')

        blockface_statistics = self.session.query(BlockfaceStatistic).all()
        assert len(blockface_statistics) == 1

    @clean_db
    @alias_test_db
    @insert_grid
    def testWritePickupsInputValidation(self):
        input = valid_pickups_from_geoms([Point(0.1, 0.0001), Point(0.9, 0.0001)], curb='left')
        input[0]['geometry'] = LineString([(0, 0), (1, 1)])
        with pytest.raises(ValueError):
            write_pickups(input, 'local')

        input = valid_pickups_from_geoms([Point(0.1, 0.0001), Point(0.9, 0.0001)], curb='left')
        input[0]['curb'] = 'INVALID'
        with pytest.raises(ValueError):
            write_pickups(input, 'local')

        input = valid_pickups_from_geoms([Point(0.1, 0.0001), Point(0.9, 0.0001)], curb='left')
        input[0]['timestamp'] = 10**10
        with pytest.raises(ValueError):
            write_pickups(input, 'local')

        input = valid_pickups_from_geoms([Point(0.1, 0.0001), Point(0.9, 0.0001)], curb='left')
        input[0]['type'] = 'INVALID'
        with pytest.raises(ValueError):
            write_pickups(input, 'local')

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
        write_pickups(input, 'local', check_distance=True)
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
        write_pickups(input, 'local', check_distance=True)
        blockface_statistics = self.session.query(BlockfaceStatistic).all()
        assert len(blockface_statistics) == 1

    @clean_db
    @alias_test_db
    @insert_grid
    def testWritePickupsMissingCurbAllLeftSimple(self):
        # GH#5 case 5
        geoms = [Point(0.2, 0.11), Point(0.5, 0.1), Point(0.8, 0.09)]
        input = valid_pickups_from_geoms(geoms, curb=None)
        write_pickups(input, 'local', check_distance=True)
        blockface_statistics = self.session.query(BlockfaceStatistic).all()
        assert len(blockface_statistics) == 1
        assert blockface_statistics[0].curb == 'right'

    @clean_db
    @alias_test_db
    @insert_grid
    def testWritePickupsMissingCurbAllRightSimple(self):
        # GH#5 case 5
        geoms = [Point(0.2, -0.11), Point(0.5, -0.1), Point(0.8, -0.09)]
        input = valid_pickups_from_geoms(geoms, curb=None)
        write_pickups(input, 'local', check_distance=True)
        blockface_statistics = self.session.query(BlockfaceStatistic).all()
        assert len(blockface_statistics) == 1
        assert blockface_statistics[0].curb == 'right'

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
        expected = 'left'
        actual = point_side_of_centerline(Point(0, 0), LineString([(1, -1), (1, 1)]))
        assert expected == actual

    def testRight(self):
        expected = 'right'
        actual = point_side_of_centerline(Point(0, 0), LineString([(-1, -1), (-1, 1)]))
        assert expected == actual

    def testOn(self):
        expected = 'left'
        actual = point_side_of_centerline(Point(0, 0), LineString([(0, -1), (0, 1)]))
        assert expected == actual

# TODO: test blockface distance calculation logic

class TestNearestCenterlineToPoint(unittest.TestCase):
    def setUp(self):
        with patch('rubbish_geo_common.get_db', new=get_db):
            self.session = db_sessionmaker('local')()

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
        with patch('rubbish_geo_common.db_ops.get_db', new=get_db):
            self.session = db_sessionmaker('local')()

    @clean_db
    @alias_test_db
    @insert_grid
    def testRunGet(self):
        with pytest.raises(ValueError):
            run_get("BAD_HASH", 'local')

        # case 1: left run inserted only
        input = valid_pickups_from_geoms(
            [Point(0.1, 0.0001), Point(0.9, 0.0001)], firebase_run_id='foo', curb='left'
        )
        write_pickups(input, 'local')
        result = run_get('foo', 'local')
        assert len(result) == 1
        assert (
            result[0]['statistics']['left'] is not None and
            result[0]['statistics']['right'] is None
        )

        # case 2: left and right runs inserted separately
        input = valid_pickups_from_geoms(
            [Point(0.1, -0.0001), Point(0.9, -0.0001)], firebase_run_id='bar', curb='right'
        )
        write_pickups(input, 'local')
        result = run_get('foo', 'local')
        assert len(result) == 1
        assert (
            result[0]['statistics']['left'] is not None and
            result[0]['statistics']['right'] is None
        )

        result = run_get('bar', 'local')
        assert len(result) == 1
        assert (
            result[0]['statistics']['left'] is None and
            result[0]['statistics']['right'] is not None
        )

class TestCoordGet(unittest.TestCase):
    def setUp(self):
        with patch('rubbish_geo_common.db_ops.get_db', new=get_db):
            self.session = db_sessionmaker('local')()

    @clean_db
    @alias_test_db
    @insert_grid
    def testCoordGetIncludeNA(self):
        # case 1: no statistics so stats is empty
        result = coord_get((0.1, 0.0001), 'local', include_na=True)
        assert set(result.keys()) == {'centerline', 'statistics'}
        assert result['centerline'] is not None
        assert result['statistics']['left'] is None and result['statistics']['right'] is None

        # case 2: no right statistics so stats only has left stats
        input = valid_pickups_from_geoms(
            [Point(0.1, 0.0001), Point(0.9, 0.0001)], firebase_run_id='foo', curb='left'
        )
        write_pickups(input, 'local')
        result = coord_get((0.1, 0.0001), 'local', include_na=True)
        assert result['statistics']['left'] is not None and result['statistics']['right'] is None

        # case 3: both sides have stats, so both sides return
        input = valid_pickups_from_geoms(
            [Point(0.1, -0.0001), Point(0.9, -0.0001)], firebase_run_id='bar', curb='right'
        )
        write_pickups(input, 'local')
        result = coord_get((0.1, -0.0001), 'local', include_na=True)
        assert result['statistics']['left'] is not None and result['statistics']['right'] is not None

    @clean_db
    @alias_test_db
    @insert_grid
    def testCoordGetNotNA(self):
        # case 1: no statistics, throws
        with pytest.raises(ValueError):
            # ignore the long-match-distance warnings
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                coord_get((0.0001, 0.0001), 'local')

        # case 2: no right statistics so stats only has left stats
        input = valid_pickups_from_geoms(
            [Point(0.1, 0.0001), Point(0.9, 0.0001)], firebase_run_id='foo', curb='left'
        )
        write_pickups(input, 'local')
        result = coord_get((0.1, 0.0001), 'local', include_na=False)
        assert result['statistics']['left'] is not None and result['statistics']['right'] is None

        # case 3: both sides have stats, so both sides return
        input = valid_pickups_from_geoms(
            [Point(0.1, -0.0001), Point(0.9, -0.0001)], firebase_run_id='bar', curb='right'
        )
        write_pickups(input, 'local')
        result = coord_get((0.1, -0.0001), 'local', include_na=False)
        assert result['statistics']['left'] is not None and result['statistics']['right'] is not None

        # case 4: point is closest to some other centerline, but we iter through to match
        with warnings.catch_warnings():
            # ignore the long-match-distance warnings
            warnings.simplefilter('ignore')
            result = coord_get((1, 1), 'local', include_na=False)
        assert result['statistics']['left'] is not None and result['statistics']['right'] is not None

class TestSectorGet(unittest.TestCase):
    def setUp(self):
        with patch('rubbish_geo_common.db_ops.get_db', new=get_db):
            self.session = db_sessionmaker('local')()

    @clean_db
    @alias_test_db
    @insert_grid
    def testSectorGetNoSuchSector(self):
        with pytest.raises(ValueError):
            sector_get('INVALID', 'local')

    @clean_db
    @alias_test_db
    @insert_grid
    def testSectorGet(self):
        from rubbish_geo_admin.ops import insert_sector

        with tempfile.TemporaryDirectory() as tmpdir:
            poly = Polygon([[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]])
            filepath = tmpdir.rstrip("/") + "/" + "sector-polygon.geojson"
            gpd.GeoDataFrame(geometry=[poly]).to_file(filepath, driver="GeoJSON")
            insert_sector("Polygon Land", filepath, 'local')
        input = valid_pickups_from_geoms(
            [Point(0.1, 0.0001), Point(0.9, 0.0001)], firebase_run_id='foo', curb='left'
        )
        write_pickups(input, 'local')

        result = sector_get('Polygon Land', 'local', include_na=True)
        assert len(result) == 8

        result = sector_get('Polygon Land', 'local', include_na=False)
        assert len(result) == 1
        assert (
            result[0]['statistics']['left'] is not None and
            result[0]['statistics']['right'] is None
        )

class TestRadialGet(unittest.TestCase):
    def setUp(self):
        with patch('rubbish_geo_common.db_ops.get_db', new=get_db):
            self.session = db_sessionmaker('local')()

    @clean_db
    @alias_test_db
    @insert_grid
    def testRadialGetEmpty(self):
        statistics = radial_get((10, 10), 10, 'local')
        assert len(statistics) == 0

    @clean_db
    @alias_test_db
    @insert_grid
    def testRadialGet(self):
        input = valid_pickups_from_geoms(
            [Point(0.1, 0.0001), Point(0.9, 0.0001)], firebase_run_id='foo', curb='left'
        )
        write_pickups(input, 'local')

        result = radial_get((0, 0), 1, 'local', include_na=True)
        assert len(result) == 2

        result = radial_get((0, 0), 10**6, 'local', include_na=True)
        assert len(result) == 12

        result = radial_get((2, 2), 1, 'local', include_na=True)
        assert len(result) == 2

        result = radial_get((2, 2), 1, 'local', include_na=False)
        assert len(result) == 0
