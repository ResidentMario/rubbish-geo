"""
Admin methods for interacting with zones.
"""
import os
from datetime import datetime
import warnings
import math

import osmnx as ox
import geopandas as gpd
import sqlalchemy as sa
from geopy.distance import distance
import shapely
from rich.console import Console
from rich.table import Table

from rubbish.common.db_ops import db_sessionmaker, get_db
from rubbish.common.orm import Zone, ZoneGeneration, Centerline, Sector

def _get_name_for_centerline_edge(G, u, v):
    """
    Returns a nice name for a specific centerline in the given osmnx graph. `u` and `v` are the
    (networkx) IDs of the centerline endpoints.
    
    We format centerline names thusly:
    * "Unknown" if the centerline has no name.
    * X b/w Y and Z format for ordinary centerlines linked to other centerlines on both ends.
      * In the case of multiple intersections, Y and Z are chosen based on length. The longest
        adjacent centerline is the one which gifts its name.
    * X off Y for dead-ends.
    * X for centerlines only connected to other centerlines with the same name.
    * X for centerlines not connected to any other centerlines at all.
    
    Example output: 'Park View Avenue b/w Winsor Avenue and Palm Drive'
    
    Note that these names are non-unique, if you need a UID, use the computed ID instead.
    """
    def c_len(u, v):
        return math.sqrt(abs(G.nodes[u]['x'] - G.nodes[v]['x'])**2 +
                         abs(G.nodes[u]['y'] - G.nodes[v]['y'])**2)
    def get_name(G, u, v):
        struct = G[u][v][0]
        if 'name' not in struct:
            return "Unknown"
        
        n = struct['name']
        if isinstance(n, str):
            return n
        elif isinstance(n, list):
            return n[0]
        else:
            return "Unknown"
    
    name = get_name(G, u, v)
    if name == "Unknown":
        return "Unknown"

    u_neighbors = list(G[u].keys())
    v_neighbors = list(G[v].keys())

    # TODO: make sure southern edge is first and northern edge is last, as per
    # `point_side_of_centerline` rules.
    
    u_w_maxlen, u_w_maxlen_idx = 0, None
    for w_i, w in enumerate(u_neighbors):
        if get_name(G, u, w) == name:
            continue
        u_w_cand_len = c_len(u, w)
        if u_w_cand_len > u_w_maxlen:
            u_w_maxlen = c_len(u, w)
            u_w_maxlen_idx = w_i

    v_w_maxlen, v_w_maxlen_idx = 0, None
    for w_i, w in enumerate(v_neighbors):
        if get_name(G, v, w) == name:
            continue
        v_w_cand_len = c_len(v, w)
        if v_w_cand_len > v_w_maxlen:
            v_w_maxlen = c_len(v, w)
            v_w_maxlen_idx = w_i
    
    # Centerline names entries may be NaN, a str name, or a list[str] of names. AFAIK there
    # isn't any interesting information in the ordering of names, so we'll use first-wins
    # rules for list[str]. For NaN names, we'll insert an "Unknown" string.
    if v_w_maxlen_idx is not None:
        w = v_neighbors[v_w_maxlen_idx]
        v_w_name = get_name(G, v, w)
    else:
        v_w_name = None
    if u_w_maxlen_idx is not None:
        w = u_neighbors[u_w_maxlen_idx]
        u_w_name = get_name(G, u, w)
    else:
        u_w_name = None
    
    if u_w_maxlen_idx is None and v_w_maxlen_idx is None:
        return name
    elif u_w_maxlen_idx is None:
        return f"{name} off {v_w_name}"
    elif v_w_maxlen_idx is None:
        return f"{name} off {u_w_name}"
    else:
        return f"{name} b/w {v_w_name} and {u_w_name}"

def _calculate_linestring_length(linestring):
    length = 0
    for idx_b in range(1, len(linestring.coords)):
        idx_a = idx_b - 1
        # NOTE: geopy uses (y, x) order, shapely uses (x, y) order.
        length += distance(linestring.coords[idx_a][::-1], linestring.coords[idx_b][::-1]).meters
    return length

def update_zone(osmnx_name, name, centerlines=None, profile=None):
    """
    Updates a zone, plopping the new centerlines into the database.

    The `osmnx_name` and `name` arguments map to database fields.
    
    The optional `centerlines` argument is used to avoid a network request in testing.
    """
    session = db_sessionmaker(profile=profile)()

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
        G = ox.graph_from_place(osmnx_name, simplify=True, network_type="drive")
        _, edges = ox.graph_to_gdfs(G)

        # Centerline names entries may be NaN, a str name, or a list[str] of names. AFAIK there
        # isn't any interesting information in the ordering of names, so we'll use first-wins
        # rules for list[str]. For NaN names, we'll insert an "Unknown" string.
        #
        # Centerline osmid values cannot be NaN, but can map to a list. It's unclear why this
        # is the case.
        names = []
        for edge in G.edges:
            u, v, _ = edge
            names.append(_get_name_for_centerline_edge(G, u, v))
        edges = edges.assign(
            name=names,
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
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            centerlines.to_postgis("centerlines", conn, if_exists="append")
    except:
        session.rollback()
        raise
    finally:
        session.close()

def show_zones(profile=None):
    """Pretty-prints a list of zones in the database."""
    session = db_sessionmaker(profile=profile)()
    zones = (session
        .query(Zone)
        .all()
    )
    if len(zones) == 0:
        print("No zones in the database. :(")
    else:
        console = Console()
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("ID", justify="left")
        table.add_column("Name", justify="left")
        table.add_column("OSMNX Name", justify="left")
        table.add_column("# Generations", justify="right")
        table.add_column("# Centerlines", justify="right")
        for zone in zones:
            zone_gen_ids = [gen.id for gen in zone.zone_generations]
            n_centerlines = (
                session.query(Centerline).filter(Centerline.id in zone_gen_ids).count()
            )
            table.add_row(
                str(zone.id), zone.name, zone.osmnx_name, str(len(zone.zone_generations)),
                str(n_centerlines)
            )
        console.print(table)

def _validate_sector_geom(filepath):
    if not os.path.exists(filepath) or os.path.isdir(filepath):
        raise ValueError(f"File {filepath} does not exist or is not a file.")
    try:
        sector_shape = (gpd.read_file(filepath)
            .assign(tmpcol=0)
            .dissolve(by='tmpcol')
            .geometry.iloc[0]
        )
    except ValueError:
        raise ValueError(
            f"Could not decode the file at {filepath}, are you sure it's in GeoJSON format?"
        )

    if sector_shape.geom_type == "Polygon":
        sector_shape = shapely.geometry.MultiPolygon([sector_shape])  # DB requirement
    elif sector_shape.geom_type != "MultiPolygon":
        raise ValueError(f"Input sector has unsupported {sector_shape.geom_type} union type.")
    return sector_shape

def insert_sector(sector_name, filepath, profile=None):
    session = db_sessionmaker(profile=profile)()

    if session.query(Sector).filter_by(name=sector_name).count() != 0:
        raise ValueError(
            f"The database already contains a sector with the name {sector_name!r}. "
            f"If you are redefining the same sector, please run `delete_sector({sector_name!r})` "
            f"first. Otherwise, please choose a different name for this sector."
        )

    sector_shape = _validate_sector_geom(filepath)
    sector = Sector(name=sector_name, geometry=f'SRID=4326;{str(sector_shape)}')
    session.add(sector)
    try:
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()

def delete_sector(sector_name, profile=None):
    if profile is None:
        profile = 'default'
    session = db_sessionmaker(profile=profile)()

    sector = session.query(Sector).filter_by(name=sector_name).one_or_none()
    if sector is None:
        raise ValueError(f"Cannot delete sector {sector_name!r}: no such sector in the database.")

    session.delete(sector)
    try:
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()

def show_sectors(profile=None):
    """Pretty-prints a list of sectors in the database."""
    session = db_sessionmaker(profile=profile)()
    
    sectors = session.query(Sector).all()
    if len(sectors) == 0:
        print("No sectors in the database. :(")

    console = Console()
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("ID", justify="left")
    table.add_column("Name", justify="left")
    for sector in session.query(Sector).all():
        table.add_row(str(sector.id), sector.name)
    console.print(table)

__all__ = ['update_zone', 'show_zones', 'insert_sector', 'delete_sector', 'show_sectors']
