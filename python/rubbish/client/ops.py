"""
Python client library I/O methods.
"""
import sqlalchemy as sa
import shapely
from shapely.geometry import Point
import geoalchemy2
import warnings
from datetime import datetime, timedelta

from rubbish.common.db_ops import db_sessionmaker
from rubbish.common.orm import Pickup, Centerline, BlockfaceStatistic
from rubbish.common.consts import RUBBISH_TYPES, RUBBISH_TYPE_MAP

def _munge_pickups(pickups):
    if len(pickups) == 0:
        return

    # validate input and perform type conversions
    for pickup in pickups:
        if not isinstance(pickup, dict):
            raise ValueError(
                f"Pickups must be of type dict, but found pickup of type {type(pickup)} instead."
            )
        for attr in ["firebase_id", "type", "timestamp", "curb", "geometry"]:
            if attr not in pickup:
                raise ValueError(f"Found pickup missing required attribute {attr}.")
        try:
            geom = shapely.wkt.loads(pickup["geometry"])
        except shapely.errors.WKTReadingError:
            raise shapely.errors.WKTReadingError(
                f"Pickups include invalid geometry {pickup['geometry']!r}."
            )
        if not isinstance(geom, Point):
            raise ValueError(f"Found geometry of invalid type {type(geom)}.")
        pickup["geometry"] = geom
        for int_attr in ["firebase_id", "timestamp"]:
            try:
                v = int(float(pickup[int_attr]))
                pickup[int_attr] = v
            except ValueError:
                raise ValueError(
                    f"Found pickup with {int_attr} of non-castable type {type(v)}."
                )
        # the five minutes of padding are just in case there is clock skew
        if pickup["timestamp"] > (datetime.utcnow() + timedelta(minutes=5)).timestamp():
            raise ValueError(
                f"Found pickup with greater than expected UTC timestamp {pickup['timestamp']}. "
                f"Current server UTC UNIX time is {datetime.utcnow()}. Are you sure your "
                f"timestamp is actually a UTC UNIX timestamp?"
            )
        curb = pickup["curb"]
        if curb is not None and curb != "left" and curb != "right":
            raise ValueError(
                f"Found pickup with invalid curb value {curb} "
                f"(must be one of 'left', 'right')."
            )
        try:
            pickup["type"] = RUBBISH_TYPE_MAP[pickup["type"]]
        except KeyError:
            raise ValueError(f"Found pickup with type not in valid types {RUBBISH_TYPES!r}.")

    # Snap points to centerlines. Cf. https://postgis.net/workshops/postgis-intro/knn.html
    session = db_sessionmaker()()
    centerline_objs, pickup_objs = dict(), dict()
    for pickup in pickups:
        orig_point = pickup["geometry"]
        orig_point_wkt = f"SRID=4326;{str(orig_point)}"
        matches = (session
            .query(Centerline)
            .order_by(Centerline.geometry.distance_centroid(orig_point_wkt))
            .limit(100)
            .all()
        )
        if len(matches) == 0:
            raise ValueError("No centerlines in the database!")
        match, match_geom_wkt, dist = (session
            .query(
                Centerline,
                geoalchemy2.functions.ST_AsText(Centerline.geometry),
                geoalchemy2.functions.ST_Distance(Centerline.geometry, orig_point_wkt)
            )
            .order_by(Centerline.geometry.ST_Distance(orig_point_wkt))
            .first()
        )
        # unrectified coordinate values so these are approximate
        if dist > 0.0009:
            warnings.warn(
                f"Matching pickup {orig_point_wkt} to centerline {str(match.geometry)} "
                f"located >100m (but <1km) away. This indicates potential data problems."
            )
        if dist > 0.001:
            warnings.warn(
                f"{orig_point_wkt} is >1km from nearest centerline and was discarded."
            )
        
        match_geom = shapely.wkt.loads(match_geom_wkt)
        linear_reference = match_geom.project(orig_point, normalized=True)
        snapped_point = match_geom.interpolate(linear_reference, normalized=True)

        # For now, no curb means left curb. See the to-do item below this code block.
        if pickup['curb'] is None:
            pickup['curb'] = 'left'

        pickup_obj = Pickup(
            geometry=f'SRID=4326;{str(orig_point)}',
            snapped_geometry=f'SRID=4326;{str(snapped_point)}',
            centerline_id=match.id,
            firebase_id=pickup['firebase_id'],
            type=pickup['type'],
            timestamp=datetime.utcfromtimestamp(pickup['timestamp']),
            linear_reference=linear_reference,
            curb=0 if pickup['curb'] == 'left' else 1
        )

        if match.id not in centerline_objs:
            centerline_objs[match.id] = (match, match_geom)
        if match.id in pickup_objs:
            pickup_objs[match.id][pickup['curb']].append(pickup_obj)
        else:
            pickup_objs[match.id] = {'left': [], 'right': []}
            pickup_objs[match.id][pickup['curb']].append(pickup_obj)
        session.add(pickup_obj)

    # percentile calculation logic
    for centerline_id in centerline_objs:
        for curb in ['left', 'right']:
            centerline, centerline_geom = centerline_objs[centerline_id]
            matching_pickups = pickup_objs[centerline_id][curb]
            curb_as_int = 0 if curb == 'left' else 1

            if len(matching_pickups) <= 1:
                continue

            linear_ref_min, linear_ref_max = 1, 0
            for matching_pickup in matching_pickups:
                linear_ref = matching_pickup.linear_reference
                if linear_ref < linear_ref_min:
                    linear_ref_min = linear_ref
                if linear_ref > linear_ref_max:
                    linear_ref_max = linear_ref

            # skip if the run covered <50% of the length of the street
            linear_ref_coverage = linear_ref_max - linear_ref_min
            if linear_ref_coverage < 0.5:
                continue

            n_matching_pickups = len(matching_pickups)
            inferred_n_pickups = n_matching_pickups / linear_ref_coverage
            inferred_pickup_density = inferred_n_pickups / centerline.length_in_meters
            prior_information = (session
                .query(BlockfaceStatistic)
                .filter(
                    BlockfaceStatistic.centerline_id == centerline_id,
                    BlockfaceStatistic.curb == curb_as_int
                )
                .one_or_none()
            )
            kwargs = {'centerline_id': centerline_id, 'curb': curb_as_int}
            if prior_information is None:
                blockface_statistic = BlockfaceStatistic(
                    num_runs=1, rubbish_per_meter=inferred_pickup_density, **kwargs
                )
                session.add(blockface_statistic)
            else:
                updated_rubbish_per_meter = (
                    (prior_information.rubbish_per_meter *
                     prior_information.num_runs +
                     inferred_pickup_density) /
                    (prior_information.num_runs + 1)
                )
                blockface_statistic = BlockfaceStatistic(
                    num_runs=prior_information.num_runs + 1,
                    rubbish_per_meter=updated_rubbish_per_meter,
                    **kwargs
                )

    try:
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()

def write_pickups(pickups):
    """
    Writes pickups to the database. Pickups is expected to be a list of entries in the format:

    ```
    {"firebase_id": <int>,
     "type": <int, see key in docs>,
     "timestamp": <int; UTC UNIX timestamp>,
     "curb": <{left, right}; user indication of what side of the street the pickup occurred on>,
     "geometry": <str; POINT in WKT format>}
    ```

    All other keys included in the dict will be silently ignored.

    This list is to correspond with a single rubbish run, with items sequenced in the order in
    which the pickups were made.
    """
    return _munge_pickups(pickups)

def radial_get(coord, distance, include_na=False, offset=0):
    """
    Returns all blockface statistics for blockfaces containing at least one point at most
    ``distance`` away from ``coord``.

    Parameters
    ----------
    coord : (x, y) coordinate tuple
        Centerpoint for the scan.
    distance : int
        Distance (in meters) from centerpoint to scan for.
    include_na : bool, optional
        Whether or not to include blockfaces for which blockface statistics do not yet exist.
        Defaults to ``False``.

        Blockfaces with no statistics have not met the minimum threshold for assignment of
        statistics yet (at time of writing, this means that no runs touching at least 50% of
        the blockface have been saved to the database yet).

        The additional blockfaces returned when ``include_na=True`` is set will only have
        their geometry field set. All other fields will be `None`.
    offset : int, optional
        The results offset to use. Defaults to `0`, e.g. no offset.

        To prevent inappropriately large requests from overloading the database, this API is
        limited to returning 1000 items at a time. Use this parameter to fetch more results
        for a query exceeding this limit.

    Returns
    -------
    ``dict``
        Query result.
    """
    pass

def sector_get(sector_name, include_na=False, offset=0):
    """
    Returns all blockface statistics for blockfaces contained in a sector. Only blockfaces located
    completely within the sector count. Blockfaces touching sector edges are ok, blockfaces
    containing some points outside of the sector are not.

    Parameters
    ----------
    sector_name: str
        Unique sector name.
    include_na : bool, optional
        Whether or not to include blockfaces for which blockface statistics do not yet exist.
        Defaults to ``False``.

        Blockfaces with no statistics have not met the minimum threshold for assignment of
        statistics yet (at time of writing, this means that no runs touching at least 50% of
        the blockface have been saved to the database yet).

        The additional blockfaces returned when ``include_na=True`` is set will only have
        their geometry field set. All other fields will be `None`.
    offset : int, optional
        The results offset to use. Defaults to `0`, e.g. no offset.

        To prevent inappropriately large requests from overloading the database, this API is
        limited to returning 1000 items at a time. Use this parameter to fetch more results
        for a query exceeding this limit.

    Returns
    -------
    ``dict``
        Query result.
    """
    pass

def coord_get(coord, include_na=False):
    """
    Returns blockface statistics and run history for the set of blockfaces for the centerline
    closest to the given coordinate.

    Parameters
    ----------
    coord: (x, y) coordinate tuple
        Origin point for the snapped selection.
    include_na : bool, optional
        Whether or not to include blockfaces for which blockface statistics do not exist yet.
        Defaults to ``False``.

        Blockfaces with no statistics have not met the minimum threshold for assignment of
        statistics yet (at time of writing, this means that no runs touching at least 50% of
        the blockface have been saved to the database yet).

        When ``include_na=True``, the blockfaces returned will be that of the nearest centerline.

        When ``include_na=False``, the blockfaces returned will be that of the nearest centerline
        having at least one blockface statistic.
    
    Returns
    -------
    ``dict``
        Query result.    
    """
    pass

def run_get(run_id):
    """
    Returns blockface statistics and run-specific data for a specific run by id.

    Parameters
    ----------
    run_id : str
        The run id. Note: this is stored as ``firebase_id`` in the ``Pickups`` table.

    Returns
    -------
    ``dict``
        Query result.    
    """
    pass

__all__ = ['write_pickups', 'radial_get', 'sector_get', 'coord_get', 'run_get']
