"""
The rubbish-admin CLI application.
"""

import click
import os
import subprocess
import warnings
import time

from rubbish_geo_common.db_ops import set_db as _set_db, reset_db as _reset_db, get_db as _get_db
from .ops import (
    update_zone as _update_zone, insert_sector as _insert_sector, delete_sector as _delete_sector,
    show_sectors as _show_sectors, show_zones as _show_zones, show_dbs, run_cloud_sql_proxy
)

@click.group()
def cli():
    pass

@click.command(name="connect", short_help="Shell out to psql.")
@click.option("-p", "--profile", help="Connection profile to use. If not set uses default profile.")
def connect(profile):
    sp = subprocess.run(["which", "psql"], capture_output=True)
    if sp.returncode != 0:
        print("psql not installed, install that first.")
        return
    psql = sp.stdout.decode("utf-8").rstrip()
    connstr, conntype, _ = _get_db(profile)
    if connstr == None:
        print("database not set, set that first with set_db")
        return
    if conntype not in ["local", "gcp"]:
        print(f"connection type {conntype!r} not understood, must be one of [local, gcp]")

    if conntype == "gcp":
        # TODO: find a more elegant way of doing this -- execl is an exec process replacement, so
        # we actually currently orphan the cloud_sql_proxy background process as written.
        cloud_sql_proxy_process = run_cloud_sql_proxy(profile=profile)
        print("Waiting five seconds for cloud_sqp_proxy to start...")
        print(
            "WARNING: after exiting psql you will still have a cloud_sql_proxy listener on "
            "port 5432. To get rid of it find the PID of the process and kill it manually:\n"
            "$ lsof -i tcp:5432\n"
            "$ kill -s SIGTERM $PID\n"
            "A more elegant way of doing this is a TODO."
        )
        time.sleep(5)
        # cloud_sql_proxy_process.terminate()
    os.execl(psql, psql, connstr)

@click.command(name="get-db", short_help="Prints the DB connection strings.")
@click.option("-p", "--profile", help="Optional profile. If set, prints just that string.")
def get_db(profile):
    if profile is None:
        show_dbs()
    else:
        connstr, conntype, _ = _get_db(profile=profile)
        if connstr:
            if conntype == "gcp":
                warnings.warn(
                    "This is a GCP database, and GCP does not allow direct connections to Cloud "
                    "SQL. In order to connect to this database, you will first need to start up "
                    "a cloud_sql_proxy daemon process. To do this automatically use:\n"
                    f"$ rubbish-admin connect --profile {profile}"
                )
            print(connstr)
        else:
            print("Connection string not set.")

@click.command(name="set-db", short_help="Set the DB connection string.")
@click.argument("dbstr")
@click.argument("conntype")
@click.option("-c", "--conname", help="Optional connection name. Required if conntype is GCP.")
@click.option("-p", "--profile", help="Optional profile. If not set uses default profile.")
def set_db(dbstr, conntype, conname, profile):
    _set_db(dbstr, conntype, conname, profile=profile)

@click.command(name="reset-db", short_help="Reset the DB.")
@click.option("-p", "--profile", help="Optional profile. If not set uses default profile.")
def reset_db(profile):
    y_n = input("This will delete ALL data currently in the database. Are you sure? [Y/n]: ")
    if y_n == "y" or y_n == "yes" or y_n == "Y":
        _reset_db(profile=profile)
    elif y_n == "n" or y_n == "no":
        return
    else:
        print("invalid input, must reply y/n")
    pass

@click.command(name="update-zone", short_help="Write a new zone generation in and reticulates.")
@click.argument("osmnx_name")
@click.option("-n", "--name", help="Optional name, otherwise copies osmnx_name.", default=None)
@click.option("-p", "--profile", help="Optional profile. If not set uses default profile.")
def update_zone(osmnx_name, name, profile):
    if name is None:
        name = osmnx_name
    _update_zone(osmnx_name, name, profile=profile)

@click.command(name="show-zones", short_help="Pretty-prints zones in the database.")
@click.option("-p", "--profile", help="Optional profile. If not set uses default profile.")
def show_zones(profile):
    _show_zones(profile=profile)

@click.command(name="insert-sector", short_help="Inserts a new sector into the database.")
@click.argument("sector_name")
@click.argument("filepath")
@click.option("-p", "--profile", help="Optional profile. If not set uses default profile.")
def insert_sector(sector_name, filepath, profile):
    _insert_sector(sector_name, filepath, profile)

@click.command(name="delete-sector", short_help="Deletes a sector from the database.")
@click.option("-p", "--profile", help="Optional profile. If not set uses default profile.")
@click.argument("sector_name")
def delete_sector(sector_name, profile):
    _delete_sector(sector_name, profile=profile)

@click.command(name="show-sectors", short_help="Pretty-prints sectors in the database.")
@click.option("-p", "--profile", help="Optional profile. If not set uses default profile.")
def show_sectors(profile):
    _show_sectors(profile=profile)

cli.add_command(connect)
cli.add_command(get_db)
cli.add_command(set_db)
cli.add_command(reset_db)
cli.add_command(update_zone)
cli.add_command(show_zones)
cli.add_command(insert_sector)
cli.add_command(delete_sector)
cli.add_command(show_sectors)
