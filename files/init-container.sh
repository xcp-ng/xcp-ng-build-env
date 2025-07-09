#!/bin/sh

if [ -n "$FAIL_ON_ERROR" ]; then
    set -e
fi

# get list of user repos
(
    source /etc/os-release
    case "$VERSION_ID" in
        8.2.*) XCPREL=8/8.2 ;;
        8.3.*) XCPREL=8/8.3 ;;
        *) echo >&2 "WARNING: unknown release, not fetching user repo definitions" ;;
    esac

    curl -s https://koji.xcp-ng.org/repos/user/${XCPREL}/xcpng-users.repo |
        sed '/^gpgkey=/ ipriority=1' | sudo tee /etc/yum.repos.d/xcp-ng-users.repo > /dev/null
)

# disable repositories if needed
if [ -n "$DISABLEREPO" ]; then
    sudo yum-config-manager --disable "$DISABLEREPO"
fi

# enable additional repositories if needed
if [ -n "$ENABLEREPO" ]; then
    sudo yum-config-manager --enable "$ENABLEREPO"
fi

# update to either install newer updates or to take packages from added repos into account
sudo yum update -y --disablerepo=epel

cd "$HOME"

SRPM_MOUNT_DIR=/mnt/docker-SRPMS/
LOCAL_SRPM_DIR=$HOME/local-SRPMs

mkdir -p "$LOCAL_SRPM_DIR"

# Copy in any SRPMs from the directory mounted by the host.
if [ -d $SRPM_MOUNT_DIR ]
then
    cp $SRPM_MOUNT_DIR/*.src.rpm "$LOCAL_SRPM_DIR"
fi

# Install deps for all the SRPMs.
SRPMS=$(find "$LOCAL_SRPM_DIR" -name "*.src.rpm")

for SRPM in $SRPMS
do
    sudo yum-builddep -y "$SRPM"
done

# double the default stack size
ulimit -s 16384

if [ -n "$BUILD_LOCAL" ]; then
    pushd ~/rpmbuild
    rm BUILD BUILDROOT RPMS SRPMS -rf
    sudo yum-builddep -y SPECS/*.spec
    # in case the build deps contain xs-opam-repo, source the added profile.d file
    [ ! -f /etc/profile.d/opam.sh ] || source /etc/profile.d/opam.sh
    if [ $? == 0 ]; then
        if [ -n "$RPMBUILD_DEFINE" ]; then
            rpmbuild -ba SPECS/*.spec --define "$RPMBUILD_DEFINE"
        else
            rpmbuild -ba SPECS/*.spec
        fi
        if [ $? == 0 -a -d ~/output/ ]; then
            cp -rf RPMS SRPMS ~/output/
        fi
    fi
    popd
elif [ -n "$REBUILD_SRPM" ]; then
    # build deps already installed above
    # in case the build deps contain xs-opam-repo, source the added profile.d file
    [ ! -f /etc/profile.d/opam.sh ] || source /etc/profile.d/opam.sh
    if [ -n "$RPMBUILD_DEFINE" ]; then
        rpmbuild --rebuild "$LOCAL_SRPM_DIR/$REBUILD_SRPM" --define "$RPMBUILD_DEFINE"
    else
        rpmbuild --rebuild "$LOCAL_SRPM_DIR/$REBUILD_SRPM"
    fi
    if [ $? == 0 ]; then
        cp -rf ~/rpmbuild/RPMS ~/output/
    fi
elif [ -n "$COMMAND" ]; then
    $COMMAND
else
    /bin/bash --login
    exit 0
fi

if [ -n "$NO_EXIT" ]; then
    /bin/bash --login
fi
