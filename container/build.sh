#!/usr/bin/env bash
set -e

SELF_NAME=$0

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
Usage: $SELF_NAME [--platform PF] <version>
... where <version> is a 'x.y' version such as 8.0.

--platform override the default platform for the build container.
EOF
}

PLATFORM=
EXTRA_ARGS=()
OVERLAY_CACHE=0
while [ $# -ge 1 ]; do
    case "$1" in
        --help|-h)
            usage
            exit 0
            ;;
        --platform)
            [ $# -ge 2 ] || die_usage "$1 needs an argument"
            PLATFORM="$2"
            shift
            ;;
        --overlay-cache)
            OVERLAY_CACHE=1
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

if [ $OVERLAY_CACHE = 0 ]; then
    EXTRA_ARGS+=(--no-cache)
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

ALMA_VERSION=
CENTOS_VERSION=
case "$1" in
    9.*)
        DOCKERFILE=Dockerfile-9.x
        ALMA_VERSION=10.0
        : ${PLATFORM:=linux/amd64/v2}
        ;;
    8.*)
        DOCKERFILE=Dockerfile-8.x
        : ${PLATFORM:=linux/amd64}
        ;;
    *)
        echo >&2 "Unsupported release '$1'"
        exit 1
        ;;
esac

case "$PLATFORM" in
    linux/amd64)
        RPMARCH=x86_64
        ;;
    linux/amd64/v2)
        RPMARCH=x86_64_v2
        ;;
    linux/aarch64)
        RPMARCH=aarch64
        ;;
    *)
        echo >&2 "Unsupported platform '$PLATFORM'"
        exit 1
        ;;
esac

"$RUNNER" build \
    --platform "$PLATFORM" \
    -t ghcr.io/xcp-ng/xcp-ng-build-env:${1} \
    --build-arg XCP_NG_BRANCH=${1} \
    --build-arg RPMARCH="$RPMARCH" \
    --ulimit nofile=1024 \
    "${EXTRA_ARGS[@]}" \
    -f $DOCKERFILE .
