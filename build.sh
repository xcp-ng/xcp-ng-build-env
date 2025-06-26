#!/usr/bin/env bash
set -e

die() {
    echo >&2
    echo >&2 "ERROR: $*"
    echo >&2
    exit 1
}

die_usage() {
    usage >&2
    die "$*"
}

usage() {
    cat <<EOF
Usage: $0 <version>
... where <version> is a 'x.y' version such as 8.0.
EOF
}

while [ $# -ge 1 ]; do
    case "$1" in
        --help|-h)
            usage
            exit 0
            ;;
        -*)
            die_usage "unknown flag '$1'"
            ;;
        *)
            break
            ;;
    esac
    shift
done

[ -n "$1" ] || die_usage "version parameter missing"

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

ALMA_VERSION=
CENTOS_VERSION=
case "$1" in
    9.*)
        DOCKERFILE=Dockerfile-9.x
        ALMA_VERSION=10.0
        PLATFORM=linux/amd64/v2
        ;;
    8.*)
        DOCKERFILE=Dockerfile-8.x
        PLATFORM=linux/amd64
        ;;
    7.*)
        DOCKERFILE=Dockerfile-7.x
        PLATFORM=linux/amd64
        ;;
    *)
        echo >&2 "Unsupported release '$1'"
        exit 1
        ;;
esac

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
    --platform "$PLATFORM" \
    "${CUSTOM_ARGS[@]}" \
    -t ghcr.io/xcp-ng/xcp-ng-build-env:${1} \
    --build-arg XCP_NG_BRANCH=${1} \
    --ulimit nofile=1024 \
    -f $DOCKERFILE .
