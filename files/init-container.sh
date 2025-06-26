#!/bin/sh

if [ -n "$FAIL_ON_ERROR" ]; then
    set -e
fi

os_release()
{
    (
        source /etc/os-release
        echo "$VERSION_ID"
    )
}

OS_RELEASE=$(os_release)

# get list of user repos
case "$OS_RELEASE" in
    8.2.*) XCPREL=8/8.2 ;;
    8.3.*) XCPREL=8/8.3 ;;
    *) echo >&2 "WARNING: unknown release, not fetching user repo definitions" ;;
esac

if [ -n "$XCPREL" ]; then
    curl -s https://koji.xcp-ng.org/repos/user/${XCPREL}/xcpng-users.repo |
        sed '/^gpgkey=/ ipriority=1' | sudo tee /etc/yum.repos.d/xcp-ng-users.repo > /dev/null
fi

# yum or dnf?
case "$OS_RELEASE" in
    8.2.*|8.3.*)
        DNF=yum
        CFGMGR=yum-config-manager
        BDEP=yum-builddep
        ;;
    8.99.*|9.*|10.*) # FIXME 10.* actually to bootstrap Alma10
        DNF=dnf
        CFGMGR="dnf config-manager"
        BDEP="dnf builddep"
        ;;
    *) echo >&2 "ERROR: unknown release, cannot know package manager"; exit 1 ;;
esac

# disable repositories if needed
if [ -n "$DISABLEREPO" ]; then
    sudo $CFGMGR --disable "$DISABLEREPO"
fi

# enable additional repositories if needed
if [ -n "$ENABLEREPO" ]; then
    sudo $CFGMGR --enable "$ENABLEREPO"
fi

# update to either install newer updates or to take packages from added repos into account
sudo $DNF update -y --disablerepo=epel

cd "$HOME"

# double the default stack size
ulimit -s 16384

# get the package arch used in the container (eg. "x86_64_v2")
RPMARCH=$(rpm -q glibc --qf "%{arch}")

if [ -n "$BUILD_LOCAL" ]; then
    time (
        cd ~/rpmbuild
        rm BUILD BUILDROOT RPMS SRPMS -rf
        sudo $BDEP -y SPECS/*.spec
        RPMBUILDFLAGS=(
            -ba SPECS/*.spec
            --target "$RPMARCH"
        )
        # in case the build deps contain xs-opam-repo, source the added profile.d file
        [ ! -f /etc/profile.d/opam.sh ] || source /etc/profile.d/opam.sh
        if [ $? == 0 ]; then
            if [ -n "$RPMBUILD_DEFINE" ]; then
                RPMBUILDFLAGS+=(--define "$RPMBUILD_DEFINE")
            fi
            rpmbuild "${RPMBUILDFLAGS[@]}"
            if [ $? == 0 -a -d ~/output/ ]; then
                cp -rf RPMS SRPMS ~/output/
            fi
        fi
    )
elif [ -n "$COMMAND" ]; then
    $COMMAND
else
    /bin/bash --login
    exit 0
fi

if [ -n "$NO_EXIT" ]; then
    /bin/bash --login
fi
