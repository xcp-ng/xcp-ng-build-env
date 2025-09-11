#!/usr/bin/env bash

set -e
if [ -n "${SCRIPT_DEBUG}" ]; then
    set -x
fi

if [ "${BUILDER_UID}" ]; then
    # BUILDER_UID is defined, update the builder ids, and continue with the builder user
    if [ "${BUILDER_GID}" != "1000" ]; then
        groupmod -g "${BUILDER_GID}" builder
    fi
    if [ "${BUILDER_UID}" != "1000" ]; then
        usermod -u "${BUILDER_UID}" -g "${BUILDER_GID}" builder
    fi
    find ~builder -maxdepth 1 -type f | xargs chown builder:builder
    # use gosu to switch user to make the command run the root process and properly
    # deal with signals
    exec /usr/local/bin/gosu builder "$@"
else
    # no BUILDER_ID, just continue as the current user
    exec "$@"
fi
