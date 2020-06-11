"""
Admin methods for interacting with zones.
"""

import os
import json
from json import JSONDecodeError
from datetime import datetime

import osmnx as ox
import geopandas as gpd
import sqlalchemy as sa
from geopy.distance import distance
import shapely
import rich

from rubbish.common.db_ops import db_sessionmaker, get_db
from rubbish.common.orm import Zone, ZoneGeneration, Centerline

def _calculate_linestring_length(linestring):
    length = 0
    for idx_b in range(1, len(linestring.coords)):
        idx_a = idx_b - 1
        length += distance(linestring.coords[idx_a], linestring.coords[idx_b]).meters
    return length

def update_zone(osmnx_name, name, centerlines=None):
    """
    Updates a zone, plopping the new centerlines into the database.

    The `osmnx_name` and `name` arguments map to database fields.
    
    The optional `centerlines` argument is used to avoid a network request in testing.
    """
    session = db_sessionmaker()()

    # insert zone
    # NOTE: flush writes DB ops to the database's transactional buffer without actually
    # performing a commit (and closing the transaction). This is important because it 
    # allows us to reserve a primary key ID from the corresponding auto-increment 
    # sequence, which we need when we use it as a foreign key. See SO#620610.
    if name is None:
        name = osmnx_name
    zone_query = (session
        .query(Zone)
        .filter(Zone.osmnx_name == osmnx_name)
        .one_or_none()
    )
    zone_already_exists = zone_query is not None
    if zone_already_exists:
        zone = zone_query
        session.close()
    else:
        zone = Zone(osmnx_name=osmnx_name, name=name)
        session.add(zone)
        session.flush()

    # modify old and insert new zone generation
    if zone_already_exists:
        zone_generation_query = (session
            .query(ZoneGeneration)
            .filter(ZoneGeneration.zone_id == zone.id)
            .order_by(ZoneGeneration.generation)
            .all()
        )
        next_zone_generation = zone_generation_query[-1].generation + 1
    else:
        next_zone_generation = 0
    zone_generation = ZoneGeneration(
        zone_id=zone.id, generation=next_zone_generation, final_timestamp=None
    )
    session.add(zone_generation)
    session.flush()

    # insert centerlines
    if centerlines is None:
        G = ox.graph_from_place(osmnx_name, network_type="drive")
        _, edges = ox.graph_to_gdfs(G)

        # Centerline names entries may be NaN, a str name, or a list[str] of names. AFAIK there
        # isn't any interesting information in the ordering of names, so we'll use first-wins
        # rules for list[str]. For NaN names, we'll insert an "Unknown" string.
        #
        # Centerline osmid values cannot be NaN, but can map to a list. It's unclear why this
        # is the case.
        edges = edges.assign(
            name=edges.name.map(
                lambda n: n if isinstance(n, str) else n[0] if isinstance(n, list) else "Unknown"
            ),
            osmid=edges.osmid.map(lambda v: v if isinstance(v, int) else v[0])
        )
        centerlines = gpd.GeoDataFrame(
            {"first_zone_generation": zone_generation.id, "last_zone_generation": None,
             "zone_id": zone.id, "osmid": edges.osmid, "name": edges.name},
            index=range(len(edges)),
            geometry=edges.geometry
        )
        centerlines.crs = "epsg:4326"
        centerlines["length_in_meters"] = centerlines.geometry.map(_calculate_linestring_length)
    
    else:
        centerlines["length_in_meters"] = centerlines.geometry.map(_calculate_linestring_length)        
    conn = sa.create_engine(get_db())

    # Cap the previous centerline generations (see previous comment).
    previously_current_centerlines = (session
        .query(Centerline)
        .filter_by(zone_id=zone.id, last_zone_generation=None)
        .all()
    )
    for previously_current_centerline in previously_current_centerlines:
        previously_current_centerline.last_zone_generation = next_zone_generation - 1

    # Set the current zone generation's final timestamp.
    current_zone_generation = (session
        .query(ZoneGeneration)
        .filter_by(zone_id=zone.id)
        .order_by(sa.desc(ZoneGeneration.id))
        .first()
    )
    if current_zone_generation:
        current_zone_generation.final_timestamp = datetime.now()

    session.add(zone)
    session.add(zone_generation)

    try:
        session.commit()
        # TODO: if the session (which writes zone and zone_generation information) clears, but the
        # centerlines write (which geopandas executes in its own separate transaction, but which
        # depends on the success of the first transaction due to foreign key constrains) fails,
        # this will technically result in inconsistent state. For now I'm ignoring this problem.
        centerlines.to_postgis("centerlines", conn, if_exists="append")
    except:
        session.rollback()
        raise
    finally:
        session.close()

# TODO: WIP below
def show_zones():
    """Pretty-prints a list of zones in the database."""
    session = db_sessionmaker()()
    zones = (session
        .query(Zone)
        .all()
    )
    if len(zones) == 0:
        print("No zones in the database. :(")
    else:
        console = rich.Console()
        table = rich.Table(show_header=True, header_style="bold magenta")
        table.add_column("ID", justify="left")
        table.add_column("Name", justify="left")
        table.add_column("OSMNX Name", justify="left")
        table.add_column("# Generations", justify="right")
        table.add_column("# Centerlines", justify="right")
        for zone in zones:
            table.add_row(
                Zone.id, Zone.name, Zone.osmnx_name, len(Zone.zone_generations), "TODO"
            )
        console.print(table)

def _validate_sector_geom(filepath):
    if not os.path.exists(filepath) or not os.path.isdir(filepath):
        raise ValueError(f"File {filepath} does not exist or is not a file.")
    with open(filepath, "r") as fp:
        try:
            sector_shape = json.loads(filepath.read())
        except JSONDecodeError:
            raise ValueError(
                f"Could not decode the file at {filepath}, are you sure it's in GeoJSON format?"
            )
    try:
        sector_shape = shapely.geometry.shape(sector_shape)
    except ValueError:
        raise ValueError(
            f"Could not decode the file at {filepath}, are you sure it's in GeoJSON format?"
        )
    if sector_shape.geom_type not in ["Polygon", "MultiPolygon", "GeometryCollection"]:
        raise ValueError(f"Input sector has unsupported {sector_shape.geom_type} type.")
    return sector_shape

def insert_sector(sector_name, filepath):
    # TODO: fail if sector_name already exists (force delete_sector first).
    sector_shape = _validate_sector_geom(filepath)
    pass

def delete_sector(sector_name):
    pass

def show_sectors():
    """Pretty-prints a list of sectors in the database."""
    pass