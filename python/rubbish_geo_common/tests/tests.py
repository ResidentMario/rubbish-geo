"""
Tests for the CRUD configuration operations, namely set_db and get_db.
"""

import unittest
from unittest.mock import patch
import pytest
import pathlib
import configparser

from rubbish_geo_common.db_ops import get_db, set_db, db_sessionmaker
from rubbish_geo_common.test_utils import (get_app_dir, reset_app_dir, TEST_APP_DIR_TMPDIR)

class TestGetDB(unittest.TestCase):
    @reset_app_dir
    def testNonexistantConfigFileRaises(self):
        with patch('rubbish_geo_common.db_ops.APPDIR', new=get_app_dir()):
            with pytest.raises(ValueError):
                return get_db('local')

    @reset_app_dir
    def testEmptyConfigFileRaises(self):
        with patch('rubbish_geo_common.db_ops.APPDIR', new=get_app_dir()):
            (pathlib.Path(TEST_APP_DIR_TMPDIR) / 'config').touch()
            with pytest.raises(ValueError):
                return get_db('local')

    @reset_app_dir
    def testEmptyConfigFileKeyRaises(self):
        with patch('rubbish_geo_common.db_ops.APPDIR', new=get_app_dir()):
            with open(pathlib.Path(TEST_APP_DIR_TMPDIR) / 'config', 'w') as f:
                f.write("[nonlocal]\nconnstr = foo\nconntype = local\nconname = unset")
            with pytest.raises(ValueError):
                return get_db('local')

    @reset_app_dir
    def testPresentConfigFileKeyWorks(self):
        with patch('rubbish_geo_common.db_ops.APPDIR', new=get_app_dir()):
            with open(pathlib.Path(TEST_APP_DIR_TMPDIR) / 'config', 'w') as f:
                f.write("[local]\nconnstr = foo\nconntype = local\nconname = unset")
            expected = ('foo', 'local', 'unset')
            result = get_db('local')
            assert result == expected

class TestSetDB(unittest.TestCase):
    @reset_app_dir
    def testWriteLocalConnection(self):
        with patch('rubbish_geo_common.db_ops.APPDIR', new=get_app_dir()):
            set_db(profile='local', connstr='foo', conntype='local')
            cfg = configparser.ConfigParser()
            cfg.read(pathlib.Path(TEST_APP_DIR_TMPDIR) / 'config')
            
            assert 'local' in cfg
            local = cfg['local']
            assert local['connstr'] == 'foo'
            assert local['conntype'] == 'local'
            assert local['conname'] == 'unset'

    @reset_app_dir
    def testWriteGCPConnection(self):
        with patch('rubbish_geo_common.db_ops.APPDIR', new=get_app_dir()):
            set_db(profile='dev', connstr='foo', conntype='gcp', conname='bar')
            cfg = configparser.ConfigParser()
            cfg.read(pathlib.Path(TEST_APP_DIR_TMPDIR) / 'config')
            
            assert 'dev' in cfg
            dev = cfg['dev']
            assert dev['connstr'] == 'foo'
            assert dev['conntype'] == 'gcp'
            assert dev['conname'] == 'bar'

    @reset_app_dir
    def testWriteBadGCPConnection(self):
        with patch('rubbish_geo_common.db_ops.APPDIR', new=get_app_dir()):
            with pytest.raises(ValueError):
                set_db(profile='dev', connstr='foo', conntype='gcp')  # no conntype!

class TestDBSessionMaker(unittest.TestCase):
    @reset_app_dir
    def testProfileExists(self):
        with patch('rubbish_geo_common.db_ops.APPDIR', new=get_app_dir()):
            set_db(
                profile='dev', connstr='postgresql://foo:bar@localhost:5432/baz',
                conntype='gcp', conname='bar'
            )
            db_sessionmaker(profile='dev')

    def testProfileDoesntExist(self):
        with patch('rubbish_geo_common.db_ops.APPDIR', new=get_app_dir()):
            with pytest.raises(ValueError):
                db_sessionmaker(profile='dev')

# TODO: set_db tests, fix db_sessionmaker, etcetera.
# Very far-reaching and annoying refactor. :'(