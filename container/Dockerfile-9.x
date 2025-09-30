FROM    ghcr.io/almalinux/10-base:10.0

ARG     VARIANT=build

# Add our repositories
# temporary bootstrap repository
# FIXME: if [ ${VARIANT} = build ]
COPY    files/xcp-ng-8.99.repo /etc/yum.repos.d/xcp-ng.repo

# Almalinux 10 devel
COPY    files/Alma10-devel.repo /etc/yum.repos.d/

# Install GPG key
RUN     curl -sSf https://xcp-ng.org/RPM-GPG-KEY-xcpng -o /etc/pki/rpm-gpg/RPM-GPG-KEY-xcpng

# dnf config-manager not available yet?
RUN     if [ ${VARIANT} != build ]; then \
            sed -i -e 's/^enabled=1$/enabled=0/' /etc/yum.repos.d/xcp-ng.repo; \
        fi

# Update
RUN     dnf update -y \
        # Common build requirements
        && dnf install -y \
            gcc \
            gcc-c++ \
            git \
            make \
            rpm-build \
            redhat-rpm-config \
            python3-rpm \
            sudo \
            dnf-plugins-core \
            epel-release \
        # EPEL: needs epel-release installed first
        && dnf install -y \
            epel-rpm-macros \
            almalinux-git-utils \
            ccache \
        # Niceties
        && dnf install -y \
            bash-completion \
            vim \
            wget \
            which \
        # FIXME: isn't it already pulled as almalinux-release when available?
        && if [ ${VARIANT} != bootstrap ]; then \
            dnf install -y \
            xcp-ng-release \
            xcp-ng-release-presets; \
        fi \
        # clean package cache to avoid download errors
        && yum clean all

# enable repositories commonly required to build
RUN     dnf config-manager --enable crb

# workaround sudo not working (e.g. in podman 4.9.3 in Ubuntu 24.04)
RUN     chmod 0400 /etc/shadow

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
# FIXME: check it we really need any of this
# COPY    --chown=builder:builder files/rpmmacros /home/builder/.rpmmacros

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["bash"]
