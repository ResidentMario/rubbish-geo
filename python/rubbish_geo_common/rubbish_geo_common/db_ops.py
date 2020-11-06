"""
Generic DB operations unrelated to application state.
"""

import click
import pathlib
import os
import configparser

import sqlalchemy as sa
from sqlalchemy.orm.session import sessionmaker
from rubbish_geo_common.orm import (
    Zone, ZoneGeneration, Sector, Centerline, Pickup, BlockfaceStatistic
)

APPDIR = pathlib.Path(click.get_app_dir("rubbish", force_posix=True))

def set_db(dbstr, conntype, conname=None, profile=None):
    """
    Sets the target database connection settings (writing the input value to disk).
    """
    if conntype not in ["local", "gcp"]:
        raise ValueError("conntype must be set to one of [local, gcp].")
    if profile is None:
        profile = 'default'
    if conname is None:
        if conntype == 'gcp':
            raise ValueError(
                "Databases of the 'gcp' type must specify a connection name, as this value "
                "is required by the GCP cloud_sql_proxy. For more information refer to "
                "https://cloud.google.com/sql/docs/postgres/sql-proxy."
            )
        else:
            conntype = 'unset'

    if not APPDIR.exists():
        os.makedirs(APPDIR)

    cfg_fp = APPDIR / "config"
    cfg = configparser.ConfigParser()
    if cfg_fp.exists():
        cfg.read(cfg_fp)
    cfg[profile] = {'connstr': dbstr, 'type': conntype, 'conname': conname}
    with open(cfg_fp, "w") as f:
        cfg.write(f)

def get_db_cfg():
    cfg_fp = APPDIR / "config"
    if not cfg_fp.exists():
        return None
    cfg = configparser.ConfigParser()
    cfg.read(cfg_fp)
    return cfg

def get_db(profile=None):
    """
    Gets the database connection string (what gets passed to psql or sqlalchemy at runtime), type
    (local or gcp), and connection name (used by the cloud_sql_proxy and required for local
    connections to GCP databases.
    """
    if 'RUBBISH_POSTGIS_CONNSTR' in os.environ:
        return os.environ['RUBBISH_POSTGIS_CONNSTR'], 'local', 'unset'

    if profile is None:
        profile = 'default'

    cfg = get_db_cfg()
    return cfg[profile]['connstr'], cfg[profile]['type'], cfg[profile]['conname']

def db_sessionmaker(profile=None):
    """
    Returns a sessionmaker object for creating DB sessions.
    """
    if profile is None:
        profile = 'default'
    
    connstr, _, _ = get_db(profile=profile)
    if connstr == None:
        raise ValueError("connection string not set, run set_db first")
    engine = sa.create_engine(connstr)
    return sessionmaker(bind=engine)

def reset_db(profile=None):
    """
    Resets the current database, deleting all data.
    """
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

__all__ = ['set_db', 'get_db_cfg', 'get_db', 'db_sessionmaker', 'reset_db']
