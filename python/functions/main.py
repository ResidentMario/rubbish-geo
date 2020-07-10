from rubbish.client import write_pickups
from rubbish.common.db_ops import get_db

def write_pickups(request):
    try:
        get_db()
    except ValueError:
        raise ValueError(
            "Could not connect to the database. Did you forget to set RUBBISH_POSTGIS_CONNSTR?"
        )

    # TODO: debate this input format on the Friday call.
    # {"firebase_id": <int>,
    #  "firebase_run_id": <int>,
    #  "type": <int, see key in docs>,
    #  "timestamp": <int; UTC UNIX timestamp>,
    #  "curb": <{left, right, None}; user statement of side of the street>,
    #  "geometry": <str; POINT in WKT format>}
    return request.get_json()
