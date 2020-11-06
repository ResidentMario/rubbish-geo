"""
Dumps one or more runs from the dev user database into the local user database, thereby load
testing the entire rubbish-admin flow to the PostGIS DB. Example command:

$ python dev_load_test.py rSha3Lu56sOeTwt1RCHh --reset-db
"""
# NOTE(aleksey): in order to run this script, you must run the PostGIS database, the POST_pickups
# emulator, and the Firebase Functions emulator *first*. See scripts/run_local_integration_tests
# for the relevant code.
#
# At time of writing (and on my machine) this meant:
# $ scripts/reset_local_postgis_db.sh
# $ functions-framework --source $RUBBISH_BASE_DIR/python/functions/main.py \
#     --port 8081 --target POST_pickups --debug
# $ GOOGLE_APPLICATION_CREDENTIALS=/Users/alekseybilogur/Desktop/rubbish-geo/auth/devServiceAccountKey.json \
#     firebase emulators:start

from firebase_admin import firestore, initialize_app
import os
import pathlib

from rubbish_geo_common.db_ops import reset_db
from rubbish_geo_admin.ops import update_zone

import argparse
parser = argparse.ArgumentParser(description='Run local load tests using the dev database.')
parser.add_argument('ids', metavar='N', type=str, nargs='+',
                    help='RubbishRunStory to load test with, by document ID.')
parser.add_argument('--reset-db', dest='reset_db', action='store_true',
                    help='Reset the database first before inserts.')
args = parser.parse_args()
source_story_ids = [v for v in args.ids]

if __name__ == "__main__":
    print("Initializing environment...")
    if 'RUBBISH_GEO_ENV' not in os.environ:
        os.environ['RUBBISH_GEO_ENV'] = 'local'
    elif os.environ['RUBBISH_GEO_ENV'] != 'local':
        raise NotImplementedError("Load tests are currently only implemented in local.")

    # TODO: setting this environment variable points initialization at the local emulator instead
    # of at the project-configured endpoint. But this is ugly. There must be a cleaner way...
    if 'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ:
        key_fp = pathlib.Path('.').absolute().parent / 'auth'
        key_fp = key_fp / 'devServiceAccountKey.json'
        if not key_fp.exists():
            raise ValueError(
                f"Firebase service account key file {key_fp.as_posix()!r} not available "
                "locally, you need to download that first. See "
                "https://firebase.google.com/docs/database/admin/start."
            )
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = key_fp.as_posix()
    if 'FIRESTORE_EMULATOR_HOST' in os.environ:
        del os.environ['FIRESTORE_EMULATOR_HOST']
    source_app = initialize_app(name='source')
    source_db = firestore.client(app=source_app)
    source_stories = source_db.collection('RubbishRunStory')
    source_pickups = source_db.collection('Story')
    os.environ['FIRESTORE_EMULATOR_HOST'] = 'localhost:8080'
    sink_app = initialize_app(name='sink', options={'databaseURL': 'localhost:8080'})
    sink_db = firestore.client(app=sink_app)
    sink_stories = sink_db.collection('RubbishRunStory')
    sink_pickups = sink_db.collection('Story')

    if args.reset_db:
        print("Resetting database...")
        reset_db(profile='local')
        print("Inserting San Francisco centerlines into database...")
        update_zone('San Francisco, California', 'San Francisco, California', profile='local')
        print("Done inserting San Francisco centerlines into database!")

    def dictify(doc_ref):
        return {field: doc_ref.get(field) for field in doc_ref._data}

    print("Writing runs to the user database...")
    undefined_entries = 0
    # source_stories = [source_stories.document('0Vh5P0OqtoX9YFWsL6e6').get()]
    source_stories = [source_stories.document(doc_id).get() for doc_id in source_story_ids]
    for idx, story in enumerate(source_stories):
        # Dev-only signal that this is a test case with an incomplete schema.
        if "-" in story.id:
            continue
        photoStoryIDs = story.get('photoStoryIDs')
        for photoStoryID in photoStoryIDs:
            pickup = source_pickups.document(photoStoryID)
            pickup_struct = pickup.get(
                ['curb', 'lat', 'long', 'photoStoryID', 'rubbishType', 'userTimeStamp']
            )
            # For some reason, prod has some RubbishRunStory entries linked to Story entries
            # that don't actually exist. Example case: RubbishRunStory '04yS2lIMG2ehUJrH7OO2'
            # links to non-existant Story 'KkTPjp7GIAW8uz6qWsvT'.
            if not pickup_struct.exists:
                undefined_entries += 1
                continue
            pickup_struct = dictify(pickup_struct)
            sink_pickups.document(pickup.id).set(pickup_struct)

        sink_stories.document(story.id).set(dictify(story))

    print(f"Done writing runs to the user database! Found {undefined_entries} undefined entries.")
