#!/bin/bash

# This script is intended to called from inside a git repo by github workflows.
# It will download build-repo-internal.sh and run.py, launch a
# xcp-ng-build-env container with the git repo mounted, and will finally
# run the script build-repo-internal.sh inside the container.
#
# build-repo.sh makes use of the following environment variables:
# $CONTAINER_NAME (option - default 'build-env')
# - The name to use for the container. Useful if you want to copy build
#   artifacts out of the container once the build is finished.
# $BUILDENV_USER (optional - default 'xcp-ng')
# - The github user from which to pull the required scripts.
# $BUILDENV_BRANCH (optional - default 'master')
# - The github branch from which to pull the required scripts.
# $REPO_PACKAGE_NAME (required)
# - The package for which dependencies will be installed in the container.
# $REPO_CONFIGURE_CMD (optional - default './configure')
# - The configure command to run in the repo.
# $REPO_BUILD_CMD (optional - default 'make')
# - The build command to run in the repo.
# $REPO_TEST_CMD (optional - default 'make test')
# - The test command to run in the repo.
# $REPO_DOC_CMD (optional - no default (allow to be unset))
# - The doc command to run in the repo.

set -eux

CONTAINER_NAME=${CONTAINER_NAME:-build-env}
BUILDENV_USER=${BUILDENV_USER:-xcp-ng}
BUILDENV_BRANCH=${BUILDENV_BRANCH:-master}
GIT_BRANCH=${GIT_BRANCH:-${GITHUB_REF##*/}}

BASE_URL=https://raw.githubusercontent.com/${BUILDENV_USER}/xcp-ng-build-env/${BUILDENV_BRANCH}

RUN_SCRIPT=run.py
BUILD_SCRIPT=build-repo-internal.sh

[ -f ${RUN_SCRIPT} ] || wget "${BASE_URL}/${RUN_SCRIPT}"
[ -f ${BUILD_SCRIPT} ] || wget "${BASE_URL}/utils/${BUILD_SCRIPT}"

REPO=$(basename "$PWD")
REPO_PATH=/repos/$REPO

REPO_CONFIGURE_CMD=${REPO_CONFIGURE_CMD-./configure}
REPO_BUILD_CMD=${REPO_BUILD_CMD-make}
REPO_TEST_CMD=${REPO_TEST_CMD-make test}
REPO_DOC_CMD=${REPO_DOC_CMD-}

python run.py -p "$REPO_PACKAGE_NAME" --name "${CONTAINER_NAME}" \
    --fail-on-error \
    -b "${TARGET_XCP_NG_VERSION}" \
    -e "REPO_CONFIGURE_CMD=$REPO_CONFIGURE_CMD" \
    -e "REPO_BUILD_CMD=$REPO_BUILD_CMD" \
    -e "REPO_TEST_CMD=$REPO_TEST_CMD" \
    -e "REPO_DOC_CMD=$REPO_DOC_CMD" \
    -e "GIT_BRANCH=$GIT_BRANCH" \
    -v "$PWD:$REPO_PATH" \
    bash -l "$REPO_PATH"/build-repo-internal.sh "$REPO_PATH"
