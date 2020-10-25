#!/bin/bash
# Helper script for running local integration tests.
pushd ../ && \
    RUBBISH_BASE_DIR=$PWD \
    GOOGLE_APPLICATION_CREDENTIALS=$PWD/js/serviceAccountKey.json && \
    popd
GOOGLE_APPLICATION_CREDENTIALS=$GOOGLE_APPLICATION_CREDENTIALS \
    node $RUBBISH_BASE_DIR/js/functions/tests/integration/tests.js