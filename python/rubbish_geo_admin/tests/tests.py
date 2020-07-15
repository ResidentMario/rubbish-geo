"""
Admin client tests.
"""
import geopandas as gpd
from datetime import datetime, timedelta
from shapely.geometry import LineString, Polygon, MultiPolygon

import unittest
from unittest.mock import patch
import pytest
import tempfile

from rubbish_geo_common.db_ops import db_sessionmaker
from rubbish_geo_common.orm import Zone, ZoneGeneration, Centerline, Sector
from rubbish_geo_common.test_utils import get_db, clean_db, alias_test_db, insert_grid, get_grid
from rubbish_geo_admin import update_zone, insert_sector, delete_sector, show_zones, show_sectors

class TestUpdateZone(unittest.TestCase):
    def setUp(self):
        with patch('rubbish_geo_common.db_ops.get_db', new=get_db):
            self.session = db_sessionmaker()()

    @clean_db
    @alias_test_db
    def testNewZoneWrite(self):
        grid = get_grid()
        update_zone("Grid City, California", "Foo, Bar", centerlines=grid)
        
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
        grid = get_grid()
        update_zone("Grid City, California", "Foo, Bar", centerlines=grid)
        update_zone("Grid City, California", "Foo, Bar", centerlines=grid)

        zones = self.session.query(Zone).all()
        assert len(zones) == 1

        zone_generations = self.session.query(ZoneGeneration).all()
        assert len(zone_generations) == 2
        assert zone_generations[0].id == 1
        assert zone_generations[1].id == 2
    
    @clean_db
    @alias_test_db
    @insert_grid
    def testShowZones(self):
        show_zones()


class testSectorOps(unittest.TestCase):
    def setUp(self):
        with patch('rubbish_geo_common.db_ops.get_db', new=get_db):
            self.session = db_sessionmaker()()

    @clean_db
    @alias_test_db
    def testOps(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # polygon case (valid)
            poly = Polygon([[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]])
            filepath = tmpdir.rstrip("/") + "/" + "sector-polygon.geojson"
            gpd.GeoDataFrame(geometry=[poly]).to_file(filepath, driver="GeoJSON")

            insert_sector("Polygon Land", filepath)
            assert self.session.query(Sector).count() == 1

            with pytest.raises(ValueError):
                insert_sector("Polygon Land", filepath)
            
            delete_sector("Polygon Land")
            assert self.session.query(Sector).count() == 0

            with pytest.raises(ValueError):
                delete_sector("Polygon Land")

            # multipolygon case (valid)
            mpoly = MultiPolygon(
                [
                    Polygon([[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]),
                    Polygon([[1, 1], [1, 2], [2, 2], [2, 1], [1, 1]])        
                ]
            )
            filepath = tmpdir.rstrip("/") + "/" + "sector-multipolygon.geojson"
            gpd.GeoDataFrame(geometry=[mpoly]).to_file(filepath, driver="GeoJSON")
            insert_sector("MultiPolygon Land", filepath)
            assert self.session.query(Sector).count() == 1
            delete_sector("MultiPolygon Land")
            assert self.session.query(Sector).count() == 0

            # linestring case (invalid)
            ls = LineString([[0, 0], [1, 1]])
            gpd.GeoDataFrame(geometry=[ls]).to_file(filepath, driver="GeoJSON")
            filepath = tmpdir.rstrip("/") + "/" + "sector-linestring.geojson"
            with pytest.raises(ValueError):
                insert_sector("LineString Land", filepath)

    @clean_db
    @alias_test_db
    def testShowSectors(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            poly = Polygon([[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]])
            filepath = tmpdir.rstrip("/") + "/" + "sector-polygon.geojson"
            gpd.GeoDataFrame(geometry=[poly]).to_file(filepath, driver="GeoJSON")
            insert_sector("Polygon Land", filepath)

            show_sectors()
