"""
The rubbish-admin CLI application.
"""

import click
import os
import subprocess

from rubbish.common.db_ops import set_db as _set_db, reset_db as _reset_db, get_db as _get_db
from .ops import (
    update_zone as _update_zone, insert_sector as _insert_sector, delete_sector as _delete_sector,
    show_sectors as _show_sectors, show_zones as _show_zones
)

@click.group()
def cli():
    pass

@click.command(name="connect", short_help="Shell out to psql.")
def connect():
    sp = subprocess.run(["which", "psql"], capture_output=True)
    if sp.returncode != 0:
        print("psql not installed, install that first.")
        return
    connstr = _get_db()
    if connstr == None:
        print("database not set, set that first with set_db")
        return
    psql = sp.stdout.decode("utf-8").rstrip()
    os.execl(psql, psql, connstr)

@click.command(name="get-db", short_help="Prints the DB connection string.")
def get_db():
    connstr = _get_db()
    if connstr:
        print(connstr)
    else:
        print("Connection string not set.")

@click.command(name="set-db", short_help="Set the DB connection string.")
@click.argument("dbstr")
def set_db(dbstr):
    _set_db(dbstr)

@click.command(name="reset-db", short_help="Reset the DB.")
def reset_db():
    y_n = input("This will delete ALL data currently in the database. Are you sure? [y/n]: ")
    if y_n == "y" or y_n == "yes":
        _reset_db()
    elif y_n == "n" or y_n == "no":
        return
    else:
        print("invalid input, must reply y/n")
    pass

@click.command(name="update-zone", short_help="Write a new zone generation in and reticulates.")
@click.argument("osmnx_name")
@click.option("-n", "--name", help="Optional name, otherwise copies osmnx_name.", default=None)
def update_zone(osmnx_name, name):
    if name is None:
        name = osmnx_name
    _update_zone(osmnx_name, name)

@click.command(name="show-zones", short_help="Pretty-prints zones in the database.")
def show_zones():
    _show_zones()

@click.command(name="insert-sector", short_help="Inserts a new sector into the database.")
@click.argument("sector_name")
@click.argument("filepath")
def insert_sector(sector_name, filepath):
    _insert_sector(sector_name, filepath)

@click.command(name="delete-sector", short_help="Deletes a sector from the database.")
@click.argument("sector_name")
def delete_sector(sector_name):
    _delete_sector(sector_name)

@click.command(name="show-sectors", short_help="Pretty-prints sectors in the database.")
def show_sectors():
    show_sectors()

cli.add_command(connect)
cli.add_command(get_db)
cli.add_command(set_db)
cli.add_command(reset_db)
cli.add_command(update_zone)
cli.add_command(show_zones)
cli.add_command(insert_sector)
cli.add_command(delete_sector)
