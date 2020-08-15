#!/bin/bash
# Helper script for running local integration tests.
pushd ../ && RUBBISH_BASE_DIR=$PWD && popd
node $RUBBISH_BASE_DIR/js/functions/tests/integration/tests.js