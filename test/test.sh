#!/usr/bin/env bash

set -eux

TARGET_XCP_NG_VERSION="8.2"

./build.sh "$TARGET_XCP_NG_VERSION"

REPOS=xcp-emu-manager

for REPO in ${REPOS}; do
    REPO_PATH=/tmp/"$REPO"
    git clone --branch "$TARGET_XCP_NG_VERSION" git://github.com/xcp-ng-rpms/"$REPO" "$REPO_PATH"

    TARGET_XCP_NG_VERSION="$TARGET_XCP_NG_VERSION" \
        bash utils/build-repo.sh "$REPO_PATH"

    rm -rf "$REPO_PATH"
done
