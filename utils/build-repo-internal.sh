#!/bin/bash -l

set -eux

REPO_PATH=$1
REPO=$(basename "$REPO_PATH")

cp -r "$REPO_PATH" .
cd "$REPO"

eval "$REPO_CONFIGURE_CMD"
eval "$REPO_BUILD_CMD"
eval "$REPO_TEST_CMD"
eval "$REPO_DOC_CMD"
