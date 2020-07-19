const functions = require('firebase-functions');
const admin = require('firebase-admin');
const axios = require('axios');

admin.initializeApp();
const db = admin.firestore();

// NOTE(aleksey): cloud functions do not support environment variables, using project-wide
// configuration variables instead. For testing purposes, we set NODE_ENV to local in local tests
// (which use the emulator) and interpret the lack a NODE_ENV environment variable as prod
// (which uses the live cloud function).
let private_api_endpoint_url = null;
if (process.env.NODE_ENV === "local") {
  private_api_endpoint_url = process.env.CLOUD_FUNCTIONS_EMULATOR_HOST;
  if (private_api_endpoint_url === undefined) {
    throw new Error(`
      CLOUD_FUNCTIONS_EMULATOR_HOST environment variable is not set. This value must point to the
      private API HTTPS endpoint when running locally.
    `)
  }
} else {
  private_api_endpoint_url = functions.config().private_api.post_pickups_url;
  if (private_api_endpoint_url  === undefined) {
    throw new Error(`
      private_api.post_pickups_url environment configuration variable is not set. Did you forget
      to set it? For more information refer to the "configuration" section in the README.
    `)
  }
}


// Listens for new runs inserted into /RubbishRunStory/:runID.
// TODO: rename the cloud function and client package fields to match Firestore names exactly.
// This would make the code more readable for those most familiar with the Firestore values
// (mainly Emin).
exports.proxy_POST_PICKUPS = functions.firestore.document('/RubbishRunStory/{runID}')
  .onCreate((snap, context) => {
    const rubbishRunStory = snap.data();
    const firebaseID = rubbishRunStory.rubbishRunStoryModelID;
    const photoStoryPromises = [];
    for (let photoStoryIDEnum in rubbishRunStory.photoStoryIDs) {
      let photoStoryID = rubbishRunStory.photoStoryIDs[photoStoryIDEnum]
      console.log(photoStoryIDEnum);
      console.log(photoStoryID);
      photoStoryPromises.push(db.collection('Story').doc(photoStoryID).get());
    }
    return Promise.all(photoStoryPromises).then((photoStories => {
      let payload = photoStories.map(photoStory => {
        const photoStoryData = photoStory.data();
        const firebaseRunID = photoStoryData.photoStoryID;
        const type = photoStoryData.rubbishType;
        const timestamp = photoStoryData.userTimeStamp;
        // Documents that preexist the development of this service lack the curb prop.
        const curb = Object.hasOwnProperty(photoStoryData, "curb") ?
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
      payload = {firebaseID: payload}
      // console.log(payload);

      // const client = axios.create({
      //   baseURL: private_api_endpoint_url,
      //   headers: { 'Content-Type': 'application/json' }
      // })
      // eslint-disable-next-line promise/no-nesting
      return axios.post(private_api_endpoint_url, payload).then(resp => {
        console.log(resp);
        return;
      });
    }));
  });