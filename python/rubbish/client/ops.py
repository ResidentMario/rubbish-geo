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
    # TODO: it may be possible to significantly speed this process up by precomputing areas using
    # morphological tesselation.
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
        # TODO: deal with pickups near the edges of centerlines that stray into matching with
        # other streets that are not actually part of the run.
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

    # TODO: curb correction logic

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
            # TODO: only run this check for the first and last street in the run
            linear_ref_coverage = linear_ref_max - linear_ref_min
            if linear_ref_coverage < 0.5:
                continue

            n_matching_pickups = len(matching_pickups)
            inferred_n_pickups = n_matching_pickups / linear_ref_coverage
            # TODO: store and use geographic distance instead of Cartesian distance.
            # TODO: also scale against curb width, somehow?
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
    # TODO: expand curb definition to include pedestrian islands.
    return _munge_pickups(pickups)
