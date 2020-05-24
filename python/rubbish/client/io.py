"""
Python client library I/O methods.
"""
import sqlalchemy as sa
from rubbish.common.db import db_sessionmaker
from rubbish.common.orm import Pickup, Centerline

sessionmaker = db_sessionmaker()

# TODO:
# Two-stage KNN seach to match centerline (https://postgis.net/workshops/postgis-intro/knn.html)
# Linear reference snapping.
# But, need to know API input signature first. E.g. is side-of-street a property?
def _munge_pickups(pickups):
    session = sessionmaker()
    for pickup in pickups:
        return (session
            .query(Centerline)
            .order_by(Centerline.geometry.distance_centroid('SRID=4326;POINT(-71.064544 42.28787)'))
            .limit(10)
            .all()
        )
    session.close()

def write_pickups(pickups):
    """
    Writes pickups to the database. Pickups is expected to be a list of entries in the format:

    ```
    {"firebase_id": <int>
     "type": <int, see key in docs>
     "timestamp": <int; UNIX timestamp>
     "geometry": <str; POINT in WKT format>}
    ```

    All other keys included in the dict will be silently ignored.
    """
    return _munge_pickups(pickups)
    pass
