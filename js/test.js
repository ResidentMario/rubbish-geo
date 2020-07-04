const admin = require('firebase-admin');
admin.initializeApp();
const db = admin.firestore();
const uuid4 = require('uuid').v4;

async function insertRubbishRun(runID, pickupIDs) {
    await db.collection('RubbishRunStory').doc(runID).set({
        startLat: 0,
        startLong: 0,
        endLat: 0.01,
        endLat: 0.01,
        rubbishRunStoryModelID: runID,
        photoStoryIDs: pickupIDs
    });
    return;
}

async function insertPickup(runID) {
    const pickupID = uuid4();
    await db.collection('Story').doc(pickupID).set({
        photoStoryID: pickupID,
        lat: 0,
        long: 0
    });
    return pickupID;
}

(async () => {
    const runID = uuid4();
    const pickupIDs = [];

    for (let _ of [...Array(5).keys()]) {
        const pickupID = await insertPickup(runID);
        pickupIDs.push(pickupID);
    }
    
    insertRubbishRun(runID, pickupIDs);
})();
