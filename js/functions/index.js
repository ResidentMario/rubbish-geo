const functions = require('firebase-functions');
const admin = require('firebase-admin');
const axios = require('axios');

admin.initializeApp();
const db = admin.firestore();

// NOTE(aleksey): to make the HTTP request, we must know the endpoint URL. When running in local,
// this value is set by an environment variable. When running in dev or prod, this value is set by
// a (project-wide) Firebase configuration variable (firebase functions do not support environment
// variables directly, unfortunately).
let private_api_endpoint_url = null;
if (process.env.RUBBISH_GEO_ENV === "local") {
  private_api_endpoint_url = "http://localhost:8081";
} else {
  private_api_endpoint_url = functions.config().private_api.post_pickups_url;
  if (private_api_endpoint_url  === undefined) {
    throw new Error(
      `private_api.post_pickups_url environment configuration variable is not set. Did you forget` +
      `to set it? For more information refer to the "configuration" section in the README.`
    )
  }
}


// Listens for new runs inserted into /RubbishRunStory/:runID.
exports.proxy_POST_PICKUPS = functions.firestore.document('/RubbishRunStory/{runID}')
  .onCreate((snap, context) => {
    const rubbishRunStory = snap.data();
    const firebaseID = rubbishRunStory.rubbishRunStoryModelID;
    const photoStoryPromises = [];
    for (let photoStoryIDEnum in rubbishRunStory.photoStoryIDs) {
      let photoStoryID = rubbishRunStory.photoStoryIDs[photoStoryIDEnum]
      photoStoryPromises.push(db.collection('Story').doc(photoStoryID).get());
    }
    let firebaseRunID = null;
    return Promise.all(photoStoryPromises).then((photoStories => {
      let payload = photoStories.map(photoStory => {
        const photoStoryData = photoStory.data();
        firebaseRunID = photoStoryData.photoStoryID;
        const type = photoStoryData.rubbishType;
        const timestamp = photoStoryData.userTimeStamp;
        // NOTE(aleksey): Documents that preexist the development of this service lack a curb.
        // NOTE(aleksey): Object.hasOwnProperty("curb") always returns false. The Firebase API does
        // not make this an owned property, it is inherited from the prototype chain. Hence the use
        // of the "in" operator here.
        const curb = ("curb" in photoStoryData) ?
          photoStoryData.curb :
          null;
        const geometry = `POINT(${photoStoryData.long} ${photoStoryData.lat})`
        return {
          firebase_run_id: firebaseRunID,
          firebase_id: firebaseID,
          type: type,
          timestamp: timestamp,
          curb: curb,
          geometry: geometry
        };
      });
      payload = {[firebaseID]: payload}

      const log_ids = payload[firebaseID].map(e => e.firebase_run_id);
      functions.logger.info(
        `Processing proxy_POST_pickups({${firebaseID}: ...${log_ids}}).`
      );
      // eslint-disable-next-line promise/no-nesting
      return axios.post(private_api_endpoint_url, payload).then(resp => {
        functions.logger.info(
          `proxy_POST_pickups POST of the run with firebaseRunID ${firebaseRunID} was successful.`
        );
        return;
      }).catch((err) => {
        functions.logger.error(
          `The proxy_POST_pickups authentication proxy failed to POST to the ` +
          `POST_pickups private API endpoint. Failed with ${err.name}: ${err.message}`
        );
        throw err;
      }
      );
    }));
  });
