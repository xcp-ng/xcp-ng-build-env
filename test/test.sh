#!/usr/bin/env bash

set -eux

TARGET_XCP_NG_VERSION="8.2"

xcp-ng-dev-env-create "$TARGET_XCP_NG_VERSION"

REPOS=xcp-emu-manager

CONTAINER_NAME=${CONTAINER_NAME:-build-env}

for REPO in ${REPOS}; do
    REPO_PATH=$(mktemp --directory --tmpdir xcp-buildenv-test.XXXXXX)
    trap "rm -rf '$REPO_PATH'" EXIT
    git clone --branch "$TARGET_XCP_NG_VERSION" https://github.com/xcp-ng-rpms/"$REPO" "$REPO_PATH"

    xcp-ng-dev container build "$TARGET_XCP_NG_VERSION" "$REPO_PATH" \
        --name "$CONTAINER_NAME" \
        --fail-on-error
done
