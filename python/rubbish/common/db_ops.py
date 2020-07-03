"""
Generic DB operations unrelated to application state.
"""

import click
import pathlib
import os
import configparser

import sqlalchemy as sa
from sqlalchemy.orm.session import sessionmaker
from .orm import (Zone, ZoneGeneration, Sector, Centerline, Pickup, BlockfaceStatistic)

APPDIR = pathlib.Path(click.get_app_dir("rubbish", force_posix=True))

def set_db(dbstr, profile=None):
    """
    Sets the target database connection string (writing the input value to disk).
    """
    if profile is None:
        profile = 'default'

    if not APPDIR.exists():
        os.makedirs(APPDIR)

    cfg_fp = APPDIR / "config"
    cfg = configparser.ConfigParser()
    if cfg_fp.exists():
        cfg.read(cfg_fp)
    cfg[profile] = {'connstr': dbstr}
    with open(cfg_fp, "w") as f:
        cfg.write(f)

def get_db(profile=None):
    """
    Gets the current database. Returns None if unset.
    """
    if profile is None:
        profile = 'default'

    cfg_fp = APPDIR / "config"
    if not cfg_fp.exists():
        return None
    cfg = configparser.ConfigParser()
    cfg.read(cfg_fp)
    return cfg[profile]['connstr']

def db_sessionmaker(profile=None):
    """
    Returns a sessionmaker object for creating DB sessions.
    """
    if profile is None:
        profile = 'default'
    
    connstr = get_db(profile=profile)
    if connstr == None:
        raise ValueError("connection string not set, run set_db first")
    engine = sa.create_engine(connstr)
    return sessionmaker(bind=engine)

def reset_db(profile=None):
    """
    Resets the current database, deleting all data.
    """
    if profile is None:
        profile = 'default'

    session = db_sessionmaker(profile=profile)()

    engine = session.bind
    engine.execute('ALTER SEQUENCE zones_id_seq RESTART WITH 1;')
    engine.execute('ALTER SEQUENCE zone_generations_id_seq RESTART WITH 1;')
    engine.execute('ALTER SEQUENCE blockface_statistics_id_seq RESTART WITH 1;')
    engine.execute('ALTER SEQUENCE pickups_id_seq RESTART WITH 1;')
    engine.execute('ALTER SEQUENCE sectors_id_seq RESTART WITH 1;')
    engine.execute('ALTER SEQUENCE centerlines_id_seq RESTART WITH 1;')

    try:
        session.query(Pickup).delete()
        session.query(BlockfaceStatistic).delete()
        session.query(Centerline).delete()
        session.query(Sector).delete()
        session.query(ZoneGeneration).delete()
        session.query(Zone).delete()
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()

__all__ = ['set_db', 'get_db', 'db_sessionmaker', 'reset_db']
