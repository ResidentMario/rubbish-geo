const functions = require('firebase-functions');
const admin = require('firebase-admin');
const axios = require('axios');

admin.initializeApp();
const db = admin.firestore();

// NOTE(aleksey): to make the HTTP request, we must know the endpoint URL. When running in local,
// this value is set by an environment variable. When running in dev or prod, this value is set by
// a (project-wide) Firebase configuration variable (firebase functions do not support environment
// variables directly, unfortunately).
let functional_api_endpoint_url = null;
if (process.env.RUBBISH_GEO_ENV === "local") {
  functional_api_endpoint_url = "http://localhost:8081";
} else {  // [dev, prod]
  functional_api_endpoint_url = functions.config().functional_api.post_pickups_url;
  if (functional_api_endpoint_url  === undefined) {
    throw new Error(
      `functional_api.post_pickups_url environment configuration variable is not set. Did you forget` +
      `to set it? For more information refer to the "configuration" section in the README.`
    )
  }
}


// Listens for new runs inserted into /RubbishRunStory/:runID.
exports.proxy_POST_PICKUPS = functions.firestore.document('/RubbishRunStory/{runID}')
  .onCreate(async (snap, _) => {
    const rubbishRunStory = snap.data();
    const firebaseID = rubbishRunStory.rubbishRunStoryModelID;
    const photoStoryPromises = [];
    for (let photoStoryIDEnum in rubbishRunStory.photoStoryIDs) {
      let photoStoryID = rubbishRunStory.photoStoryIDs[photoStoryIDEnum]
      photoStoryPromises.push(db.collection('Story').doc(photoStoryID).get());
    }
    let firebaseRunID = null;
    let photoStories = await Promise.all(photoStoryPromises);

    let token = null;
    if (process.env.RUBBISH_GEO_ENV !== "local") {
      // https://cloud.google.com/functions/docs/securing/authenticating
      const metadataServerURL =
      'http://metadata/computeMetadata/v1/instance/service-accounts/default/identity?audience=';
      const tokenUrl = metadataServerURL + functional_api_endpoint_url;
      const tokenResponse = await axios.get(tokenUrl, {headers: {'Metadata-Flavor': 'Google'}});
      token = tokenResponse.data;
    }

    let payload = photoStories.map(photoStory => {
      const photoStoryData = photoStory.data();
      firebaseRunID = photoStoryData.photoStoryID;
      const type = photoStoryData.rubbishType;
      const timestamp = photoStoryData.userTimeStamp;
      const curb = ("curb" in photoStoryData) ? photoStoryData.curb : null;
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
      `Processing proxy_POST_pickups({${firebaseID}: [...${log_ids}]}).`
    );

    return axios.post(
      functional_api_endpoint_url, payload, {headers: {Authorization: `bearer ${token}`}}
    ).then(_ => {
      functions.logger.info(
        `proxy_POST_pickups POST of the run with firebaseRunID ${firebaseRunID} was successful.`
      );
      return;
    }).catch((err) => {
      functions.logger.error(
        `The proxy_POST_pickups authentication proxy failed to POST to the ` +
        `POST_pickups functional API endpoint. Failed with ${err.name}: ${err.message}`
      );
      throw err;
    });
  });
