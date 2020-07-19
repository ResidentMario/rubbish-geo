const admin = require('firebase-admin');
admin.initializeApp();
const db = admin.firestore();

// const uuid4 = require('uuid').v4;

// async function insertRubbishRun(runID, pickupIDs) {
//     await db.collection('RubbishRunStory').doc(runID).set({
//         startLat: 0,
//         startLong: 0,
//         endLat: 0,
//         endLat: 1,
//         rubbishRunStoryModelID: runID,
//         photoStoryIDs: pickupIDs
//     });
//     return;
// }

// async function insertPickup(lat, long) {
//     const pickupID = uuid4();
//     await db.collection('Story').doc(pickupID).set({
//         photoStoryID: pickupID,
//         lat: lat,
//         long: long
//     });
//     return pickupID;
// }

(async () => {
    const runID = '123';
    const pickupIDs = ['345', '567'];
    const res = await db.collection('RubbishRunStory').doc(runID).get({
        startLat: 0,
        startLong: 0,
        endLat: 0,
        endLong: 1,
        rubbishRunStoryModelID: runID,
        photoStoryIDs: pickupIDs
    });
})();
