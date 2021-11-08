#!/bin/bash
set -e
if [ -z "$1" ]; then
    echo "Usage: $0 {version}"
    echo "... where {version} is a 'x.y' version such as 8.0."
    exit
fi

cd $(dirname "$0")

CUSTOM_ARGS=()

DEFAULT_VERSION="8.2"
MAJOR=${1:0:1}

RE_ISNUM='^[0-9]$'
if ! [[ ${MAJOR} =~ ${RE_ISNUM} ]]; then
    echo "[WARNING] The first character of version should be a number: '${MAJOR}' was passed:"
    MAJOR=8
    set -- "${DEFAULT_VERSION}" "${@:2}"
    echo "          using default version ${1}"
fi

if [ ${MAJOR} -eq 7 ]; then
    REPO_FILE=files/xcp-ng.repo.7.x.in
    CENTOS_VERSION=7.2.1511
else
    REPO_FILE=files/xcp-ng.repo.8.x.in
    CENTOS_VERSION=7.5.1804
fi

sed -e "s/@XCP_NG_BRANCH@/${1}/g" "$REPO_FILE" > files/tmp-xcp-ng.repo
sed -e "s/@CENTOS_VERSION@/${CENTOS_VERSION}/g" files/CentOS-Vault.repo.in > files/tmp-CentOS-Vault.repo

# Support using docker on arm64, building
# for amd64 (e.g. Apple Silicon)
if [ "$(uname -m)" == "arm64" ]; then
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

docker build \
    $(echo "${CUSTOM_ARGS[@]}") \
    -t xcp-ng/xcp-ng-build-env:${1} \
    -f Dockerfile-${MAJOR}.x .

rm -f files/tmp-xcp-ng.repo
rm -f files/tmp-CentOS-Vault.repo
