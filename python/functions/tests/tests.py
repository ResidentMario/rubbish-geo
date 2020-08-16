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

from rubbish_geo_common.test_utils import (
    clean_db, alias_test_db, insert_grid, valid_pickups_from_geoms
)
from rubbish_geo_admin import insert_sector
from rubbish_geo_client.ops import write_pickups

import firebase_admin
import firebase_admin.auth

# A "Firebase ID token" is a user-identifying token that is used for user auth inside the Firebase
# ecosystem. A "Firebase custom token" is an application-identifying token that is used for project
# auth inside of the Firebase project.
# 
# Firebase provides a verify_id_token method for verifying ID tokens but no equivalent for minting
# them. The private API expects this token to be set (for user authentication and security
# purposes). This means that we have to deploy an advanced pattern from the follow SO thread:
# https://stackoverflow.com/q/41989345/1993206. The answers here are out of date due to recent
# deprecations on Google's end, but do lead to the correction solution here:
# https://cloud.google.com/identity-platform/docs/use-rest-api#section-verify-custom-token.
#
# Basically we mint a custom token, then use an API call to Google's identity service to reverse
# lookup the id token.
#
# Note that this user will show up in Firebase's authentication console as a new user (with user 
# UID 'polkstreet'): https://console.firebase.google.com/project/PROJECT/authentication/users.
if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
    raise ValueError(
        "The 'GOOGLE_APPLICATION_CREDENTIALS' environment variable must be set and must point "
        "to your local service account file. For instructions on what to do, refer to: "
        "https://firebase.google.com/docs/admin/setup#initialize-sdk."
    )
if "WEB_API_KEY" not in os.environ:
    raise ValueError(
        "The 'WEB_API_KEY' environment variable must be set to your project's web API key. "
        "This value may be read from the settings page for your project: "
        "https://console.firebase.google.com/project/_/settings/general."
        "To learn more about GCP API keys refer to: "
        "https://cloud.google.com/docs/authentication/api-keys?visit_id=637331240698538048-645747484&rd=1"
        "Unfortunately this cannot be set for you automatically, as GCP API Keys have no public "
        "programmtic key API. See further: https://stackoverflow.com/q/61623786/1993206."
    )

WEB_API_KEY = os.environ["WEB_API_KEY"]

app = firebase_admin.initialize_app()
custom_token = firebase_admin.auth.create_custom_token('polkstreet').decode('utf8')
id_token = requests.post(
    f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={WEB_API_KEY}",
    {'token': custom_token, 'returnSecureToken': True}
).json()["idToken"]
print(id_token)

headers = {"Authorization": f"Bearer {id_token}"}

if "PRIVATE_API_EMULATOR_HOST" not in os.environ:
    F_URL = "http://localhost:8081"
else:
    F_URL = os.environ["PRIVATE_API_EMULATOR_HOST"]

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
            f"{F_URL}?request_type=radial&x=0&y=0&distance=0&include_na=False&offset=0",
            headers=headers
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
            f"{F_URL}?request_type=radial&x=0&y=0&distance=1&include_na=False&offset=0",
            headers=headers
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
            f"{F_URL}?request_type=radial&x=0&y=0&distance=1&include_na=False&offset=0",
            headers=headers
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
            f"{F_URL}?request_type=sector&sector_name=Polygon%20Land&include_na=False&offset=0",
            headers=headers
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

        response = requests.get(
            f"{F_URL}?request_type=coord&x=0&y=0&include_na=False&offset=0",
            headers=headers
        )
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

        response = requests.get(f"{F_URL}?request_type=run&run_id=foo", headers=headers)
        response.raise_for_status()
        result = response.json()

        assert result is not None
        assert len(result) == 1
