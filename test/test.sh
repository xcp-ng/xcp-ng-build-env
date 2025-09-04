#!/usr/bin/env bash

set -eux

TARGET_XCP_NG_VERSION="8.2"

xcp-ng-dev-env-create "$TARGET_XCP_NG_VERSION"

REPOS=xcp-emu-manager

CONTAINER_NAME=${CONTAINER_NAME:-build-env}

for REPO in ${REPOS}; do
    REPO_PATH=/tmp/"$REPO"
    git clone --branch "$TARGET_XCP_NG_VERSION" https://github.com/xcp-ng-rpms/"$REPO" "$REPO_PATH"

    xcp-ng-dev container build "$REPO_PATH" "$TARGET_XCP_NG_VERSION" \
        --name "$CONTAINER_NAME" \
        --fail-on-error \
        --rm

    rm -rf "$REPO_PATH"
done
