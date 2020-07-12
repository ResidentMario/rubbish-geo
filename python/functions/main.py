"""
Cloud functions defining the rubbish-geo private API.
"""
import requests
import shapely

from rubbish.client import write_pickups, radial_get, sector_get, coord_get, run_get
from rubbish.common.db_ops import get_db

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
    print(include_na)

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
