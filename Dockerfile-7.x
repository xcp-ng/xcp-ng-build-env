ARG     CENTOS_VERSION=7.2.1511

FROM    centos:${CENTOS_VERSION}

ARG     CUSTOM_BUILDER_UID=""
ARG     CUSTOM_BUILDER_GID=""

# Remove all repositories
RUN     rm /etc/yum.repos.d/*

# Add only the specific CentOS 7.2 repositories, because that's what XS used for the majority of packages
ARG     CENTOS_VERSION
COPY    files/CentOS-Vault.repo.in /etc/yum.repos.d/CentOS-Vault-7.2.repo
RUN     sed -e "s/@CENTOS_VERSION@/${CENTOS_VERSION}/g" -i /etc/yum.repos.d/CentOS-Vault-7.2.repo

# Add our repositories
# Repository file depends on the target version of XCP-ng, and is pre-processed by build.sh
ARG     XCP_NG_BRANCH=7.6
COPY    files/xcp-ng.repo.7.x.in /etc/yum.repos.d/xcp-ng.repo
RUN     sed -e "s/@XCP_NG_BRANCH@/${XCP_NG_BRANCH}/g" -i /etc/yum.repos.d/xcp-ng.repo

# Fix invalid rpmdb checksum error with overlayfs, see https://github.com/docker/docker/issues/10180
RUN     yum install -y yum-plugin-ovl

# Use priorities so that packages from our repositories are preferred over those from CentOS repositories
RUN     yum install -y yum-plugin-priorities

# Update
RUN     yum update -y

# Build requirements
RUN     yum install -y --exclude=gcc-xs \
            gcc \
            gcc-c++ \
            git \
            git-lfs \
            make \
            mercurial \
            mock \
            rpm-build \
            rpm-python \
            sudo \
            yum-utils \
            epel-release

# Niceties
RUN     yum install -y \
            vim \
            wget \
            which

# clean package cache to avoid download errors
RUN     yum clean all

# OCaml in XS is slightly older than in CentOS
RUN     sed -i "/gpgkey/a exclude=ocaml*" /etc/yum.repos.d/Cent* /etc/yum.repos.d/epel*

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
        && echo "builder ALL=(ALL:ALL) NOPASSWD: ALL" >> /etc/sudoers \
        && usermod -G mock builder

RUN     mkdir -p /usr/local/bin
COPY    files/init-container.sh /usr/local/bin/init-container.sh
COPY    files/rpmmacros /home/builder/.rpmmacros
