"""
Tests the functions in the private `rubbish-geo` API.

Be sure to stand up the function emulator first.
"""

from datetime import datetime
import unittest
import tempfile
import os

import requests
from shapely.geometry import Point, Polygon
import geopandas as gpd

from rubbish.common.test_utils import (
    clean_db, alias_test_db, insert_grid, valid_pickups_from_geoms
)
from rubbish.admin.ops import insert_sector
from rubbish.client.ops import write_pickups
from rubbish.common.consts import RUBBISH_TYPES

F_URL = "http://localhost:8080" if "FUNCTION_SERVICE_URL" not in os.environ\
    else os.environ["FUNCTION_SERVICE_URL"]

class Test_POST_pickups(unittest.TestCase):
    @clean_db
    @alias_test_db
    @insert_grid
    def testWriteZeroPickups(self):
        response = requests.post(F_URL, json={})
        response.raise_for_status()
        assert response.json() is not None

    @clean_db
    @alias_test_db
    @insert_grid
    def testWriteSinglePickup(self):
        payload = {
            'foo': [
                    {
                        'firebase_run_id': 'foo',
                        'firebase_id': 'baz',
                        'type': 'glass',
                        'timestamp': int(datetime.now().timestamp()),
                        'curb': 'left',
                        'geometry': 'POINT(0 0.1)'
                    },
                    {
                        'firebase_run_id': 'foo',
                        'firebase_id': 'ban',
                        'type': 'glass',
                        'timestamp': int(datetime.now().timestamp()),
                        'curb': 'left',
                        'geometry': 'POINT(0 0.9)'
                    }
            ]
        }
        response = requests.post(F_URL, json=payload)
        response.raise_for_status()
        assert response.json() is not None

    @clean_db
    @alias_test_db
    @insert_grid
    def testWriteMultiplePickups(self):
        payload = {
            'foo': [
                    {
                        'firebase_run_id': 'foo',
                        'firebase_id': 'baz',
                        'type': 'glass',
                        'timestamp': int(datetime.now().timestamp()),
                        'curb': 'left',
                        'geometry': 'POINT(0 0.1)'
                    },
                    {
                        'firebase_run_id': 'foo',
                        'firebase_id': 'ban',
                        'type': 'glass',
                        'timestamp': int(datetime.now().timestamp()),
                        'curb': 'left',
                        'geometry': 'POINT(0 0.9)'
                    }
            ],
            'bar': [
                    {
                        'firebase_run_id': 'bar',
                        'firebase_id': 'baz',
                        'type': 'glass',
                        'timestamp': int(datetime.now().timestamp()),
                        'curb': 'left',
                        'geometry': 'POINT(0.1 0)'
                    },
                    {
                        'firebase_run_id': 'bar',
                        'firebase_id': 'ban',
                        'type': 'glass',
                        'timestamp': int(datetime.now().timestamp()),
                        'curb': 'left',
                        'geometry': 'POINT(0.9 0)'
                    }
            ]
        }
        response = requests.post(F_URL, json=payload)
        response.raise_for_status()
        assert response.json() is not None


class Test_GET_radial(unittest.TestCase):
    @clean_db
    @alias_test_db
    @insert_grid
    def testGetZero(self):
        response = requests.get(
            f"{F_URL}?x=0&y=0&distance=0&include_na=False&offset=0"
        )
        response.raise_for_status()
        assert response.json() is not None

    @clean_db
    @alias_test_db
    @insert_grid
    def testGetSingle(self):
        pickups = valid_pickups_from_geoms([Point(0.1, 0), Point(0.9, 0)], curb='left')
        write_pickups(pickups)

        response = requests.get(
            f"{F_URL}?x=0&y=0&distance=1&include_na=False&offset=0"
        )
        response.raise_for_status()
        result = response.json()

        assert result is not None
        assert len(result) == 1

    @clean_db
    @alias_test_db
    @insert_grid
    def testGetDouble(self):
        pickups = valid_pickups_from_geoms([Point(0.1, 0), Point(0.9, 0)], curb='left')
        write_pickups(pickups)
        pickups = valid_pickups_from_geoms([Point(0, 0.1), Point(0, 0.9)], curb='left')
        write_pickups(pickups)

        response = requests.get(
            f"{F_URL}?x=0&y=0&distance=1&include_na=False&offset=0"
        )
        response.raise_for_status()
        result = response.json()

        assert result is not None
        assert len(result) == 1


class Test_GET_sector(unittest.TestCase):
    @clean_db
    @alias_test_db
    @insert_grid
    def testGetSector(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            poly = Polygon([[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]])
            filepath = tmpdir.rstrip("/") + "/" + "sector-polygon.geojson"
            gpd.GeoDataFrame(geometry=[poly]).to_file(filepath, driver="GeoJSON")
            insert_sector("Polygon Land", filepath)

        pickups = valid_pickups_from_geoms([Point(0.1, 0), Point(0.9, 0)], curb='left')
        write_pickups(pickups)

        response = requests.get(
            f"{F_URL}?sector_name=Polygon%20Land&include_na=False&offset=0"
        )
        response.raise_for_status()
        result = response.json()

        assert result is not None
        assert len(result) == 1


class Test_GET_coord(unittest.TestCase):
    # No zero test in this case: raises value error if no match was found within some number of
    # attempts.
    
    @clean_db
    @alias_test_db
    @insert_grid
    def testGetSingleCoord(self):
        pickups = valid_pickups_from_geoms([Point(0.1, 0), Point(0.9, 0)], curb='left')
        write_pickups(pickups)

        response = requests.get(f"{F_URL}?x=0&y=0&include_na=False&offset=0")
        response.raise_for_status()
        result = response.json()

        assert result is not None
        assert len(result) == 1

class Test_GET_run(unittest.TestCase):
    @clean_db
    @alias_test_db
    @insert_grid
    def testGetRun(self):
        pickups = valid_pickups_from_geoms(
            [Point(0.1, 0), Point(0.9, 0)], firebase_run_id='foo', curb='left'
        )
        write_pickups(pickups)

        response = requests.get(f"{F_URL}?run_id=foo")
        response.raise_for_status()
        result = response.json()

        assert result is not None
        assert len(result) == 1
