#!/bin/bash
# Helper script for running local integration tests.
pushd ../ && \
    RUBBISH_BASE_DIR=$PWD \
    popd && \
    GOOGLE_APPLICATION_CREDENTIALS=$RUBBISH_BASE_DIR/auth/devServiceAccountKey.json && \
GOOGLE_APPLICATION_CREDENTIALS=$GOOGLE_APPLICATION_CREDENTIALS \
    node $RUBBISH_BASE_DIR/js/functions/tests/integration/tests.js