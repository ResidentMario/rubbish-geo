"""
Function tests. Be sure to stand up the function emulator first.
"""
import unittest

from rubbish.common.test_utils import clean_db, alias_test_db, insert_grid
import requests

# TODO: real tests
class TestWritePickupsFunction(unittest.TestCase):
    @clean_db
    @alias_test_db
    @insert_grid
    def testWriteZeroPickups(self):
        response = requests.post("http://localhost:8080", json={"key": "value"})
        response.raise_for_status()
        assert response.json() is not None
