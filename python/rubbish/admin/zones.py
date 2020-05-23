"""
API methods for interacting with zones.
"""

import osmnx as ox
import geopandas as gpd
from rubbish.common.db import db_sessionmaker, get_db
from rubbish.common.orm import Zone, ZoneGeneration
import sqlalchemy as sa

def update_zone(osmnx_name, name):
    session = db_sessionmaker()()

    # munge zone
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
    else:
        largest_zone_by_id = (session
            .query(Zone)
            .order_by(sa.desc(Zone.id))
            .first()
        )
        next_zone_id = largest_zone_by_id.id + 1 if largest_zone_by_id else 0
        zone = Zone(id=next_zone_id, osmnx_name=osmnx_name, name=name)

    # munge zone generation
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
    largest_zone_generation_by_id = (session
        .query(ZoneGeneration)
        .order_by(sa.desc(ZoneGeneration.id))
        .first()
    )
    next_zone_generation_id =\
        largest_zone_generation_by_id.id + 1 if largest_zone_generation_by_id else 0
    zone_generation = ZoneGeneration(
        id=next_zone_generation_id, zone_id=zone.id,
        generation=next_zone_generation, final_timestamp=None
    )

    G = ox.graph_from_place(osmnx_name, network_type="drive")
    _, edges = ox.graph_to_gdfs(G)
    centerlines = gpd.GeoDataFrame(
        {'first_zone_generation': 0, 'last_zone_generation': None, 'zone_id': 0},
        index=range(len(edges)),
        geometry=edges.geometry
    )
    con = sa.create_engine(get_db())

    session.add(zone)
    session.add(zone_generation)
    try:
        session.commit()
        centerlines.to_postgis("centerlines", con, if_exists="append")
    except:
        session.rollback()
        raise
    finally:
        session.close()

    print(session)

    # TODO: get correct zone generation for this osmnx_name

    # TODO: get graph
    # G = ox.graph_from_place(place=osmnx_name, network_type="drive")
    # _, gdf_edges = ox.graph_to_gdfs(G)

    # TODO: if this is not the first generation, reticulate

    # TODO: format result for writing and write it
