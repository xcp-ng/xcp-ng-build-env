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

You'll need to install git-lfs to be able to download the source tarballs from
git, otherwise when running xcp-ng-dev, it won't be able to extract the sources.

## Installation

This can be done with `uv`:
```
uv tool install --from git+https://github.com/xcp-ng/xcp-ng-build-env xcp-ng-dev
```
or `pipx:`
```
pipx install git+https://github.com/xcp-ng/xcp-ng-build-env
```

After this, two new commands will be available: `xcp-ng-dev-env-create` and
`xcp-ng-dev`.

If you want to develop the package and try the changes as you develop the
package, clone the repository and install the `xcp-ng-dev` package:

```bash
git clone github.com:xcp-ng/xcp-ng-build-env
cd xcp-ng-build-env
uv tool install --editable .
```

If `uv` is not available you can use other tools to install python packages,
like `pipx install --editable .`

If you do not want this behaviour, use: `uv tool install --from . xcp-ng-dev`
or `pipx install .`

## Building the container image(s)

You need one container image per target version of XCP-ng.

Clone this repository (outside any container), then use `xcp-ng-dev-env-create` to
generate the images for the wanted releases of XCP-ng.
Note that Docker and Podman store container images separately.

```
Usage: xcp-ng-dev-env-create {version_of_XCP_ng}
... where {version_of_XCP_ng} is a 'x.y' version such as 8.0.
```

## Using the container

Use `xcp-ng-dev`. It accepts a variety of parameters allowing for different uses:
* rebuild an existing source RPM (with automated installation of the build dependencies)
* build a package from an already extracted source RPM (sources and spec file), or from a directory that follows the rpmbuild convention (a `SOURCES/` directory and a `SPECS/` directory). Most useful for building packages from XCP-ng's git repositories of RPM sources: https://github.com/xcp-ng-rpms.
* or simply start a shell in the build environment, with the appropriate CentOS, EPEL and XCP-ng yum repositories enabled.

**Examples**

Build from git (and put the result into RPMS/ and SRPMS/ subdirectories)
```sh
# Find the relevant repository at https://github.com/xcp-ng-rpms/
# Make sure you have git-lfs installed before cloning.
# Then... (Example taken: xapi)
git clone https://github.com/xcp-ng-rpms/xapi.git

# ... Here add your patches ...

# Build.
xcp-ng-dev container build -b 8.2 --rm xapi/
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
```sh
xcp-ng-dev container build --rm -b 8.3 --rpmbuild-stage=p -n --enablerepo=epel .
```
3. ask `quilt` to refresh all your patches (alternatively just the one you want)
```sh
cd rpmbuild/BUILD/$dir
quilt pop -a --refresh
cp patches/* ../../SOURCES/
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
can do so by mounting a volume in the container, using the `-v` option to mount
a directory from your host to a suitable point inside the container. For
example, if I clone some repos into a directory on my host, say `/work/code/`,
then I can mount it inside the container as follows:

```sh
xcp-ng-dev container shell -b 8.2 -v /work/code:/mnt/repos
```
