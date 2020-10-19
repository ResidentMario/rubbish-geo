const admin = require('firebase-admin');
const uuid4 = require('uuid').v4;

// Use a static runID for local testing, and a randomly generated one for remote testing.
const rubbishGeoEnv = process.env.RUBBISH_GEO_ENV;
if (rubbishGeoEnv === undefined) {
  throw Error('RUBBISH_GEO_ENV environment variable is not set.')
}
const runID = rubbishGeoEnv === 'local' ? 'f976f9cb-ecc5-4613-93e0-6327536cd684' : uuid4();

admin.initializeApp();
const db = admin.firestore();

async function insertPickup(lat, long) {
  const pickupID = uuid4();
  await db.collection('Story').doc(pickupID).set({
    photoStoryID: pickupID,
    lat: lat,
    long: long,
    rubbishType: 'glass',
    curb: 'left',
    userTimeStamp: Math.floor(Date.now() / 1000)
  });
  return pickupID;
}

async function insertRun(runID, pickupIDs) {
  await db.collection('RubbishRunStory').doc(runID).set({
    startLat: 0,
    startLong: 0,
    endLat: 0,
    endLong: 1,
    rubbishRunStoryModelID: runID,
    photoStoryIDs: pickupIDs
  });
  return;
}

async function insertExampleRun() {
  const pickupIDs = [];

  const n_points = 10;
  for (let idx of [...Array(n_points).keys()]) {
    // eslint-disable-next-line no-await-in-loop
    const pickupID = await insertPickup(0, idx / n_points);
    pickupIDs.push(pickupID);
  }
  
  insertRun(runID, pickupIDs);
}

(async () => {
  await insertExampleRun();
  console.log(
    `Though this test succeeded the function may still fail in the POST part. Be sure to ` +
    `also check the error logs.`
  )
})();
