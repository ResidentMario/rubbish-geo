"""
Generic DB operations unrelated to application state.
"""

import click
import pathlib
import os
import configparser
import warnings
import time

import sqlalchemy as sa
from sqlalchemy.orm.session import sessionmaker
from rubbish_geo_common.orm import (
    Zone, ZoneGeneration, Sector, Centerline, Pickup, BlockfaceStatistic
)

APPDIR = pathlib.Path(click.get_app_dir("rubbish", force_posix=True))

def run_cloud_sql_proxy(profile, force_download=False):
    """
    Internal method. Does the song and dance Google requires to shell psql through to a DB.
    """
    import pathlib
    import click
    import subprocess
    import socket
    import stat
    import requests

    if profile is None:
        profile = 'default'

    APPDIR = pathlib.Path(click.get_app_dir("rubbish", force_posix=True))
    outpath = APPDIR / "cloud_sql_proxy"
    if not outpath.exists() or force_download:
        # this is the macOS path, so this method only currently works on macOS
        dl_url = "https://dl.google.com/cloudsql/cloud_sql_proxy.darwin.amd64"
        proxy_bytes = requests.get(dl_url)
        proxy_bytes.raw.decode_content = True
        with open(outpath, "wb") as f:
            try:
                f.write(proxy_bytes.content)
            except PermissionError:
                raise PermissionError(
                    "Could not download the cloud_sql_proxy script to your local home folder "
                    "due to a permissions error. Follow the instructions in the GCP docs "
                    "(https://cloud.google.com/sql/docs/postgres/sql-proxy) and download the "
                    "executable to the ~/.rubbish/cloud_sql_proxy path on your local machine."
                )

        try:
            os.chmod(outpath, stat.S_IEXEC)
        except OSError:
            raise OSError(
                "Could not mark the cloud_sql_proxy script as executable. You may have to do "
                "this yourself: run 'chmod +x ~/.rubbish/cloud_sql_proxy' in the terminal."
            )

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        port_occupied = s.connect_ex(('localhost', 5432)) == 0
    if port_occupied:
        raise OSError(
            "This method needs to launch the cloud_sql_proxy daemon on port 5432, but port is "
            "already in use. You will have to free the port first."
        )

    _, _, conname = get_db(profile)
    popen = subprocess.Popen([f"{outpath.as_posix()}", f"-instances={conname}=tcp:5432"])
    print("Launched cloud_sql_proxy process with PID {popen.pid}.")
    return popen

def shut_down_cloud_sql_proxy(popen):
    """
    Shuts down (terminates) a Cloud SQL Proxy process, as returned by `run_cloud_sql_proxy`.
    """
    pid = popen.pid
    try:
        popen.terminate()
    except:
        warnings.warn(
            f"Could not terminate Cloud SQL Proxy process (PID {pid}), killing it instead."
        )
        popen.kill()

class OptionalCloudSQLProxyProcess:
    """
    Context manager class which launches a cloud SQL proxy process in the background if one is
    needed, and manages the lifecycle of that process (startup/shutdown).
    
    This is not needed when connecting to a local database. In that case, this context manager
    does nothing. Hence "Optional".
    """
    def __init__(self, profile, wait=5, force_download=False):
        self.profile = profile
        self.wait = wait
        self.force_download = force_download

        _, conntype, _ = get_db(self.profile)
        self.conntype = conntype

    def __enter__(self):
        if self.conntype == 'gcp':
            process = run_cloud_sql_proxy(self.profile, force_download=self.force_download)
            self.process = process

            print(f"Waiting {self.wait} seconds for cloud_sql_proxy process to initialize...")
            time.sleep(self.wait)
            print(f"Finished waiting, continuing execution...")
    
    def __exit__(self, type, value, traceback):
        if self.conntype == 'gcp':
            shut_down_cloud_sql_proxy(self.process)

def set_db(profile, connstr, conntype, conname=None):
    """
    Sets the target database connection settings (writing the input value to disk).
    """
    if conntype not in ["local", "gcp"]:
        raise ValueError("conntype must be set to one of [local, gcp].")
    if conname is None:
        if conntype == 'gcp':
            raise ValueError(
                "Databases of the 'gcp' type must specify a connection name, as this value "
                "is required by the GCP cloud_sql_proxy. For more information refer to "
                "https://cloud.google.com/sql/docs/postgres/sql-proxy."
            )
        conname = 'unset'

    if not APPDIR.exists():
        os.makedirs(APPDIR)

    cfg_fp = APPDIR / "config"
    cfg = configparser.ConfigParser()
    if cfg_fp.exists():
        cfg.read(cfg_fp)
    cfg[profile] = {'connstr': connstr, 'conntype': conntype, 'conname': conname}
    with open(cfg_fp, "w") as f:
        cfg.write(f)

def get_db_cfg():
    cfg_fp = APPDIR / "config"
    if not cfg_fp.exists():
        return None
    cfg = configparser.ConfigParser()
    cfg.read(cfg_fp)
    return cfg

def get_db(profile):
    """
    Gets the database connection string (what gets passed to psql or sqlalchemy at runtime), type
    (local or gcp), and connection name (used by the cloud_sql_proxy and required for local
    connections to GCP databases.
    """
    if 'RUBBISH_POSTGIS_CONNSTR' in os.environ:
        return os.environ['RUBBISH_POSTGIS_CONNSTR'], profile, 'unset'

    cfg = get_db_cfg()
    if cfg is None:
        raise ValueError("The Rubbish configuration file is empty or does not exist.")
    if profile not in cfg:
        raise ValueError(f"Rubbish configuration file does not have a profile named {profile!r}.")
    
    cfg_profile = cfg[profile]
    if 'connstr' not in cfg_profile:
        raise ValueError(f"Rubbish connection profile {profile!r} is missing a connstr field.")
    if 'conntype' not in cfg_profile:
        raise ValueError(f"Rubbish connection profile {profile!r} is missing a conntype field.")
    if 'conname' not in cfg_profile:
        raise ValueError(f"Rubbish connection profile {profile!r} is missing a conname field.")

    return cfg_profile['connstr'], cfg_profile['conntype'], cfg_profile['conname']

def db_sessionmaker(profile):
    """
    Returns a sessionmaker object for creating DB sessions.
    """
    connstr, _, _ = get_db(profile)
    if connstr == None:
        raise ValueError("connection string not set, run set_db first")
    engine = sa.create_engine(connstr)
    return sessionmaker(bind=engine)

def reset_db(profile, wait=5, force_download=False):
    """
    Resets the current database, deleting all data.
    """
    with OptionalCloudSQLProxyProcess(profile, wait=wait, force_download=force_download):
        session = db_sessionmaker(profile)()

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
            engine.dispose()

__all__ = [
    'set_db', 'get_db_cfg', 'get_db', 'db_sessionmaker', 'reset_db', 'run_cloud_sql_proxy',
    'OptionalCloudSQLProxyProcess'
]
