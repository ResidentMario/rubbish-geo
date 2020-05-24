"""
Admin methods for interacting with zones.
"""

from datetime import datetime
import osmnx as ox
import geopandas as gpd
from rubbish.common.db import db_sessionmaker, get_db
from rubbish.common.orm import Zone, ZoneGeneration, Centerline
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

    # TODO: intergenerational reticulation.
    #
    # The current behavior is that every time a zone is overwritten, every centerline
    # in the previous zone generation is capped at that generation, and the complete
    # new street grid of the current generation is written into the DB.
    #
    # The long-term correct behavior would be to merge the old and new street grid:
    # overwrite only where there are changes, and perform smart reticulation of points
    # when doing so is useful.
    G = ox.graph_from_place(osmnx_name, network_type="drive")
    _, edges = ox.graph_to_gdfs(G)
    centerlines = gpd.GeoDataFrame(
        {"first_zone_generation": next_zone_generation_id, "last_zone_generation": None,
         "zone_id": zone.id},
        index=range(len(edges)),
        geometry=edges.geometry
    )
    centerlines.crs = "epsg:4326"
    con = sa.create_engine(get_db())

    # Cap the previous centerline generations (see previous comment).
    previously_current_centerlines = (session
        .query(Centerline)
        .filter_by(zone_id=zone.id, last_zone_generation=None)
        .all()
    )
    for previously_current_centerline in previously_current_centerlines:
        previously_current_centerline.last_zone_generation = next_zone_generation_id - 1

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
        centerlines.to_postgis("centerlines", con, if_exists="append")
    except:
        session.rollback()
        raise
    finally:
        session.close()
