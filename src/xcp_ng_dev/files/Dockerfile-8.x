ARG     CENTOS_VERSION=7.5.1804

FROM    centos:${CENTOS_VERSION}

# Remove all repositories
RUN     rm /etc/yum.repos.d/*

# Add only the specific CentOS 7.5 repositories, because that's what XS used for the majority of packages
ARG     CENTOS_VERSION
COPY    files/CentOS-Vault.repo.in /etc/yum.repos.d/CentOS-Vault-7.5.repo
RUN     sed -i -e "s/@CENTOS_VERSION@/${CENTOS_VERSION}/g" /etc/yum.repos.d/CentOS-Vault-7.5.repo

# Add our repositories
# Repository file depends on the target version of XCP-ng, and is pre-processed by build.sh
ARG     XCP_NG_BRANCH=8.3
COPY    files/xcp-ng.repo.8.x.in /etc/yum.repos.d/xcp-ng.repo
RUN     sed -i -e "s/@XCP_NG_BRANCH@/${XCP_NG_BRANCH}/g" /etc/yum.repos.d/xcp-ng.repo

# Install GPG key
RUN     curl -sSf https://xcp-ng.org/RPM-GPG-KEY-xcpng -o /etc/pki/rpm-gpg/RPM-GPG-KEY-xcpng

# Fix invalid rpmdb checksum error with overlayfs, see https://github.com/docker/docker/issues/10180
# (still needed?)
RUN     yum install -y yum-plugin-ovl

# Use priorities so that packages from our repositories are preferred over those from CentOS repositories
RUN     yum install -y yum-plugin-priorities

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
            rpm-python \
            sudo \
            yum-utils \
            epel-release \
            epel-rpm-macros

# Niceties
RUN     yum install -y \
            vim \
            wget \
            which

# clean package cache to avoid download errors
RUN     yum clean all

# OCaml in XS may be older than in CentOS
RUN     sed -i "/gpgkey/a exclude=ocaml*" /etc/yum.repos.d/Cent* /etc/yum.repos.d/epel*

# create the builder user
RUN     groupadd -g 1000 builder \
        && useradd -u 1000 -g 1000 builder \
        && echo "builder:builder" | chpasswd \
        && echo "builder ALL=(ALL:ALL) NOPASSWD: ALL" >> /etc/sudoers

RUN     mkdir -p /usr/local/bin
RUN     curl -fsSL "https://github.com/tianon/gosu/releases/download/1.17/gosu-amd64" -o /usr/local/bin/gosu \
        && chmod +x /usr/local/bin/gosu
COPY    files/init-container.sh /usr/local/bin/init-container.sh
COPY    files/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY    --chown=builder:builder files/rpmmacros /home/builder/.rpmmacros

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["bash"]
