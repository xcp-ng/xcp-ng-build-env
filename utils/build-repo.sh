#!/usr/bin/env bash

set -eux

CONTAINER_NAME=${CONTAINER_NAME:-build-env}

REPO_PATH="$1"

python run.py --name "$CONTAINER_NAME" \
    --fail-on-error \
    -l "$REPO_PATH" \
    -b "$TARGET_XCP_NG_VERSION" \
    --rm
