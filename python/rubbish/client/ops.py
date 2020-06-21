"""
Python client library I/O methods.
"""
import warnings
from datetime import datetime, timedelta
from collections import defaultdict
import json

import sqlalchemy as sa
import shapely
from shapely.geometry import Point, LineString
import geoalchemy2
from geoalchemy2.shape import to_shape

from rubbish.common.db_ops import db_sessionmaker
from rubbish.common.orm import Pickup, Centerline, BlockfaceStatistic
from rubbish.common.consts import RUBBISH_TYPES, RUBBISH_TYPE_MAP

def point_side_of_centerline(point_geom, centerline_geom):
    """
    Which side of a centerline a point lies on.

    Parameters
    ----------
    point_geom: ``shapely.geometry.Point``
        Point geometry.
    centerline_geom: ``shapely.geometry.LineString``
        Centerline geometry.
    
    Returns
    -------
    0 if point is leftward or on the line exactly, 1 if rightward.
    """
    # To determine centerline cardinality, ignore the winding direction of the linestring
    # and use the following rule.
    #
    # Starting point is southernmost endpoint. If the endpoints are tied, starting point is the
    # southwesternmost endpoint.
    #
    # Ending point is the northernmost endpoint. If the endpoints are tied, ending point is the
    # northeasternmost endpoint.
    #
    # Note: shapely encodes points in (x, y) format.
    start, stop = centerline_geom.coords[0], centerline_geom.coords[-1]
    if start[1] > stop[1]:
        centerline_geom = LineString(centerline_geom.coords[::-1])
    elif start[1] == stop[1]:
        if start[0] > stop[0]:
            centerline_geom = LineString(centerline_geom.coords[::-1])
    
    lr = centerline_geom.project(point_geom, normalized=True)  # linear reference
    linear_approx_start, linear_approx_stop = lr - 0.01, lr + 0.01
    start_geom = centerline_geom.interpolate(linear_approx_start, normalized=True)
    stop_geom = centerline_geom.interpolate(linear_approx_stop, normalized=True)
    x_start, y_start, x_stop, y_stop = start_geom.x, start_geom.y, stop_geom.x, stop_geom.y
    p_x, p_y = point_geom.x, point_geom.y
    d = (p_x - x_start) * (y_stop - y_start) - (p_y - y_start) * (x_stop - x_start)
    return 0 if d <= 0 else 1

def nearest_centerline_to_point(point_geom, session, rank=0, check_distance=False):
    """
    Returns the centerline nearest to the given point in the database.

    Rank controls the point chosen, e.g. rank=0 means the nearest centerline, rank=1 means the
    second nearest, etcetera.

    Implementation uses a two-step KNN -> ST_DISTANCE match. Refer to the page
    https://postgis.net/workshops/postgis-intro/knn.html for more information.
    
    In the future we may introduce a cache of morphological tesselations into the database to
    to speed up match times.

    Parameters
    ----------
    point_geom : ``shapely.geometry.Point``
        Centerpoint of interest.
    session: The database session.
    rank : ``int``, default 0
        The rank of the centerline to return. Zero-indexed, so 0 means the closest centerline,
        1 means second-closest, and so on.
    check_distance: ``bool``, default False
        Whether or not to ignore distance insert constraints. Should only be used in testing.

    Returns
    -------
    ``rubbish.common.orm.Centerline object``
        The centerline matched.
    """
    if rank > 100:
        raise ValueError("Cannot retrieve centerline match with rank > 100.")
    point_geom_wkt = f"SRID=4326;{str(point_geom)}"
    matches = (session
        .query(Centerline)
        .order_by(Centerline.geometry.distance_centroid(point_geom_wkt))
        .limit(100)
        .all()
    )
    if len(matches) == 0:
        raise ValueError("No centerlines in the database!")
    if rank >= len(matches):
        raise ValueError(
            f"Cannot return result with rank {rank}: there are only {len(matches)} centerlines "
            f"in the database."
        )
    match, dist = (session
        .query(
            Centerline,
            geoalchemy2.functions.ST_Distance(Centerline.geometry, point_geom_wkt)
        )
        .order_by(Centerline.geometry.ST_Distance(point_geom_wkt))
        .offset(rank)
        .first()
    )
    # unrectified coordinate values so these distance are approximate
    if not check_distance:
        if dist > 0.0009:
            warnings.warn(
                f"Matching point {point_geom_wkt} to centerline {str(match.geometry)} "
                f"located >~100m (but <~1km) away. This indicates potential data problems."
            )
        if dist > 0.001:
            warnings.warn(
                f"{point_geom_wkt} is >~1km from nearest centerline and was discarded."
            )
    return match

def write_pickups(pickups, check_distance=True):
    """
    Writes pickups to the database. Pickups is expected to be a list of entries in the format:

    ```
    {"firebase_id": <int>,
     "firebase_run_id": <int>,
     "type": <int, see key in docs>,
     "timestamp": <int; UTC UNIX timestamp>,
     "curb": <{left, right, None}; user statement of side of the street>,
     "geometry": <str; POINT in WKT format>}
    ```

    All other keys included in the dict will be silently ignored.

    This list is to correspond with a single rubbish run, with items sequenced in the order in
    which the pickups were made.
    """
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
            geom = pickup["geometry"]
        except shapely.errors.WKTReadingError:
            raise shapely.errors.WKTReadingError(
                f"Pickups include invalid geometry {pickup['geometry']!r}."
            )
        if not isinstance(geom, Point):
            raise ValueError(f"Found geometry of invalid type {type(geom)}.")
        pickup["geometry"] = geom
        for int_attr in ["firebase_id", "timestamp"]:
            try:
                pickup[int_attr] = int(float(pickup[int_attr]))
            except ValueError:
                raise ValueError(f"Found pickup with {int_attr} of non-castable type.")
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

    session = db_sessionmaker()()

    # Snap points to centerlines.
    # 
    # Recall that pickup locations are inaccurate due to GPS inaccuracy. Because of this, a
    # simplest nearest-point matching algorithm is not enough: this strategy will assign points
    # to streets that were not actually included in the run, only because of inaccurate GPS
    # triangulation.
    #
    # We use an iterative greedy algorithm instead. Points are initially matched to the nearest
    # centerline, but the result is thrown out if the centerline is not at least 50% covered
    # (in this context "coverage" means "distance between the first and last point assigned to
    # the centerline"). 
    #
    # Points failing this constraint are rematched to their second nearest centerline instead.
    # Points failing this constraint against are rematched to their third choice, and so on,
    # until the constraint is everywhere satisfied.
    #
    # This is a relatively simple heuristical algorithm that has some notable edge cases
    # (small centerlines, centerlines with just a single pickup) but should hopefully be robust
    # enough, given an accurate enough GPS.
    #
    # Curbs are ignored. Pickups with no curb set are matched to a curb in a separate routine.
    # This helps keep things simple.
    needs_work = True
    points_needing_work = pickups
    iter = 0
    centerlines = dict()
    while needs_work:
        for point in points_needing_work:
            point_geom = point["geometry"]
            centerline = nearest_centerline_to_point(
                point_geom, session, rank=iter, check_distance=check_distance
            )
            centerline_geom = to_shape(centerline.geometry)
            lr = centerline_geom.project(point_geom, normalized=True)  # linear reference
            c_id = centerline.id
            if c_id not in centerlines:
                centerlines[c_id] = (centerline, (lr, lr), [point])
            else:
                lr_min, lr_max = centerlines[c_id][1]
                points = centerlines[c_id][2] + [point]
                lr_min = min(lr_min, lr)
                lr_max = max(lr_max, lr)
                centerlines[c_id] = (centerline, (lr_min, lr_max), points)

        points_needing_work = []
        needs_work = False
        for c_id in list(centerlines):
            lr_min, lr_max = centerlines[c_id][1]
            points = centerlines[c_id][1]
            if lr_max - lr_min < 0.5:
                points_needing_work += centerlines[c_id][2]
                del centerlines[c_id]
                needs_work = True

        iter += 1

        # If no centerline achieves 50 percent coverage in the first pass, no centerline will pass
        # this threshold ever. To simplify the logic, we do not even bother inserting these points
        # into the database at all, we just raise a ValueError. "Every run must have coverage of
        # at least one street" is a meaningful business rule.
        at_least_one_centerline_with_coverage_geq_50_perc = len(centerlines) > 0
        if not at_least_one_centerline_with_coverage_geq_50_perc:
            raise ValueError(
                "This run was not inserted into the database because it violate the constraint "
                "that runs must cover at least one centerline."
            )

    # `centerlines` is a map with `centerline_id` keys and 
    # (centerline_obj, (min_lr, max_lr), [...pickups]) values.
    
    # Construct a key-value map with blockface identifier keys and pickup_obj values. We will pass
    # over this map in the next step to construct blockface statistics.
    blockface_pickups = dict()
    blockface_lrs = dict()
    for c_id in centerlines:
        centerline_obj = centerlines[c_id][0]
        centerline_geom = to_shape(centerline_obj.geometry)

        for pickup in centerlines[c_id][2]:
            pickup_geom = pickup['geometry']
            # TODO: curb matching logic goes here
            if pickup['curb'] is None:
                raise NotImplementedError
                # pickup['curb'] = point_side_of_centerline(pickup_geom, centerline_geom)

            linear_reference = centerline_geom.project(pickup_geom, normalized=True)
            snapped_pickup_geom = centerline_geom.interpolate(linear_reference, normalized=True)

            pickup_obj = Pickup(
                geometry=f'SRID=4326;{str(pickup_geom)}',
                snapped_geometry=f'SRID=4326;{str(snapped_pickup_geom)}',
                centerline_id=centerline_obj.id,
                firebase_id=pickup['firebase_id'],
                firebase_run_id=pickup['firebase_run_id'],
                type=pickup['type'],
                timestamp=datetime.utcfromtimestamp(pickup['timestamp']),
                linear_reference=linear_reference,
                curb=0 if pickup['curb'] == 'left' else 1
            )
            session.add(pickup_obj)

            blockface_id_tup = (centerline_obj, pickup_obj.curb)
            if blockface_id_tup not in blockface_pickups:
                blockface_pickups[blockface_id_tup] = [pickup_obj]
            else:
                blockface_pickups[blockface_id_tup] += [pickup_obj]
            if blockface_id_tup not in blockface_lrs:
                blockface_lrs[blockface_id_tup] =\
                    (pickup_obj.linear_reference, pickup_obj.linear_reference)
            else:
                min_lr, max_lr = blockface_lrs[blockface_id_tup]
                if linear_reference < min_lr:
                    min_lr = linear_reference
                elif linear_reference > max_lr:
                    max_lr = linear_reference
                blockface_lrs[blockface_id_tup] = (min_lr, max_lr)

    # From this point on, assume all curbs are set.

    # Insert blockface statistics into the database (or update existing ones).
    for blockface_id_tup in blockface_pickups:
        centerline, curb = blockface_id_tup
        pickups = blockface_pickups[blockface_id_tup]
        min_lr, max_lr = blockface_lrs[blockface_id_tup]
        coverage = max_lr - min_lr

        inferred_n_pickups = len(pickups) / coverage
        inferred_pickup_density = inferred_n_pickups / centerline.length_in_meters

        prior_information = (session
            .query(BlockfaceStatistic)
            .filter(
                BlockfaceStatistic.centerline_id == centerline.id,
                BlockfaceStatistic.curb == curb
            )
            .one_or_none()
        )

        kwargs = {'centerline_id': centerline.id, 'curb': curb}
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

def _bf_statistic_to_dict(stat):
    # WKBElement -> shapely.geometry.LineString -> dict -> JSONified dict
    # Cf. https://gis.stackexchange.com/a/233246/74038
    #     https://stackoverflow.com/a/57792988/1993206
    geom = json.dumps(
        shapely.geometry.mapping(
            to_shape(
                stat.centerline.geometry
            )
        )
    )
    return {
        "centerline_id": stat.centerline_id,
        "centerline_geometry": geom,
        "centerline_length_in_meters": stat.centerline.length_in_meters,
        "centerline_name": stat.centerline.name,
        "curb": stat.curb,
        "rubbish_per_meter": stat.rubbish_per_meter,
        "num_runs": stat.num_runs,
    }

def _centerline_to_dict(centerline):
    geom = json.dumps(
        shapely.geometry.mapping(
            to_shape(
                centerline.geometry
            )
        )
    )
    return {
        "id": centerline.id,
        "geometry": centerline.geometry,
        "centerline_length_in_meters": centerline.length_in_meters,
        "centerline_name": centerline.name,
    }

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
    raise NotImplementedError

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
    raise NotImplementedError

def coord_get(coord, include_na=False):
    """
    Returns blockface statistics for the centerline closest to the given coordinate.

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
    session = db_sessionmaker()()
    coord = shapely.geometry.Point(*coord)
    centerline = nearest_centerline_to_point(coord, session)

    if include_na == True:
        stats = (session
            .query(BlockfaceStatistic)
            .filter(BlockfaceStatistic.centerline_id == centerline.id)
            .all()
        )
        stats_out = list(map(_bf_statistic_to_dict, stats))
        return {"centerline": _centerline_to_dict(centerline), "stats": stats_out}
    else:
        raise NotImplementedError

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
    session = db_sessionmaker()()
    # Runs are not a native object in the analytics database. Instead, pickups are stored
    # with firebase_run_id and centerline_id columns set. We use this to get the
    # (centerline, curb) combinations this run touched. We then find all blockface statistics
    # for the given centerlines. Then we filter out statistics with unmatched curbs: e.g. if
    # a run went only up the left side of Polk, we'll match both left and right sides, then
    # filter out the right side.
    pickups = session.query(Pickup).filter(Pickup.firebase_run_id == run_id).all()
    if len(pickups) == 0:
        raise ValueError(f"No pickups matching a run with ID {run_id} in the database.")

    curb_map = defaultdict(list)
    centerline_ids = []
    for pickup in pickups:
        centerline_ids.append(pickup.centerline_id)
        curb_map[pickup.centerline_id].append(pickup.curb)

    stats = (
        session.query(BlockfaceStatistic)
        .filter(BlockfaceStatistic.centerline_id.in_(centerline_ids))
        .all()
    )
    stats_filtered = []
    for stat in stats:
        if stat.curb in curb_map[stat.centerline_id]:
            stats_filtered.append(stat)

    return list(map(_bf_statistic_to_dict, stats_filtered))

__all__ = [
    'write_pickups', 'radial_get', 'sector_get', 'coord_get', 'run_get',
    'nearest_centerline_to_point'
]
