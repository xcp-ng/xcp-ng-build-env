FROM    ghcr.io/almalinux/10-base:10.0

ARG     CUSTOM_BUILDER_UID=""
ARG     CUSTOM_BUILDER_GID=""

# Add our repositories
# temporary bootstrap repository
COPY    files/xcp-ng-8.99.repo /etc/yum.repos.d/xcp-ng.repo
# Almalinux 10 devel
COPY    files/Alma10-devel.repo /etc/yum.repos.d/

# Install GPG key
RUN     curl -sSf https://xcp-ng.org/RPM-GPG-KEY-xcpng -o /etc/pki/rpm-gpg/RPM-GPG-KEY-xcpng

# Update
RUN     dnf update -y

# Common build requirements
RUN     dnf install -y \
            gcc \
            gcc-c++ \
            git \
            make \
            rpm-build \
            redhat-rpm-config \
            python3-rpm \
            sudo \
            dnf-plugins-core \
            epel-release

# EPEL: needs epel-release installed first
RUN     dnf install -y \
            epel-rpm-macros \
            almalinux-git-utils

# Niceties
RUN     dnf install -y \
            bash-completion \
            vim \
            wget \
            which

# clean package cache to avoid download errors
RUN     yum clean all

# -release*, to be commented out to boostrap the build-env until it gets built
# FIXME: isn't it already pulled as almalinux-release when available?
RUN     dnf install -y \
            xcp-ng-release \
            xcp-ng-release-presets

# enable repositories commonly required to build
RUN     dnf config-manager --enable crb

# workaround sudo not working (e.g. in podman 4.9.3 in Ubuntu 24.04)
RUN     chmod 0400 /etc/shadow

# Set up the builder user
RUN     bash -c ' \
            OPTS=(); \
            if [ -n "${CUSTOM_BUILDER_UID}" ]; then \
                OPTS+=("-u" "${CUSTOM_BUILDER_UID}"); \
            fi; \
            if [ -n "${CUSTOM_BUILDER_GID}" ]; then \
                OPTS+=("-g" "${CUSTOM_BUILDER_GID}"); \
                if ! getent group "${CUSTOM_BUILDER_GID}" >/dev/null; then \
                    groupadd -g "${CUSTOM_BUILDER_GID}" builder; \
                fi; \
            fi; \
            useradd "${OPTS[@]}" builder; \
        ' \
        && echo "builder:builder" | chpasswd \
        && echo "builder ALL=(ALL:ALL) NOPASSWD: ALL" >> /etc/sudoers

RUN     mkdir -p /usr/local/bin
COPY    files/init-container.sh /usr/local/bin/init-container.sh

# FIXME: check it we really need any of this
# COPY    files/rpmmacros /home/builder/.rpmmacros
