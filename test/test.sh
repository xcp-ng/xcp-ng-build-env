#!/usr/bin/env bash

set -eux

TARGET_XCP_NG_VERSION="8.2"
REPOS=xcp-emu-manager

REPO_PATH=$(mktemp --directory --tmpdir xcp-buildenv-test.XXXXXX)
trap "rm -rf '$REPO_PATH'" EXIT

# clone first, to be sure that the token won't have expired
for REPO in ${REPOS}; do
    git clone --branch "$TARGET_XCP_NG_VERSION" https://github.com/xcp-ng-rpms/"$REPO" "$REPO_PATH/$REPO"
done

xcp-ng-dev-env-create "$TARGET_XCP_NG_VERSION"

CONTAINER_NAME=${CONTAINER_NAME:-build-env}

for REPO in ${REPOS}; do
    xcp-ng-dev container build "$TARGET_XCP_NG_VERSION" "$REPO_PATH/$REPO" \
        --name "$CONTAINER_NAME"
done
