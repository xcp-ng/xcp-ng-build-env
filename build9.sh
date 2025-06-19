#!/usr/bin/env bash

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 {version}"
    echo "... where {version} is a 'x.y' version such as 8.0."
    exit
fi

RUNNER=""
if [ -n "$XCPNG_OCI_RUNNER" ]; then
    RUNNER="$XCPNG_OCI_RUNNER"
else
    SUPPORTED_RUNNERS="docker podman"
    for COMMAND in $SUPPORTED_RUNNERS; do
        if command -v $COMMAND >/dev/null; then
            RUNNER="$COMMAND"
            break
        fi
    done
    if [ -z "$RUNNER" ]; then
        echo >&2 "cannot find a supported runner: $SUPPORTED_RUNNERS"
        exit 1
    fi
fi

cd $(dirname "$0")

CUSTOM_ARGS=()

case "$1" in
    9.*)
        DOCKERFILE=Dockerfile-9.x
        ALMA_VERSION=10.0
        ;;
    *)
        echo >&2 "Unsupported release '$1'"
        exit 1
        ;;
esac

#sed -e "s/@XCP_NG_BRANCH@/${1}/g" "$REPO_FILE" > files/tmp-xcp-ng.repo
#sed -e "s/@CENTOS_VERSION@/${CENTOS_VERSION}/g" files/CentOS-Vault.repo.in > files/tmp-CentOS-Vault.repo

# Support using docker on other archs (e.g. arm64 for Apple Silicon), building for amd64
if [ "$(uname -m)" != "x86_64" ]; then
    CUSTOM_ARGS+=( "--platform" "linux/amd64" )
fi

CUSTOM_UID="$(id -u)"
CUSTOM_GID="$(id -g)"

if [ "${CUSTOM_UID}" -eq 0 ] || [ "${CUSTOM_GID}" -eq 0 ]; then
  if [ -z "${SUDO_GID}" ] || [ -z "${SUDO_UID}" ] || [ -z "${SUDO_USER}" ] || \
     [ -z "${SUDO_COMMAND}" ] || [ "${SUDO_GID}" -eq 0 ] || [ "${SUDO_UID}" -eq 0 ]; then
    echo -e "[ERROR] This operation cannot be performed by the 'root' user directly:"
    echo -e "\tplease use an unprivileged user (eventually with 'sudo')"
    exit 1
  fi
  CUSTOM_UID="${SUDO_UID}"
  CUSTOM_GID="${SUDO_GID}"
fi

# Support for seamless use of current host user
# and Docker user "builder" inside the image
CUSTOM_ARGS+=( "--build-arg" "CUSTOM_BUILDER_UID=${CUSTOM_UID}" )
CUSTOM_ARGS+=( "--build-arg" "CUSTOM_BUILDER_GID=${CUSTOM_GID}" )

"$RUNNER" build \
    "${CUSTOM_ARGS[@]}" \
    -t xcp-ng/xcp-ng-build-env:${1} \
    --ulimit nofile=1024 \
    -f $DOCKERFILE .

rm -f files/tmp-xcp-ng.repo
rm -f files/tmp-CentOS-Vault.repo
