"""
Cloud functions defining the rubbish-geo private API.
"""
from flask import abort
from firebase_admin.auth import verify_id_token
from firebase_admin import initialize_app
import shapely
import os

from rubbish_geo_client import write_pickups, radial_get, sector_get, coord_get, run_get
from rubbish_geo_common.db_ops import get_db

# NOTE(aleksey): calling verify_id_token requires initializing the app. You do not
# need to be authenticated to the specific project that minted the token in order to be able to
# verify its authenticity, but such requests are rate-limited and will raise a warning stating as
# much. This warning can safely be ignored when running local tests because cloud functions are a
# different environment with all the proper bits already set up.
app = initialize_app()

# NOTE(aleksey): Cloud Functions do not allow direct access to Cloud SQL even though they're in
# the same VPC :(. The only documented code path for accessing Cloud SQL from inside of a Cloud
# Function is one that uses UNIX sockets. This requires that the folder that will be used to
# establish the connection exists (otherwise Linux will error out). "/cloudsql" is the
# (hard-coded) folder path we'll use. See the following page in the GCP documentation:
# https://cloud.google.com/sql/docs/postgres/connect-functions.
if 'RUBBISH_GEO_ENV' in os.environ and os.environ['RUBBISH_GEO_ENV'] != 'local':
    try:
        os.mkdir("/cloudsql")
    # cloud functions recycle disks, so a previous deploy may have created the path already
    except FileExistsError:
        pass

def POST_pickups(request):
    """
    This function services a POST request writing one or more Rubbish runs into the database.

    Expects a JSON payload with the following shape:
    
    ```
    {
        "firebase_run_id": [
            {
                "firebase_run_id": <int>,
                "firebase_id": <int>,
                "type": <str; from {'tobacco', 'paper', 'plastic', 'other', 'food', 'glass'}>,
                "timestamp": <int; UTC UNIX timestamp>,
                "curb": <{'left', 'right', None}; user statement of side of the street>,
                "geometry": <str; POINT in WKT format>
            }
        ]
    }
    ```
    """
    try:
        get_db()
    except ValueError:
        raise ValueError(
            "Could not connect to the database. Did you forget to set RUBBISH_POSTGIS_CONNSTR?"
        )

    request = request.get_json()
    for firebase_run_id in request:
        run = request[firebase_run_id]
        for pickup in run:
            pickup['geometry'] = shapely.wkt.loads(pickup['geometry'])
        write_pickups(run)
    return {"status": 200}

def GET_radial(request):
    """
    This function services a GET request for blockface statistics within a certain radius.

    Expects the following URL parameters:
    * x: coord x
    * y: coord y
    * distance: float, how far away to look in meters
    * include_na (optional): `true` or `false`, whether or not to include statistics with no data
    * offset (optional): pagination offset
    """
    args = request.args
    if 'x' not in args or 'y' not in args or 'distance' not in args:
        raise ValueError("This request is missing required 'coord' or 'distance' URL parameters.")
    x = float(args['x'])
    y = float(args['y'])
    distance = int(args['distance'])
    include_na = args['include_na'].title() == 'True' if 'include_na' in args else False
    offset = int(args['offset']) if 'offset' in args else 0
    return {"blockfaces": radial_get((x, y), distance, include_na=include_na, offset=offset)}

def GET_sector(request):
    """
    This function services a GET request for blockface statistics within a sector.

    Expects the following URL parameters:
    * sector_name: name of the sector
    * include_na (optional): `true` or `false`, whether or not to include statistics with no data
    * offset (optional): pagination offset
    """
    args = request.args
    if 'sector_name' not in args:
        raise ValueError("This request is missing required 'sector_name' URL parameter.")
    sector_name = args['sector_name']
    include_na = args['include_na'].title() == 'True' if 'include_na' in args else False
    offset = int(args['offset']) if 'offset' in args else 0

    return {"blockfaces": sector_get(sector_name, include_na=include_na, offset=offset)}

def GET_coord(request):
    """
    This function services a GET request for the blockface statistic closest to the input
    coordinate.

    Expects the following URL parameters:
    * x: coord x
    * y: coord y
    * include_na (optional): `true` or `false`, whether or not to include statistics with no data
    """
    args = request.args
    if 'x' not in args or 'y' not in args:
        raise ValueError("This request is missing the required 'x' or 'y' URL parameter.")
    x = float(args['x'])
    y = float(args['y'])
    include_na = args['include_na'].title() == 'True' if 'include_na' in args else False

    return {"blockfaces": coord_get((x, y), include_na=include_na)}

def GET_run(request):
    """
    This function services a GET request for a run by ID.

    Expects the following URL parameters:
    * run_id
    """
    args = request.args
    if 'run_id' not in args:
        raise ValueError("This request is missing the required 'run_id' URL parameter.")
    run_id = args['run_id']

    return {"blockfaces": run_get(run_id)}

def GET(request):
    """
    This function is the user-facing part of the function. It passes its input to the correct GET
    method. Requests are multiplexed behind this method to reduce cold start time.
    """
    args = request.args
    if 'request_type' not in args:
        # raise ValueError("This request is missing the required 'request_type' URL parameter.")
        abort(403)

    authorization = request.headers.get('Authorization')
    if authorization is None:
        abort(403)
    try:
        id_token = authorization.split("Bearer ")[1]
    except (ValueError, IndexError):
        abort(403)
    try:
        verify_id_token(id_token, app=app, check_revoked=False)
    except:
        abort(403)

    t = args['request_type']
    if t == 'run':
        return GET_run(request)
    elif t == 'sector':
        return GET_sector(request)
    elif t == 'coord':
        return GET_coord(request)
    elif t == 'radial':
        return GET_radial(request)
    else:
        # raise ValueError(
        #     f"Received request with invalid 'request_type' value {t!r}. 'request_type' must be "
        #     f"one of 'run', 'sector', 'coord', or 'radial'."
        # )
        abort(400)
