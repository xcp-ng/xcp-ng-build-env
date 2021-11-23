#!/usr/bin/env bash

set -eux

TARGET_XCP_NG_VERSION="8.2"

./build.sh "$TARGET_XCP_NG_VERSION"

REPOS=xcp-emu-manager

CONTAINER_NAME=${CONTAINER_NAME:-build-env}

for REPO in ${REPOS}; do
    REPO_PATH=/tmp/"$REPO"
    git clone --branch "$TARGET_XCP_NG_VERSION" git://github.com/xcp-ng-rpms/"$REPO" "$REPO_PATH"

    ./run.py --name "$CONTAINER_NAME" \
        --fail-on-error \
        -l "$REPO_PATH" \
        -b "$TARGET_XCP_NG_VERSION" \
        --rm

    rm -rf "$REPO_PATH"
done
