"""
Cloud functions defining the rubbish-geo functional API.
"""
from flask import abort
from firebase_admin.auth import verify_id_token
from firebase_admin import initialize_app
import shapely
import os

from rubbish_geo_client import write_pickups, radial_get, sector_get, coord_get, run_get
from rubbish_geo_common.db_ops import get_db
from rubbish_geo_common.consts import RUBBISH_TYPES

import sys
import traceback
from google.cloud.logging.client import Client
import logging
import json
import inspect

if 'RUBBISH_GEO_ENV' not in os.environ:
    raise OSError("RUBBISH_GEO_ENV environment variable not set, exiting.")
RUBBISH_GEO_ENV = os.environ.get('RUBBISH_GEO_ENV')
if RUBBISH_GEO_ENV not in ['local', 'dev', 'prod']:
    raise ValueError(
        'RUBBISH_GEO_ENV environment variable not understood. Must be one of {local, dev, prod}.'
    )

class LogHandler:
    def __init__(self):
        if RUBBISH_GEO_ENV == "local":
            logging.basicConfig(level=logging.INFO)
        else:  # [dev, prod]
            self.client = Client()
            self.logger = self.client.logger("functional_api")
    
    def log_struct(self, struct):
        level = struct.get("level", "info")
        if level == "error":
            struct['traceback'] = traceback.format_exc()
        
        # SO#57712700
        struct["caller"] = inspect.currentframe().f_back.f_code.co_name

        if RUBBISH_GEO_ENV == "local":
            getattr(logging, level)(json.dumps(struct))
        else:  # [dev, prod]
            self.logger.log_struct(struct)

logger = LogHandler()
sys.tracebacklimit = 5

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
if RUBBISH_GEO_ENV != 'local':
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
                "curb": <{'left', 'right', 'middle', None}; side of the street>,
                "geometry": <str; POINT in WKT format>
            }
        ]
    }
    ```
    """
    try:
        get_db(RUBBISH_GEO_ENV)
    except:
        logger.log_struct({
            "level": "error",
            "message": "Could not connect to the database."
        })
        abort(400)

    request = request.get_json()
    logger.log_struct({
        "level": "info",
        "message": f"Processing POST_pickups({list(request.keys())})."
    })

    for firebase_run_id in request:
        run = request[firebase_run_id]
        for pickup in run:
            pickup['geometry'] = shapely.wkt.loads(pickup['geometry'])
            # TODO: support custom pickup types.
            pickup_type = pickup['type']
            pickup_id = pickup['firebase_id']
            if pickup_type not in RUBBISH_TYPES:
                logger.log_struct({
                    "level": "warning",
                    "message": (
                        f"Pickup {pickup_id!r} has custom pickup type {pickup_type!r}. "
                        f"rubbish-geo does not support custom types yet. Replacing with 'other'."
                    )
                })
                pickup['type'] = 'other'
        try:
            write_pickups(run, RUBBISH_GEO_ENV, logger=logger)
        except:
            logger.log_struct({
                "level": "error",
                "message": "Run write did not succeed."
            })
            abort(400)
    
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
        logger.log_struct({
            "level": "warning",
            "message": "Request is missing required URL parameters.",
        })
        abort(400)

    x = float(args['x'])
    y = float(args['y'])
    distance = int(args['distance'])
    include_na = args['include_na'].title() == 'True' if 'include_na' in args else False
    offset = int(args['offset']) if 'offset' in args else 0

    logger.log_struct({
        "level": "info",
        "message": f"Processing GET_radial(x={x}, y={y}, distance={distance}, "
                   f"include_na={include_na}, offset={offset})."
    })

    try:
        response = radial_get(
            (x, y), distance, RUBBISH_GEO_ENV, include_na=include_na, offset=offset
        )
    except:
        logger.log_struct({
            "level": "error",
            "message": "radial_get call failed."
        })
        abort(400)

    return {"status": 200, "blockfaces": response}

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
        logger.log_struct({
            "level": "warning",
            "message": "Request is missing required URL parameters.",
        })
        abort(400)
    sector_name = args['sector_name']
    include_na = args['include_na'].title() == 'True' if 'include_na' in args else False
    offset = int(args['offset']) if 'offset' in args else 0
    logger.log_struct({
        "level": "info",
        "message": f"Processing GET_sector(sector_name={sector_name}, "
                   f"include_na={include_na}, offset={offset})."
    })

    try:
        response = sector_get(sector_name, RUBBISH_GEO_ENV, include_na=include_na, offset=offset)
    except:
        logger.log_struct({
            "level": "error",
            "message": "sector_get call failed."
        })
        abort(400)

    return {"blockfaces": response}

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
        logger.log_struct({
            "level": "warning",
            "message": "Request is missing required URL parameters.",
        })
        abort(400)
    x = float(args['x'])
    y = float(args['y'])
    include_na = args['include_na'].title() == 'True' if 'include_na' in args else False

    try:
        response = coord_get((x, y), RUBBISH_GEO_ENV, include_na=include_na)
    except:
        logger.log_struct({
            "level": "error",
            "message": "coord_get call failed."
        })
        abort(400)
    logger.log_struct({
        "level": "info",
        "message": f"Processing GET_coord(x={x}, y={y}, include_na={include_na})."
    })

    return {"status": 200, "blockfaces": response}

def GET_run(request):
    """
    This function services a GET request for a run by ID.

    Expects the following URL parameters:
    * run_id
    """
    args = request.args
    if 'run_id' not in args:
        logger.log_struct({
            "level": "warning",
            "message": "Request is missing required URL parameters.",
        })
        abort(400)
    run_id = args['run_id']

    logger.log_struct({
        "level": "info",
        "message": f"Processing GET_run(run_id={run_id})."
    })
    try:
        response = run_get(run_id, RUBBISH_GEO_ENV)        
    except:
        logger.log_struct({
            "level": "error",
            "message": "run_get call failed."
        })
        abort(400)

    return {"blockfaces": response}

def GET(request):
    """
    This function is the user-facing part of the function. It passes its input to the correct GET
    method. Requests are multiplexed behind this method to reduce cold start time.
    """
    args = request.args
    if 'request_type' not in args:
        logger.log_struct({
            "level": "warning",
            "message": "Request is missing the required 'request_type' URL param, returning 403."
        })
        abort(403)

    authorization = request.headers.get('Authorization')
    if authorization is None:
        logger.log_struct({
            "level": "warning",
            "message": "Request has no authorization header, returning 403."
        })
        abort(403)
    try:
        id_token = authorization.split("Bearer ")[1]
    except (ValueError, IndexError):
        logger.log_struct({
            "level": "warning",
            "message": "Request authorization header is invalid, returning 403."
        })
        abort(403)
    try:
        verify_id_token(id_token, app=app, check_revoked=False)
    except:
        logger.log_struct({
            "level": "warning",
            "message": "Request authorization header failed validation, returning 403."
        })
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
        logger.log_struct({
            "level": "warning",
            "message": "Request has invalid 'request_type', returning 400."
        })
        abort(400)
