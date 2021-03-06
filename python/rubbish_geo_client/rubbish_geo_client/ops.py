"""
Python client library I/O methods.
"""
import warnings
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import json

import shapely
from shapely.geometry import Point, LineString
import geoalchemy2
from geoalchemy2.shape import to_shape
from scipy.stats import shapiro

from rubbish_geo_common.db_ops import db_sessionmaker
from rubbish_geo_common.orm import Pickup, Centerline, BlockfaceStatistic, Sector
from rubbish_geo_common.consts import RUBBISH_TYPES

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
    return 'left' if d <= 0 else 'right'

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

def write_pickups(pickups, profile, check_distance=True, logger=None):
    """
    Writes pickups to the database. This method hosts the primary logic for the overall service's
    POST path.

    Parameters
    ----------
    pickups: list
        A `list` of pickups. Each entry in the list is expected to be a `dict` in the following
        format:

        ```
        {"firebase_id": <str>,
        "firebase_run_id": <str>,
        "type": <str, from RUBBISH_TYPES>,
        "timestamp": <int; UTC UNIX timestamp>,
        "curb": <{left, right, middle, None}>,
        "geometry": <str; POINT in WKT format>}
        ```

        The list is to contain *all* pickups associated with an individual run.
    profile: str
        The name of the database write_pickups will write to. This named database must either be
        present on disk (written to `$HOME/.rubbish/config`, either manually or using the `set-db`
        admin CLI command), or its connection information must be set using the 
        `RUBBISH_POSTGIS_CONNSTR` environment variable.
    check_distance: bool, default `True`
        If set to `False`, the points will be matched to the nearest centerline in the database,
        regardless of distance. If `True`, points that are too far from any centerlines in the
        database (according to a heuristic threshold) will be discarded. This value should always
        be set to `True` in `prod`, but may be set to `False` for local testing purposes.
    logger: LogHandler object or None
        If set, this method will write logs using this log handler. See the definition of
        `LogHandler` in `python/functions/main.py`. If not set, logging is omitted.
    """
    # TODO: add debug-level logging. The logger is already being passed down by the function.
    # if logger is not None:
    #     logger.log_struct({"level": "debug", "message": "Got to write_pickups."})

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
        for int_attr in ["timestamp"]:
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
        if curb not in [None, "left", "right", "middle"]:
            raise ValueError(
                f"Found pickup with invalid curb value {curb} "
                f"(must be one of 'left', 'right', 'middle', None)."
            )
        if pickup["type"] not in RUBBISH_TYPES:
            raise ValueError(
                f"Found pickup with type {pickup['type']!r} not in valid types {RUBBISH_TYPES!r}."
            )

    session = db_sessionmaker(profile)()

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
    
    # This code block handles inference of side-of-street for point distributions with
    # incomplete curb data.
    #
    # If every point assigned to a centerline has a curb set, we assume the user is following
    # procedure and faithfully indicating what side of the street the pickup occurred on, and
    # we do not modify any of the values.
    #
    # If any point fails this condition, we assume the user forgot or neglected to set this
    # flag for at least some of the pickups. In this case we use a statistical test.    
    # 
    # Determine whether the distribution is unimodal (pickups on one side of the street) or
    # bimodal (pickups on both sides). We expect a normal distribution on the centerline
    # (ignoring street width displacement!) with 2σ=~±8 meters (estimated GPS inacurracy from
    # https://bit.ly/3elXK0V). If support of the alternative hypothesis is present with p>0.05
    # we assume both sides were run and assign each side points.
    #
    # The actual normality test statistic used is the Shapiro-Wilk Test. For more information:
    # https://machinelearningmastery.com/a-gentle-introduction-to-normality-tests-in-python/.
    #
    # This worked relatively well for Polk Street, but Polk Street is very wide and we had a
    # *lot* of data to work with. With small data volumes, narrow streets, and relatively
    # heterogenous side-of-street rubbish distributions, this gets very hand-wavey. For this
    # reason it's *super important* to encourage the user to set side-of-street themselves.
    centerlines_needing_curb_inference = set()
    for c_id in centerlines:
        for pickup in centerlines[c_id][2]:
            if pickup['curb'] is None:
                centerlines_needing_curb_inference.add(c_id)
                break
    for c_id in centerlines_needing_curb_inference:
        dists = []
        sides = []
        centerline_geom = to_shape(centerlines[c_id][0].geometry)
        pickups = centerlines[c_id][2]

        # Shapiro requires n>=3 points, so if there are only 1 or 2, just set it to the first
        # value that appears; there's just not much we can do in this case. ¯\_(ツ)_/¯
        if len(pickups) < 3:
            if pickups[0]['curb'] is not None:
                curb = pickups[0]['curb']
            elif len(pickups) == 2 and pickups[1]['curb'] is not None:
                curb = pickups[1]['curb']
            for pickup in pickups:
                pickup['curb'] = curb
            continue

        for pickup in pickups:
            pickup_geom = pickup['geometry']
            dists.append(pickup_geom.distance(centerline_geom))
            sides.append(point_side_of_centerline(pickup_geom, centerline_geom))
        _, p = shapiro(dists)
        if p > 0.05:
            # Gaussian unimodal case. Evidence that points are on one side of the street.
            # Pick the majority class.
            c = Counter(sides)
            curb = 'left' if c[0] > c[1] else 'right'
            for pickup in pickups:
                pickup['curb'] = curb
        else:
            # Non-Gaussian (bimodal) case. Evidence that points are on both sides of the street.
            # Use the user-set value if it's present, otherwise pick the closest match.
            for i, pickup in enumerate(pickups):
                if pickup['curb'] is None:
                    pickup['curb'] = sides[i]

    # From this point on, assume all curbs are set.

    # Construct a key-value map with blockface identifier keys and pickup_obj values. We will pass
    # over this map in the next step to construct blockface statistics.
    blockface_pickups = dict()
    blockface_lrs = dict()
    for c_id in centerlines:
        centerline_obj = centerlines[c_id][0]
        centerline_geom = to_shape(centerline_obj.geometry)
        pickups = centerlines[c_id][2]

        for pickup in pickups:
            pickup_geom = pickup['geometry']

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
                curb=pickup['curb']
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

def wkb_to_geojson(wkb):
    """
    Helper method used for converting data in the ORM WKB format into data in the output GeoJSON
    format.

    Implements the following transform: WKBElement -> shapely.geometry.LineString -> dict ->
    JSONified dict.

    See further https://gis.stackexchange.com/a/233246/74038 and
    https://stackoverflow.com/a/57792988/1993206.
    """
    return json.dumps(shapely.geometry.mapping(to_shape(wkb)))

def blockface_statistic_obj_to_dict(stat):
    """
    Transforms a `rubbish.common.orm.BlockfaceStatistic` object into a `dict` and returns it.

    This is mostly a direct translation of the ORM object. The major exception is that the geometry
    returned by `geoalchemy2` is in WKB, but we need it in GeoJSON. This requires the following
    transform: WKBElement -> shapely.geometry.LineString -> dict -> JSONified dict.
    
    See further https://gis.stackexchange.com/a/233246/74038 and
    https://stackoverflow.com/a/57792988/1993206.
    """
    geom = wkb_to_geojson(stat.centerline.geometry)
    return {
        "centerline_id": stat.centerline_id,
        "centerline_geometry": geom,
        "centerline_length_in_meters": stat.centerline.length_in_meters,
        "centerline_name": stat.centerline.name,
        "curb": stat.curb,
        "rubbish_per_meter": stat.rubbish_per_meter,
        "num_runs": stat.num_runs,
    }

def blockface_statistic_objs_to_dicts(stats):
    """
    Transforms a lit of `rubbish.common.orm.BlockfaceStatistic` objects into a `list` of `dict`
    objects and returns it. Uses `blockface_statistic_obj_to_dict`.
    """
    return [blockface_statistic_obj_to_dict(stat) for stat in stats]

def centerline_obj_to_dict(centerline):
    geom = wkb_to_geojson(centerline.geometry)
    return {
        "id": centerline.id,
        "geometry": geom,
        "centerline_length_in_meters": centerline.length_in_meters,
        "centerline_name": centerline.name,
    }

def radial_get(coord, distance, profile, include_na=False, offset=0):
    """
    Returns all blockface statistics for blockfaces containing at least one point at most
    ``distance`` away from ``coord``.

    Parameters
    ----------
    coord : (x, y) coordinate tuple
        Centerpoint for the scan.
    distance : int
        Distance (in meters) from centerpoint to scan for.
    profile: str
        The database to connect to (e.g. "dev") as configured in ~/.rubbish/config.
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
    session = db_sessionmaker(profile)()
    coord = f'SRID=4326;POINT({coord[0]} {coord[1]})'
    centerlines = (session
        .query(Centerline)
        .filter(Centerline.geometry.ST_Distance(coord) < distance)
        .all()
    )
    centerline_ids = set(centerline.id for centerline in centerlines)
    statistics = (session
        .query(BlockfaceStatistic)
        .filter(BlockfaceStatistic.centerline_id.in_(centerline_ids))
        .all()
    )
    response_map = dict()
    for statistic in statistics:
        if statistic.centerline_id not in response_map:
            centerline_dict = centerline_obj_to_dict(statistic.centerline)
            response_map[statistic.centerline_id] = {
                'centerline': centerline_dict,
                'statistics': {'left': None, 'middle': None, 'right': None}
            }
        statistic_dict = blockface_statistic_obj_to_dict(statistic)
        response_map[statistic.centerline_id]['statistics'][statistic.curb] = statistic_dict
    if include_na:
        for centerline in centerlines:
            if centerline.id not in response_map:
                response_map[centerline.id] = {
                    'centerline': centerline_obj_to_dict(centerline),
                    'statistics': {'left': None, 'middle': None, 'right': None}
                }
    if len(response_map) == 0:
        return []
    return [response_map[centerline_id] for centerline_id in response_map]

def sector_get(sector_name, profile, include_na=False, offset=0):
    """
    Returns all blockface statistics for blockfaces contained in a sector. Only blockfaces located
    completely within the sector count. Blockfaces touching sector edges are ok, blockfaces
    containing some points outside of the sector are not.

    Parameters
    ----------
    sector_name: str
        Unique sector name.
    profile: str
        The database to connect to (e.g. "dev") as configured in ~/.rubbish/config.
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
    session = db_sessionmaker(profile)()
    sector = (session
        .query(Sector)
        .filter(Sector.name == sector_name)
        .one_or_none()
    )
    if sector is None:
        raise ValueError(f"No {sector_name!r} sector in the database.")
    centerlines = (session
        .query(Centerline)
        .filter(Centerline.geometry.ST_Intersects(sector.geometry))
        .all()
    )
    centerline_ids = set(centerline.id for centerline in centerlines)
    statistics = (session
        .query(BlockfaceStatistic)
        .filter(BlockfaceStatistic.centerline_id.in_(centerline_ids))
        .all()
    )

    response_map = dict()
    for statistic in statistics:
        if statistic.centerline_id not in response_map:
            centerline_dict = centerline_obj_to_dict(statistic.centerline)
            response_map[statistic.centerline_id] = {
                'centerline': centerline_dict,
                'statistics': {'left': None, 'middle': None, 'right': None}
            }
        statistic_dict = blockface_statistic_obj_to_dict(statistic)
        response_map[statistic.centerline_id]['statistics'][statistic.curb] = statistic_dict
    if include_na:
        for centerline in centerlines:
            if centerline.id not in response_map:
                response_map[centerline.id] = {
                    'centerline': centerline_obj_to_dict(centerline),
                    'statistics': {'left': None, 'middle': None, 'right': None}
                }
    return [response_map[centerline_id] for centerline_id in response_map]

def coord_get(coord, profile, include_na=False):
    """
    Returns blockface statistics for the centerline closest to the given coordinate.

    Parameters
    ----------
    coord: (x, y) coordinate tuple
        Origin point for the snapped selection.
    profile: str
        The database to connect to (e.g. "dev") as configured in ~/.rubbish/config.
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
    session = db_sessionmaker(profile)()
    coord = shapely.geometry.Point(*coord)

    def get_stats_objs(session, centerline_id):
        return (session
            .query(BlockfaceStatistic)
            .filter(BlockfaceStatistic.centerline_id == centerline_id)
            .all()
        )

    centerline = None
    if include_na == True:
        centerline = nearest_centerline_to_point(coord, session)
        stats_objs = get_stats_objs(session, centerline.id)
    else:
        stats_objs = []
        rank = 0
        while len(stats_objs) == 0:
            centerline = nearest_centerline_to_point(coord, session, rank=rank)
            stats_objs = get_stats_objs(session, centerline.id)
            rank += 1
            if rank >= 10:
                raise ValueError("Could not find non-null blockface statistics nearby.")

    stats_dicts = blockface_statistic_objs_to_dicts(stats_objs)
    statistics = {stat_dict['curb']: stat_dict for stat_dict in stats_dicts}
    if 'left' not in statistics:
        statistics['left'] = None
    if 'right' not in statistics:
        statistics['right'] = None
    if 'middle' not in statistics:
        statistics['middle'] = None
    return {"centerline": centerline_obj_to_dict(centerline), "statistics": statistics}

def run_get(run_id, profile):
    """
    Returns blockface statistics and run-specific data for a specific run by id.

    Parameters
    ----------
    run_id : str
        The run id. Note: this is stored as ``firebase_id`` in the ``Pickups`` table.
    profile: str
        The database to connect to (e.g. "dev") as configured in ~/.rubbish/config.

    Returns
    -------
    ``dict``
        Query result.
    """
    session = db_sessionmaker(profile)()
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
    # TODO: shouldn't this be a set?
    centerline_ids = []
    for pickup in pickups:
        centerline_ids.append(pickup.centerline_id)
        curb_map[pickup.centerline_id].append(pickup.curb)

    statistics = (
        session.query(BlockfaceStatistic)
        .filter(BlockfaceStatistic.centerline_id.in_(centerline_ids))
        .all()
    )
    statistics_filtered = []
    for statistic in statistics:
        if statistic.curb in curb_map[statistic.centerline_id]:
            statistics_filtered.append(statistic)

    response_map = dict()
    for statistic in statistics_filtered:
        if statistic.centerline_id not in response_map:
            centerline_dict = centerline_obj_to_dict(statistic.centerline)
            response_map[statistic.centerline_id] = {
                'centerline': centerline_dict,
                'statistics': {'left': None, 'middle': None, 'right': None}
            }
        statistic_dict = blockface_statistic_obj_to_dict(statistic)
        response_map[statistic.centerline_id]['statistics'][statistic.curb] = statistic_dict
    return [response_map[centerline_id] for centerline_id in response_map]

__all__ = [
    'write_pickups', 'radial_get', 'sector_get', 'coord_get', 'run_get',
    'nearest_centerline_to_point'
]
