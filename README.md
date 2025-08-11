# xcp-ng-build-env

This container config and collection of supporting scripts allows for
creating a container to work on and build a XCP-ng package from an
SRPM or from a directory containing a `SOURCES/` and a `SPECS/`
directory along with appropriate RPM spec file and software sources.

It will build a container with the right build environment (including some
useful tools).
Depending on the parameters, it will either do everything automatically to build a
given package, or just install build-dependencies and let you work manually from a shell
in the container context. Or even just start the container and let you do anything you
want.

## Configuration

You'll need to install docker or podman. Podman should be available
from your distro repositories, for Docker follow the instructions for
your platform on https://www.docker.com/

If you have both installed, docker will be used by default.  If you
want to use a specific container runtime, set `XCPNG_OCI_RUNNER` to
the docker-compatible command to use (typically `podman` or `docker`).

## Building the container image(s)

You need one container image per target version of XCP-ng.

Clone this repository (outside any container), then use `build.sh` to
generate the images for the wanted releases of XCP-ng.
Note that Docker and Podman store container images separately.

```
Usage: ./build.sh {version_of_XCP_ng}
... where {version_of_XCP_ng} is a 'x.y' version such as 8.0.
```

## Adding custom files

In some cases, you may want to include additional files in the build
environment - for example, a custom repository configuration.

Suppose you have `/tmp/xcpng-users.repo` and you want it to be available
as a YUM repository in the container. You can do this by adding the
following line to your Dockerfile:
```
COPY /tmp/xcpng-users.repo /etc/yum.repos.d/
```

This approach is useful when you want to enable extra repositories during
the build or runtime, especially when using `run.py` to manage repositories.

## Using the container

Use the `run.py` script. It accepts a variety of parameters allowing for different uses:
* rebuild an existing source RPM (with automated installation of the build dependencies)
* build a package from an already extracted source RPM (sources and spec file), or from a directory that follows the rpmbuild convention (a `SOURCES/` directory and a `SPECS/` directory). Most useful for building packages from XCP-ng's git repositories of RPM sources: https://github.com/xcp-ng-rpms.
* or simply start a shell in the build environment, with the appropriate CentOS, EPEL and XCP-ng yum repositories enabled.

```sh
usage: run.py [-h] [-b BRANCH] [-l BUILD_LOCAL] [--define DEFINE]
              [-r REBUILD_SRPM] [-o OUTPUT_DIR] [-n] [-p PACKAGE] [-s SRPM]
              [-d DIR] [-e ENV] [-v VOLUME] [--rm] [--syslog] [--name NAME]
              [-a ENABLEREPO] [--fail-on-error]
              ...

positional arguments:
  command               Command to run inside the prepared container

optional arguments:
  -h, --help            show this help message and exit
  -b BRANCH, --branch BRANCH
                        XCP-ng version: 7.6, 8.0, etc. If not set, will
                        default to 8.0.
  -l BUILD_LOCAL, --build-local BUILD_LOCAL
                        Install dependencies for the spec file(s) found in the
                        SPECS/ subdirectory of the directory passed as
                        parameter, then build the RPM(s). Built RPMs and SRPMs
                        will be in RPMS/ and SRPMS/ subdirectories. Any
                        preexisting BUILD, BUILDROOT, RPMS or SRPMS
                        directories will be removed first. If --output-dir is
                        set, the RPMS and SRPMS directories will be copied to
                        it after the build.
  --define DEFINE       Definitions to be passed to rpmbuild (if --build-local
                        or --rebuild-srpm are passed too). Example: --define
                        'xcp_ng_section extras', for building the 'extras'
                        version of a package which exists in both 'base' and
                        'extras' versions.
  -r REBUILD_SRPM, --rebuild-srpm REBUILD_SRPM
                        Install dependencies for the SRPM passed as parameter,
                        then build it. Requires the --output-dir parameter to
                        be set.
  -o OUTPUT_DIR, --output-dir OUTPUT_DIR
                        Output directory for --rebuild-srpm and --build-local.
  -n, --no-exit         After executing either an automated build or a custom
                        command passed as parameter, drop user into a shell
  -p PACKAGE, --package PACKAGE
                        Packages for which dependencies will be installed
  -s SRPM, --srpm SRPM  SRPMs for which dependencies will be installed
  -d DIR, --dir DIR     Local dir to mount in the image. Will be mounted at
                        /external/<dirname>
  -e ENV, --env ENV     Environment variables passed directly to docker -e
  -v VOLUME, --volume VOLUME
                        Volume mounts passed directly to docker -v
  --rm                  Destroy the container on exit
  --syslog              Enable syslog to host by mounting in /dev/log
  --name NAME           Assign a name to the container
  -a ENABLEREPO, --enablerepo ENABLEREPO
                        additional repositories to enable before installing
                        build dependencies. Same syntax as yum's --enablerepo
                        parameter. Available additional repositories: xcp-ng-
                        updates_testing, xcp-ng-extras, xcp-ng-extras_testing.
  --fail-on-error       If container initialisation fails, exit rather than
                        dropping the user into a command shell
```

**Examples**

Rebuild an existing source RPM (with automated installation of the build dependencies)
```sh
./run.py -b 8.0 --rebuild-srpm /path/to/some-source-rpm.src.rpm --output-dir /path/to/output/directory --rm
```

Build from git (and put the result into RPMS/ and SRPMS/ subdirectories)
```sh
# Find the relevant repository at https://github.com/xcp-ng-rpms/
# Make sure you have git-lfs installed before cloning.
# Then... (Example taken: xapi)
git clone https://github.com/xcp-ng-rpms/xapi.git

# ... Here add your patches ...

# Build.
/path/to/run.py -b 8.0 --build-local xapi/ --rm
```

**Important switches**

* `-b` / `--branch` allows to select which version of XCP-ng to work on (defaults to the latest known version if not specified).
* `--no-exit` drops you to a shell after the build, instead of closing the container. Useful if the build fails and you need to debug.
* `--rm` destroys the container on exit. Helps preventing containers from using too much space on disk. You can still reclaim space afterwards by running `docker container prune` and `docker image prune`
* `-v` / `--volume` (see *Mounting repos from outside the container* below)

**Refreshing fuzzy patches**

In XCP-ng 9.0, `rpmbuild` rejects fuzzy patches.  The easiest-known
way to get them refreshed is to let `quilt` do the job, but that's not
fully automated.

1. modify the specfile to add `-Squilt` to `%autosetup` or
   `%autopatch` in the `%prep` block; add `BuildRequires: quilt`
2. let quilt apply them in a 8.3 buildenv (`quilt` in 8.3 is only in EPEL) and get you a shell:
   ```
xcpng/build-env/run.py --rm -b 8.3 -l . --rpmbuild-stage=p -n --enablerepo=epel
   ```
3. ask `quilt` to refresh all your patches (alternatively just the one you want)
   ```
$ cd rpmbuild/BUILD/$dir
$ quilt pop -a --refresh
$ cp patches/* ../../SOURCES/
   ```
4. carefully pick up the bits you need

Note: unfortunately `rpmbuild` (in 8.3 at least) does not add all
patches in `patches/series` upfront, so in case of real conflict this
has to be redone from step 2 each time.

## Building packages manually

If you need to build packages manually, here are some useful commands

Install the dependencies of the package using yum:

```sh
yum-builddep xapi
```

then either download the SRPM using yumdownloader and rebuild it:

```sh
yumdownloader --source xapi
rpmbuild --rebuild xapi*
```

or build from upstream sources, without producing RPMs:

```sh
git clone git://github.com/xapi-project/xen-api
cd xen-api
./configure
make
```

## Mounting external directories into the container

If you'd like to develop using the tools on your host and preserve the changes
to source and revision control but still use the container for building, you
can do using by mouning a volume in the container, using the `-v` option to mount
a directory from your host to a suitable point inside the container. For
example, if I clone some repos into a directory on my host, say `/work/code/`,
then I can mount it inside the container as follows:

```sh
./run.py -b 8.0 -v /work/code:/mnt/repos
```
