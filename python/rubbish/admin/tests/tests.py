"""
Admin client tests. Be sure to run scripts/init_test_db.sh first.
"""
import sqlalchemy as sa

import unittest
from unittest.mock import patch, call, Mock, ANY
import pytest

import rubbish
from rubbish.admin.zones import update_zone

import getpass
get_db = lambda: f"postgresql://{getpass.getuser()}@localhost/postgres"

# psql -U alekseybilogur -h localhost postgres
class TestUpdateZone(unittest.TestCase):
    def testWhatever(self):
        with patch('rubbish.common.db.get_db', new=get_db):
            update_zone("Piedmont, California", "Piedmont, California")
            # TODO: test write (mock out the network queries involved)
            pass

    def tearDown(self):
        # TODO: zero out again tables
        pass
