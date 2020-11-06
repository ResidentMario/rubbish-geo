from firebase_admin import firestore, initialize_app
import os
import pathlib

from rubbish_geo_common.db_ops import reset_db
from rubbish_geo_admin.ops import update_zone

if __name__ == "__main__":
    print("Initializing environment...")
    if 'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ:
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] =\
            pathlib.Path('.').absolute().parent / 'js' / 'serviceAccountKey.json'
    if 'RUBBISH_GEO_ENV' not in os.environ:
        os.environ['RUBBISH_GEO_ENV'] = 'local'

    # TODO: setting this environment variable points initialization at the local emulator instead
    # of at the project-configured endpoint. But this is ugly. There must be a cleaner way...
    try:
        del os.environ['FIRESTORE_EMULATOR_HOST']
    except KeyError:
        pass
    source_app = initialize_app(name='source')
    source_db = firestore.client(app=source_app)
    os.environ['FIRESTORE_EMULATOR_HOST'] = 'localhost:8080'
    sink_app = initialize_app(name='sink', options={'databaseURL': 'localhost:8080'})
    sink_db = firestore.client(app=sink_app)

    source_stories = source_db.collection('RubbishRunStory').stream()
    source_pickups = source_db.collection('Story')
    sink_stories = sink_db.collection('RubbishRunStory')
    sink_pickups = sink_db.collection('Story')

    print("Resetting database...")
    reset_db(profile='local')
    print("Inserting San Francisco centerlines into database...")
    update_zone('San Francisco, California', 'San Francisco, California', profile='local')
    print("Done inserting San Francisco centerlines into database!")

    def dictify(doc_ref):
        return {**{field: doc_ref.get(field) for field in doc_ref._data}, 'id': doc_ref.id}

    print("Writing runs to the user database...")
    for idx, story in enumerate(source_stories):
        story_to_write = dictify(story)
        pickups_to_write = []

        # this happens to be a signal that this is a test case, which doesn't follow
        # the full schema, so we should skip it
        if "-" in story.id:
            continue
        photoStoryIDs = story.get('photoStoryIDs')
        story_id = story.id
        for photoStoryID in photoStoryIDs:
            pickup = source_pickups.document(photoStoryID)
            pickup = pickup.get(
                ['curb', 'lat', 'long', 'photoStoryID', 'rubbishType', 'userTimeStamp']
            )
            pickups_to_write.append({**dictify(pickup)})

        for pickup_to_write in pickups_to_write:
            pickup_id = pickup_to_write['id']
            del pickup_to_write['id']
            sink_pickups.document(pickup_id).set(pickup_to_write)

        del story_to_write['id']
        sink_stories.document(story_id).set(story_to_write)
        break

    print("Done writing runs to the user database!")
