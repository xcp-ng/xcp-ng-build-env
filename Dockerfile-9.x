FROM    ghcr.io/almalinux/10-base:latest

ARG     CUSTOM_BUILDER_UID=""
ARG     CUSTOM_BUILDER_GID=""

# Remove all repositories
#RUN     rm /etc/yum.repos.d/*

# Add only the specific CentOS 7.5 repositories, because that's what XS used for the majority of packages
#COPY    files/tmp-CentOS-Vault.repo /etc/yum.repos.d/CentOS-Vault-7.5.repo

# Add our repositories
# Repository file depends on the target version of XCP-ng, and is pre-processed by build.sh
#COPY    files/tmp-xcp-ng.repo /etc/yum.repos.d/xcp-ng.repo

# Install GPG key
#RUN     curl -sSf https://xcp-ng.org/RPM-GPG-KEY-xcpng -o /etc/pki/rpm-gpg/RPM-GPG-KEY-xcpng

# Use priorities so that packages from our repositories are preferred over those from Alma repositories
#RUN     yum install -y yum-plugin-priorities

# Update
RUN     yum update -y

# Common build requirements
RUN     yum install -y \
            gcc \
            gcc-c++ \
            git \
            make \
            rpm-build \
            redhat-rpm-config \
            python3-rpm \
            sudo \
            yum-utils \
            epel-release

# EPEL
RUN     yum install -y \
            epel-rpm-macros

# Niceties
RUN     yum install -y \
            vim \
            wget \
            which

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
COPY    files/rpmmacros.9.0 /home/builder/.rpmmacros
