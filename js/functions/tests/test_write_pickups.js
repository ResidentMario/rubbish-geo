const admin = require('firebase-admin');
const uuid4 = require('uuid').v4;
// const assert = require('assert');

admin.initializeApp();
const db = admin.firestore();

async function insertPickup(lat, long) {
    const pickupID = uuid4();
    await db.collection('Story').doc(pickupID).set({
        photoStoryID: pickupID,
        lat: lat,
        long: long,
        rubbishType: 'glass',
        userTimeStamp: Date.now()
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
    // const runID = uuid4();
    const runID = 'f976f9cb-ecc5-4613-93e0-6327536cd684';
    const pickupIDs = [];

    const n_points = 10;
    for (let idx of [...Array(n_points).keys()]) {
        // eslint-disable-next-line no-await-in-loop
        const pickupID = await insertPickup(0, idx / n_points);
        pickupIDs.push(pickupID);
    }
    
    insertRun(runID, pickupIDs);
}

describe('Test Function Write', () => {
    it('Does the thing!', () => {
        insertExampleRun();
    });
});
