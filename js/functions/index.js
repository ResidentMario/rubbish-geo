const functions = require('firebase-functions');
const admin = require('firebase-admin');

admin.initializeApp();
const db = admin.firestore();

// Create and Deploy Your First Cloud Functions
// https://firebase.google.com/docs/functions/write-firebase-functions

// exports.helloWorld = functions.https.onRequest((request, response) => {
//  response.send("Hello from Firebase!");
// });

// Listens for new runs inserted into /RubbishRunStory/:runID.
exports.makeUppercase = functions.firestore.document('/RubbishRunStory/{runID}')
    .onCreate((snap, context) => {
        const rubbishRunStory = snap.data();
        const photoStoryPromises = [];
        for (let photoStoryID in rubbishRunStory.photoStoryIDs) {
            photoStoryPromises.push(db.collection('Story').doc(photoStoryID).get());
        }
        return Promise.all(photoStoryPromises).then((photoStories => {
            photoStories.map(photoStory => photoStory.data())
        }));
        // console.log("snap ", snap.data());
        // console.log("context ", context);
        // Grab the current value of what was written to Cloud Firestore.
        // const original = snap.data().original;

        // // Access the parameter `{documentId}` with `context.params`
        // functions.logger.log('Uppercasing', context.params.documentId, original);
        
        // const uppercase = original.toUpperCase();
        
        // // You must return a Promise when performing asynchronous tasks inside a Functions such as
        // // writing to Cloud Firestore.
        // // Setting an 'uppercase' field in Cloud Firestore document returns a Promise.
        // return snap.ref.set({uppercase}, {merge: true});
    });