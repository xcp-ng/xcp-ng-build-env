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

After this, a new command will be available: `xcp-ng-dev`.

If you want to develop the package and try the changes as you develop
the package, or prefer updating the version from a git repo rather
than from the python tools, clone the repository and install the
`xcp-ng-dev` package:

```bash
git clone github.com:xcp-ng/xcp-ng-build-env
cd xcp-ng-build-env
uv tool install --editable .
```

If `uv` is not available you can use other tools to install python packages,
like `pipx install --editable .`

If you do not want this behaviour, use: `uv tool install --from . xcp-ng-dev`
or `pipx install .`

## Container images

Many features of this tool rely on a container image. You can either pull a pre-built
image from ghcr.io, or build it locally (which requires a local checkout of this git
repository).


### Using the prebuilt images

For convenience, when no image is found on your system, images are pulled from ghcr.io.

You can also explicitly download the latest image for a given XCP-ng version (8.3, 9.0...)
with `docker pull ghcr.io/xcp-ng/xcp-ng-build-env:8.3` or
`podman pull ghcr.io/xcp-ng/xcp-ng-build-env:8.3` (replace the version if needed).

As the images are regularly updated, it is recommended to run this from time to time.
Especially if you see that the images pull a lot of RPM updates each time they start.

### Building the container image(s)

Building your own images is also supported.

Clone this repository (outside any container), then use `./container/build.sh` to
generate the image. Adapt the version to the wanted release of XCP-ng.
Note that Docker and Podman store container images separately.

```
Usage: ./container/build.sh [--platform PF] <version>
... where <version> is a 'x.y' version such as 8.0.
```

The build produces `localhost/xcp-ng-build-env:<version>`, a purely local
name, distinct from the `ghcr.io/xcp-ng/xcp-ng-build-env:<version>` image
published by CI. The two can coexist for the same version and neither
overwrites the other.

### Choosing which image is used

`xcp-ng-dev` selects the image for a given version in this order:

1. the image given by `--image`, or by the `XCPNG_CONTAINER_IMAGE`
   environment variable;
2. the locally built `localhost/xcp-ng-build-env:<version>`, if present;
3. the published `ghcr.io/xcp-ng/xcp-ng-build-env:<version>`, pulled if needed.

The selected image is printed on startup, so it is always visible which one a
run is using. A locally built image is never pulled or refreshed from a
registry. Rebuild it with `./container/build.sh` to update it.

## updating

Depending on how you installed:
* with `uv`: just run the same command
* with `pipx`: run the same command, with `--force`
* editable with `git`: just update your git working tree

Then update your container image(s), as described in "Container images".

## Completion

### Bash

To install the completion, add `eval "$(register-python-argcomplete xcp-ng-dev)"` to `~/.bash_completion` and relaunch Bash.

### Zsh

To install the completion, add `eval "$(register-python-argcomplete xcp-ng-dev)"` to `~/.zshrc` and relaunch Zsh.

### Fish

To install the completion, run `register-python-argcomplete --shell fish xcp-ng-dev > ~/.config/fish/completions/xcp-ng-dev.fish` and relaunch fish.


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
xcp-ng-dev container build 8.2 xapi/
```

**Important switches**

* `--no-exit` drops you to a shell after the build, instead of closing the container. Useful if the build fails and you need to debug.
* `--no-rm` keeps the container on exit, if you want to keep it for whatever reason. If you do, you can still reclaim space afterwards by running `docker container prune` and `docker image prune`.
* `-v` / `--volume` (see *Mounting repos from outside the container* below)

**Refreshing fuzzy patches**

In XCP-ng 9.0, `rpmbuild` rejects fuzzy patches.  The easiest-known
way to get them refreshed is to let `quilt` do the job, but that's not
fully automated.

1. modify the specfile to add `-Squilt` to `%autosetup` or
   `%autopatch` in the `%prep` block; add `BuildRequires: quilt`
2. let quilt apply them in a 8.3 buildenv (`quilt` in 8.3 is only in EPEL) and get you a shell:
```sh
xcp-ng-dev container build --rpmbuild-stage=p -n --enablerepo=epel 8.3
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

### Building packages manually

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

### Mounting external directories into the container

If you'd like to develop using the tools on your host and preserve the changes
to source and revision control but still use the container for building, you
can do so by mounting a volume in the container, using the `-v` option to mount
a directory from your host to a suitable point inside the container. For
example, if I clone some repos into a directory on my host, say `/work/code/`,
then I can mount it inside the container as follows:

```sh
xcp-ng-dev container shell -v /work/code:/mnt/repos 8.2
```

### Using mock

Mock is the tool used by koji to build packages.
It uses chroots as the isolation mechanism instead of containers.
The chrooted environments are called build roots.
Mock uses koji tags instead of image tags to know how to create a build roots. 

To build packages using mock, run `xcp-ng-dev mock`.
This command accepts a variety of parameters allowing for different uses:
* build a package from a directory that follows the rpmbuild convention (a
  `SOURCES/` directory and a `SPECS/` directory).This is most useful for
  building packages from XCP-ng's git repositories of RPM sources:
  https://github.com/xcp-ng-rpms.
* start a shell in the build environment, with the appropriate CentOS, EPEL and
  XCP-ng yum repositories enabled.

**Examples**

Build from git (and put the result into RPMS/)
```sh
# Find the relevant repository at https://github.com/xcp-ng-rpms/
# Make sure you have git-lfs installed before cloning.
# Then... (Example taken: xapi)
git clone https://github.com/xcp-ng-rpms/xapi.git

# ... Here add your patches ...

# Build.
xcp-ng-dev mock build v8.3-incoming xapi/
```

**Important switches**

* `shell` drops you to a shell, ready to run commands in the build environment with the sources loaded.
* `list` lists the build roots present in the computer, these can be deleted with a simple rm -r
* `--recreate` deletes the build root before running the command. Helpful to run when the build root has become outdated and building the package fails unexpectedly.

