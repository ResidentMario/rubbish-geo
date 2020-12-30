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
      `to set it? For more information refer to DEPLOY.md.`
    )
  }
}

const opts = {timeoutSeconds: 300}
// Listens for new runs inserted into /RubbishRunStory/:runID.
exports.proxy_POST_PICKUPS = functions.runWith(opts).firestore.document('/RubbishRunStory/{runID}')
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
      // The user database is schema-on-write. Do not assume that just because a run entry links
      // to a pickup entry, that pickup entry actually exists. A case in prod where this
      // constraint is violated: RubbishRunStory '04yS2lIMG2ehUJrH7OO2' links to non-existant
      // Story 'KkTPjp7GIAW8uz6qWsvT'.
      if (!photoStory.exists) {
        return null;  // sentinal value for filter(v => v)
      }
      const photoStoryData = photoStory.data();

      // The user database is schema-on-write. Do not assume any fields exist, but if they do
      // exist, assume that they are valid. If fields do not exist that are expected to exist,
      // log a warning and silently drop the pickup.
      const requiredFields = ['photoStoryID', 'rubbishType', 'userTimeStamp', 'long', 'lat'];
      const fieldExistsConstraintViolated = (
        requiredFields
        .map(field => !(field in photoStoryData))
        .some(v => v)
      )
      if (fieldExistsConstraintViolated) {
        const missingFields = (
          requiredFields
          .map(field => (field in photoStoryData) ? null : field)
          .filter(v => v)
        )
        functions.logger.info(
          `The pickup with ID ${photoStoryData.photoStoryID} associated with the run with ID ` +
          `${firebaseID} is missing required fields [${missingFields}]. This pickup will not be ` +
          `included in the pickups written to the database.`
        )
        return null;  // sentinal value for filter(v => v)
      }

      // NOTE(aleksey): The curb is allowed to be empty. Runs that predate this service lack one.
      // NOTE(aleksey): The user database calls this field "roadSnapping". We rename the field to
      // curb here, because that is a much better name. It'd be nice if we used curb everywhere.
      const curb = ("roadSnapping" in photoStoryData) ? photoStoryData.roadSnapping : null;

      firebaseRunID = photoStoryData.photoStoryID;
      const type = photoStoryData.rubbishType;
      const timestamp = photoStoryData.userTimeStamp;
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
    payload = payload.filter(v => v);
    payload = {[firebaseID]: payload}

    functions.logger.info(
      `Processing proxy_POST_pickups(${firebaseID}).`
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
        `The proxy_POST_pickups database listener failed to POST to the ` +
        `POST_pickups functional API endpoint. Failed with ${err.name}: ${err.message}.`
      );
      throw err;
    });
  });
