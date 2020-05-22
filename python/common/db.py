# Generic DB operations unrelated to application state.
import click
import pathlib
import os
import sqlalchemy as sa
from sqlalchemy.orm.session import sessionmaker
from .orm import Zone, ZoneGeneration, Sector, Centerline, Pickup

APPDIR = pathlib.Path(click.get_app_dir("rubbish", force_posix=True))

def set_db(dbstr):
    """
    Sets the target database (writing the input value to disk).
    """
    if not APPDIR.exists():
        os.makedirs(APPDIR)
    with open(APPDIR / "config", "w") as f:
        f.write(dbstr)

def get_db():
    """
    Gets the current database. Returns None if unset.
    """
    cfg = APPDIR / "config"
    if not cfg.exists():
        return None
    with open(APPDIR / "config", "r") as f:
        return f.read()

def reset_db():
    """
    Resets the current database, deleting all data.
    """
    connstr = get_db()
    if connstr == None:
        raise ValueError("connection string not set, run set_db first")
    engine = sa.create_engine(connstr)
    session = sessionmaker(bind=engine)()
    try:
        session.query(Pickup).delete(synchronize_session=False)
        session.query(Centerline).delete(synchronize_session=False)
        session.query(Sector).delete(synchronize_session=False)
        session.query(ZoneGeneration).delete(synchronize_session=False)
        session.query(Zone).delete(synchronize_session=False)
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()
