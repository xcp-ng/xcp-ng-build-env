#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# PYTHON_ARGCOMPLETE_OK

"""
Thin wrapper around "docker run" or "podman run".

Simplifies the creation of a build environment for XCP-ng packages.
"""

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import argcomplete

CONTAINER_PREFIX = "ghcr.io/xcp-ng/xcp-ng-build-env"

DEFAULT_ULIMIT_NOFILE = 2048
RPMBUILD_STAGES = "abpfcilsrd"  # valid X values in `rpmbuild -bX`

SUPPORTED_RUNNERS = ["docker", "podman"]

RUNNERS_HELP = ' / '.join(SUPPORTED_RUNNERS)

def get_runner():
    RUNNER = os.getenv("XCPNG_OCI_RUNNER")
    if RUNNER is None:
        for command in SUPPORTED_RUNNERS:
            if shutil.which(command):
                RUNNER = command
                break
        else:
            raise Exception(f"cannot find a supported runner: {SUPPORTED_RUNNERS}")
    return RUNNER

def is_podman(runner):
    if os.path.basename(runner) == "podman":
        return True
    return subprocess.getoutput(f"{runner} --version").startswith("podman ")


def get_timezone() -> str:
    # Forward the the `TZ` environment variable if provided
    tz = os.environ.get("TZ")
    if tz is not None:
        return tz
    # Otherwise use `timedatectl` if available, returning the timezone name
    # (e.g `Europe/Paris`)
    code, output = subprocess.getstatusoutput("timedatectl show -p Timezone --value")
    if code == 0:
        return output
    # Then fallback to the last line of `/etc/localtime`, returning the timezone configuration
    # (e.g `CET-1CEST,M3.5.0,M10.5.0/3`)
    code, output = subprocess.getstatusoutput("tail -n 1 /etc/localtime")
    if code == 0:
        return output
    # Then fallback to `UTC`
    return "UTC"


def get_local_image_platform(runner, image):
    """Return the platform string (e.g. 'linux/amd64') of a local image, or None."""
    try:
        result = subprocess.run(
            [runner, "image", "inspect", image,
             "--format", "{{.Os}}/{{.Architecture}}"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None

def add_common_args(parser):
    group = parser.add_argument_group("common arguments")
    group.add_argument('-n', '--no-exit', action='store_true',
                       help='After finishing the execution of the action, drop user into a shell')
    group.add_argument('-d', '--dir', action='append',
                       help='Local dir to mount in the '
                       'image. Will be mounted at /external/<dirname>')
    group.add_argument('-a', '--enablerepo',
                       help='additional repositories to enable before installing build dependencies. '
                       'Same syntax as yum\'s --enablerepo parameter. Available additional repositories: '
                       'check files/xcp-ng.repo.*.x.in.')
    group.add_argument('--disablerepo',
                       help='disable repositories. Same syntax as yum\'s --disablerepo parameter. '
                       'If both --enablerepo and --disablerepo are set, --disablerepo will be applied first')
    group.add_argument('--no-update', action='store_true',
                       help='do not run "yum update" on container start, use it as it was at build time')
    group.add_argument('--no-network', action='store_true',
                       help='disable all networking support in the build environment')

def add_container_args(parser):
    group = parser.add_argument_group("container arguments")
    group.add_argument('-e', '--env', action='append',
                       help='Environment variables passed directly to '
                       f'{RUNNERS_HELP} -e')
    group.add_argument('container_version',
                       help='The version of XCP-ng container to for the build. For example, 8.3.')
    group.add_argument('-v', '--volume', action='append',
                       help=f'Volume mounts passed directly to {RUNNERS_HELP} -v')
    group.add_argument('--no-rm', action='store_true',
                       help='Do not destroy the container on exit')
    group.add_argument('--syslog', action='store_true',
                       help='Enable syslog to host by mounting in /dev/log')
    group.add_argument('--name', help='Assign a name to the container')
    group.add_argument('--ulimit', action='append',
                       help=f'Ulimit options passed directly to {RUNNERS_HELP} run')
    group.add_argument('--platform', action='store',
                       help="Override the default platform for the build container. "
                       "Can notably be used to workaround podman bug #6185 fixed in v5.5.1.")
    group.add_argument('--pull', action='store',
                       choices=['always', 'missing', 'never', 'newer'],
                       help="Image pull policy. By default, 'never' is used when the image "
                       "exists locally (e.g. after a local build), and 'missing' otherwise. "
                       "Use 'always' to force pulling from the registry.")
    group.add_argument('--debug', action='store_true',
                       help='Enable script tracing in container initialization (sh -x)')

def add_mock_args(parser):
    group = parser.add_argument_group('mock arguments')
    group.add_argument('koji_tag',
                       help='The koji tag used for the build. For example, v8.3-incoming')
    group.add_argument('--recreate', action='store_true',
                       help='Destroy the existing build root before running the command.')
    group.add_argument('--spec',
                       help="SPEC file that defines the package to build.")

def buildparser():
    parser = argparse.ArgumentParser()
    subparsers_env = parser.add_subparsers(
        required=True, title="Development environments",
        help="Available environments")

    # container-based workflow
    parser_container = subparsers_env.add_parser('container', help="Use a local container to build a package")
    parser_container.set_defaults(func=container)
    subparsers_container = parser_container.add_subparsers(
        dest='action', required=True,
        help="Actions available for developing packages")

    # container build -- build an rpm using a container
    parser_container_build = subparsers_container.add_parser(
        'build',
        help="Install dependencies for the spec file(s) found in the SPECS/ subdirectory "
             "of the directory passed as parameter, then build the RPM(s). "
             "Built RPMs and SRPMs will be in RPMS/ and SRPMS/ subdirectories. "
             "Any preexisting BUILD, BUILDROOT, RPMS or SRPMS directories will be removed first.")
    add_common_args(parser_container_build)
    add_container_args(parser_container_build)
    group_container_build = parser_container_build.add_argument_group("build arguments")
    group_container_build.add_argument(
        'source_dir', nargs='?', default='.',
        help="Root path where SPECS/ and SOURCES are available. "
             "The default is the working directory")
    group_container_build.add_argument(
        '--define',
        help="Definitions to be passed to rpmbuild. Example: --define "
             "'xcp_ng_section extras', for building the 'extras' "
             "version of a package which exists in both 'base' and 'extras' versions.")
    group_container_build.add_argument(
        '-o', '--output-dir',
        help="Directory where the RPMs, SRPMs and the build logs will appear. "
             "The directory is created if it doesn't exist")
    group_container_build.add_argument(
        '--rpmbuild-opts', action='append',
        help="Pass additional option(s) to rpmbuild")
    group_container_build.add_argument(
        '--rpmbuild-stage', action='store',
        help=f"Request given -bX stage rpmbuild, X in [{RPMBUILD_STAGES}]")

    # container run -- execute commands inside a container
    parser_container_run = subparsers_container.add_parser(
        'run',
        help='Execute a command inside a container')
    add_common_args(parser_container_run)
    add_container_args(parser_container_run)
    group_container_run = parser_container_run.add_argument_group("run arguments")
    group_container_run.add_argument(
        'command', nargs='*',
        help='Command with arguments to run inside the container, '
             'if the command has arguments that start with --, '
             'separate the arguments for this tool and the command with " -- ".')

    # container shell -- like run bash
    parser_container_shell = subparsers_container.add_parser(
        'shell',
        help='Drop a shell into the prepared container')
    add_common_args(parser_container_shell)
    add_container_args(parser_container_shell)
    parser_container_run.add_argument_group("shell arguments")

    # mock-based workflow
    parser_mock = subparsers_env.add_parser('mock', help="Use mock to build a package")
    parser_mock.set_defaults(func=mock)
    subparsers_mock = parser_mock.add_subparsers(
        dest='action', required=True,
        help="Actions available for developing packages")

    # mock build
    parser_mock_build = subparsers_mock.add_parser(
        'build',
        help="Creates a build root for the koji tag if it doesn't exist yet, "
             "installs the needed dependencies in it needed for the packages, "
             "then builds the RPM(s). Built RPMs and SRPMs will be in the "
             "RPMS subdirectories.")
    add_common_args(parser_mock_build)
    add_mock_args(parser_mock_build)
    group_mock_build = parser_mock_build.add_argument_group("build arguments")
    group_mock_build.add_argument(
        'source_dir', nargs='?', default='.',
        help="Root path where SPECS/ and SOURCES are available. "
             "The default is the working directory")

    parser_mock_shell = subparsers_mock.add_parser(
        'shell',
        help="Creates a build root for the koji tag if it doesn't exist yet, "
             "drop the user into a shell within the build root with the "
             "selected directory mounted.")
    add_mock_args(parser_mock_shell)
    group_mock_shell = parser_mock_shell.add_argument_group("shell arguments")
    group_mock_shell.add_argument(
        'source_dir', nargs='?', default='.',
        help="Path that will be mounted in the build root. "
             "The default is the working directory")

    # TODO: mock run

    return parser

def container(args):
    RUNNER = get_runner()
    docker_args = [RUNNER, "run"]

    if is_podman(RUNNER):
        # With podman we use the `--userns` option to map the builder user to the user on the system.
        # The container will start with that user and not as root as with docker
        docker_args += ["--userns=keep-id:uid=1000,gid=1000", "--security-opt", "label=disable"]
    else:
        # With docker, the container starts as root and modify the builder user in the entrypoint to
        # match the uid:gid of the user launching the container, and then continue with the builder
        # user thanks to gosu.
        docker_args += ["-e", f'BUILDER_UID={os.getuid()}', "-e", f'BUILDER_GID={os.getgid()}']

    # common args
    if args.no_exit:
        docker_args += ["-e", "NO_EXIT=1"]
    if args.dir:
        for localdir in args.dir:
            if not os.path.isdir(localdir):
                print("Local directory argument is not a directory!", file=sys.stderr)
                sys.exit(1)
            ext_path = os.path.abspath(localdir)
            int_path = os.path.basename(ext_path)
            docker_args += ["-v", "%s:/external/%s" % (ext_path, int_path)]
    if args.env:
        for env in args.env:
            docker_args += ["-e", env]
    if args.enablerepo:
        docker_args += ["-e", "ENABLEREPO=%s" % args.enablerepo]
    if args.disablerepo:
        docker_args += ["-e", "DISABLEREPO=%s" % args.disablerepo]
    if args.no_update:
        docker_args += ["-e", "NOUPDATE=1"]
    if args.no_network:
        docker_args += ["--network", "none"]

    if args.no_network and not args.no_update:
        print("WARNING: network disabled but --no-update not passed", file=sys.stderr)

    # container args
    if args.volume:
        for volume in args.volume:
            docker_args += ["-v", volume]
    if not args.no_rm:
        docker_args += ["--rm=true"]
    if args.syslog:
        docker_args += ["-v", "/dev/log:/dev/log"]
    if args.name:
        docker_args += ["--name", args.name]

    ulimit_nofile = False
    if args.ulimit:
        for ulimit in args.ulimit:
            if ulimit.startswith('nofile='):
                ulimit_nofile = True
            docker_args += ["--ulimit", ulimit]
    if not ulimit_nofile:
        docker_args += ["--ulimit", "nofile=%s" % DEFAULT_ULIMIT_NOFILE]

    docker_arch = args.platform or ("linux/amd64/v2"
                                    if args.container_version == "9.0"
                                    else "linux/amd64")

    image_name = f"{CONTAINER_PREFIX}:{args.container_version}"
    if args.pull is not None:
        pull_policy = args.pull
    elif get_local_image_platform(RUNNER, image_name) == docker_arch:
        pull_policy = "never"
    else:
        pull_policy = "always"
    docker_args += ["--platform", docker_arch]
    docker_args += ["--pull", pull_policy]

    if args.debug:
        docker_args += ["-e", "SCRIPT_DEBUG=1"]

    # Some build systems try to re-open /dev/stderr (->
    # /dev/pts/0), so make sure pseudo-tty can be attached to
    # in the build environment.
    docker_args += ["--tty"]

    # --no-exit requires a tty
    wants_interactive = args.no_exit

    # action-specific
    match args.action:
        case 'build':
            if args.no_network and not args.local_repo:
                print("WARNING: network disabled but --local-repo not passed", file=sys.stderr)

            build_dir = os.path.abspath(args.source_dir)
            if args.define:
                docker_args += ["-e", "RPMBUILD_DEFINE=%s" % args.define]
            if args.output_dir:
                os.makedirs(args.output_dir, exist_ok=True)
                docker_args += ["-v", "%s:/home/builder/output" %
                                os.path.abspath(args.output_dir)]
            if args.rpmbuild_opts:
                docker_args += ["-e", "RPMBUILD_OPTS=%s" % ' '.join(args.rpmbuild_opts)]
            if args.rpmbuild_stage:
                if args.rpmbuild_stage not in RPMBUILD_STAGES:
                    print(f"--rpmbuild-stage={args.rpmbuild_stage} not in '{RPMBUILD_STAGES}'", file=sys.stderr)
                    sys.exit(1)
                docker_args += ["-e", f"RPMBUILD_STAGE={args.rpmbuild_stage}"]

            docker_args += ["-v", f"{build_dir}:/home/builder/rpmbuild"]
            docker_args += ["-e", "BUILD_LOCAL=1"]
            print(f"Building directory {build_dir}", file=sys.stderr)

        case 'run':
            docker_args += ["-e", f"COMMAND={shlex.join(args.command)}"]

        case 'shell':
            wants_interactive = True

    if wants_interactive:
        docker_args += ["--interactive"]

    # Set the timezone of the container so it corresponds to the local machine
    docker_args += ["-e", f"TZ={get_timezone()}"]

    # exec "docker run"
    docker_args += [f"{CONTAINER_PREFIX}:{args.container_version}",
                    "/usr/local/bin/init-container.sh"]
    print("Launching docker with args %s" % docker_args, file=sys.stderr)
    return subprocess.call(docker_args)

def ensure_commands_available_for_mock_action():
    missing_commands = []
    for command in ["mock", "koji"]:
        if not shutil.which(command):
            missing_commands += [command]

    if missing_commands != []:
        raise Exception(f"Cannot run mock because the commands {missing_commands} are not installed")

def ensure_mock_config(koji_tag):
    arch = "x86_64"
    build_root = f"xcpng-{koji_tag}-latest-{arch}"
    config_dir = Path.home() / ".config" / "mock"
    config_file = config_dir / f"{build_root}.cfg"

    if config_file.is_file():
        print(f'Using existing mock configuration "{os.fspath(config_file)}"')
        return build_root

    os.makedirs(config_dir, exist_ok=True)
    koji_args = ["koji", "mock-config", "--tag", koji_tag, "-a", arch, "-o", os.fspath(config_file)]
    print(f"Creating mock configuration by running {koji_args}", file=sys.stderr)

    subprocess.call(koji_args)

    return build_root

def specs_in(spec_dir):
    yield from (f for f in Path(spec_dir).glob('*.spec') if f.is_file())

def mock_install_deps(build_root, spec_file):
    mock_args = ["mock", "-r", build_root]
    mock_args += ["--no-clean", "--no-cleanup-after"]
    mock_args += ["--installdeps", spec_file]

    print(f'Installing dependencies for "{spec_file}"')
    return subprocess.call(mock_args)

def mock(args):
    ensure_commands_available_for_mock_action()
    build_root = ensure_mock_config(args.koji_tag)

    print('\nNOTICE: The error of "package does not verify" can be fixed by '
          'running `sudo sh -c \'echo "%_pkgverify_flags 0" >> '
          '/etc/rpm/macros\'\n')

    mock_args = ["mock"]

    common_args = ["-r", build_root, "--no-cleanup-after"]

    if not args.recreate:
        common_args += ["--no-clean"]

    source_dir = Path(args.source_dir)

    # action-specific
    match args.action:
        case 'build':
            mock_args += ["--rebuild"]
            mock_args += common_args

            result_dir = source_dir / 'RPMS'
            os.makedirs(result_dir, exist_ok=True)
            mock_args += ["--resultdir", os.fspath(result_dir)]

            sources_dir = source_dir / 'SOURCES'
            mock_args += ["--sources", os.fspath(sources_dir)]

            spec_dir = source_dir / 'SPECS/'
            if args.spec is None:
                spec_file = None
            else:
                spec_file = Path(args.spec)

            match (spec_file, list(specs_in(spec_dir))):
                case (None, []):
                    raise ValueError(f"No spec files found in {spec_dir}, please define one with --spec")
                case None, [spec, *_] | (spec, _):
                    mock_args += ["--spec", os.fspath(spec)]

        case 'shell':
            if args.spec is not None:
                spec_file = Path(args.spec)
                mock_install_deps(build_root, spec_file)

            root_dir = "/tmp/buildroot"

            mock_args += ["--shell"]
            mock_args += common_args

            mock_args += ["--cwd", root_dir]

            mock_args += ["--enable-plugin", "bind_mount"]

            mock_args += ["--unpriv",
                          f'--plugin-option=bind_mount:dirs=[("{Path.absolute(source_dir)}", "{root_dir}")]']

    return subprocess.call(mock_args)

def main():
    """ Main entry point. """
    parser = buildparser()

    argcomplete.autocomplete(parser)

    args = parser.parse_args()

    return_code = args.func(args)

    sys.exit(return_code)

if __name__ == "__main__":
    main()
