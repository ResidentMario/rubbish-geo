"""
Python client library I/O methods.
"""
import sqlalchemy as sa
from rubbish.common.db import db_sessionmaker
from rubbish.common.orm import Pickup

try:
    session = db_sessionmaker()()
except:
    session = None

def _munge_pickups(pickups):
    pass

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
    pass
