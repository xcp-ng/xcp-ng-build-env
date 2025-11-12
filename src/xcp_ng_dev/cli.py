#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# PYTHON_ARGCOMPLETE_OK

"""
Thin wrapper around "docker run" or "podman run".

Simplifies the creation of a build environment for XCP-ng packages.
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys

import argcomplete

CONTAINER_PREFIX = "ghcr.io/xcp-ng/xcp-ng-build-env"

DEFAULT_ULIMIT_NOFILE = 2048
RPMBUILD_STAGES = "abpfcilsrd"  # valid X values in `rpmbuild -bX`

RUNNER = os.getenv("XCPNG_OCI_RUNNER")
if RUNNER is None:
    SUPPORTED_RUNNERS = "docker podman"
    for command in SUPPORTED_RUNNERS.split():
        if shutil.which(command):
            RUNNER = command
            break
    else:
        raise Exception(f"cannot find a supported runner: {SUPPORTED_RUNNERS}")

def is_podman(runner):
    if os.path.basename(runner) == "podman":
        return True
    return subprocess.getoutput(f"{runner} --version").startswith("podman ")

def add_common_args(parser):
    group = parser.add_argument_group("common arguments")
    group.add_argument('-n', '--no-exit', action='store_true',
                       help='After finishing the execution of the action, drop user into a shell')
    group.add_argument('-d', '--dir', action='append',
                       help='Local dir to mount in the '
                       'image. Will be mounted at /external/<dirname>')
    group.add_argument('-e', '--env', action='append',
                       help='Environment variables passed directly to '
                       f'{RUNNER} -e')
    parser.add_argument('--ccache', action='store',
                        help="Use given directory as a cache for ccache")
    group.add_argument('-a', '--enablerepo', action='append',
                       help='additional repositories to enable before installing build dependencies. '
                       'Same syntax as yum\'s --enablerepo parameter. Available additional repositories: '
                       'check files/xcp-ng.repo.*.x.in.')
    group.add_argument('--disablerepo', action='append',
                       help='disable repositories. Same syntax as yum\'s --disablerepo parameter. '
                       'If both --enablerepo and --disablerepo are set, --disablerepo will be applied first')
    group.add_argument('--local-repo', action='append', default=[],
                       help="Directory where the build-dependency RPMs will be taken from, "
                       "in a [REPONAME:]DIRECTORY format, where REPONAME defaults to the basename "
                       "of DIRECTORY.")
    group.add_argument('--no-update', action='store_true',
                       help='do not run "yum update" on container start, use it as it was at build time')
    group.add_argument('--install', action='append',
                       help="install additional package on container start")
    group.add_argument('--bootstrap', action='store_true',
                       help='use a bootstrap build-env, able to build xc-ng-release')
    group.add_argument('--isarpm', action='store_true',
                       help='(internal) use a build-env suitable for the ISARPM build system')
    group.add_argument('--no-network', action='store_true',
                       help='disable all networking support in the build environment')

def add_container_args(parser):
    group = parser.add_argument_group("container arguments")
    group.add_argument('container_version',
                       help='The version of XCP-ng container to for the build. For example, 8.3.')
    group.add_argument('-v', '--volume', action='append',
                       help=f'Volume mounts passed directly to {RUNNER} -v')
    group.add_argument('--no-rm', action='store_true',
                       help='Do not destroy the container on exit')
    group.add_argument('--syslog', action='store_true',
                       help='Enable syslog to host by mounting in /dev/log')
    group.add_argument('--name', help='Assign a name to the container')
    group.add_argument('--ulimit', action='append',
                       help=f'Ulimit options passed directly to {RUNNER} run')
    group.add_argument('--platform', action='store',
                       help="Override the default platform for the build container. "
                       "Can notably be used to workaround podman bug #6185 fixed in v5.5.1.")
    group.add_argument('--debug', action='store_true',
                       help='Enable script tracing in container initialization (sh -x)')


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

    # build -- build an rpm using a container
    parser_build = subparsers_container.add_parser(
        'build',
        help="Install dependencies for the spec file(s) found in the SPECS/ subdirectory "
             "of the directory passed as parameter, then build the RPM(s). "
             "Built RPMs and SRPMs will be in RPMS/ and SRPMS/ subdirectories. "
             "Any preexisting BUILD, BUILDROOT, RPMS or SRPMS directories will be removed first.")
    add_common_args(parser_build)
    add_container_args(parser_build)
    group_build = parser_build.add_argument_group("build arguments")
    group_build.add_argument(
        'source_dir', nargs='?', default='.',
        help="Root path where SPECS/ and SOURCES are available. "
             "The default is the working directory")
    group_build.add_argument(
        '--define',
        help="Definitions to be passed to rpmbuild. Example: --define "
             "'xcp_ng_section extras', for building the 'extras' "
             "version of a package which exists in both 'base' and 'extras' versions.")
    group_build.add_argument(
        '-o', '--output-dir',
        help="Directory where the RPMs, SRPMs and the build logs will appear. "
             "The directory is created if it doesn't exist")
    group_build.add_argument(
        '--rpmbuild-opts', action='append',
        help="Pass additional option(s) to rpmbuild")
    group_build.add_argument(
        '--rpmbuild-stage', action='store',
        help=f"Request given -bX stage rpmbuild, X in [{RPMBUILD_STAGES}]")

    # builddep -- fetch/cache builddep of an rpm using a container
    parser_builddep = subparsers_container.add_parser(
        'builddep',
        help="Fetch dependencies for the spec file(s) found in the SPECS/ subdirectory "
             "of the directory passed as parameter.")
    add_container_args(parser_builddep)
    add_common_args(parser_builddep)
    group_builddep = parser_builddep.add_argument_group("builddep arguments")
    group_builddep.add_argument(
        'builddep_dir',
        help="Directory where the build-dependency RPMs will be cached. "
             "The directory is created if it doesn't exist")
    group_builddep.add_argument(
        'source_dir', nargs='?', default='.',
        help="Root path where SPECS/ and SOURCES are available. "
             "The default is the working directory")

    # run -- execute commands inside a container
    parser_run = subparsers_container.add_parser(
        'run',
        help='Execute a command inside a container')
    add_common_args(parser_run)
    add_container_args(parser_run)
    group_run = parser_run.add_argument_group("run arguments")
    group_run.add_argument(
        'command', nargs='*',
        help='Command with arguments to run inside the container, '
             'if the command has arguments that start with --, '
             'separate the arguments for this tool and the command with " -- ".')

    # shell -- like run bash
    parser_shell = subparsers_container.add_parser(
        'shell',
        help='Drop a shell into the prepared container')
    add_common_args(parser_shell)
    add_container_args(parser_shell)
    parser_run.add_argument_group("shell arguments")

    return parser

def _setup_repo(repo_dir, name, docker_args):
    subprocess.check_call(["createrepo_c", "--quiet", "--compatibility", repo_dir])
    outer_path = os.path.abspath(repo_dir)
    inner_path = f"/home/builder/local-repos/{name}"
    docker_args += ["-v", f"{outer_path}:{inner_path}:ro" ]
    with open(os.path.join(repo_dir, "builddep.repo"), "wt") as repofd:
        repofd.write(f"""
[{name}]
name=Local repository - {name} from {outer_path}
baseurl=file:///home/builder/local-repos/{name}/
enabled=1
repo_gpgcheck=0
gpgcheck=0
priority=1
        """)
    # need rw for --disablerepo=* --enablerepo={name} <sigh>
    docker_args += ["-v", f"{outer_path}/builddep.repo:/etc/yum.repos.d/{name}.repo:rw"]

def container(args):
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
    if args.ccache:
        os.makedirs(args.ccache, exist_ok=True)
        docker_args += ["-v", f"{os.path.realpath(args.ccache)}:/home/builder/ccachedir",
                        "-e", "CCACHE_DIR=/home/builder/ccachedir",
                        "-e", "PATH_PREPEND=/usr/lib64/ccache",
                        ]
    if args.enablerepo:
        docker_args += ["-e", "ENABLEREPO=%s" % ','.join(args.enablerepo)]
    if args.disablerepo:
        docker_args += ["-e", "DISABLEREPO=%s" % ','.join(args.disablerepo)]
    if args.no_update:
        docker_args += ["-e", "NOUPDATE=1"]
    if args.install:
        docker_args += ["-e", "INSTALL=%s" % ' '.join(args.install)]
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


    match platform.machine():
        case 'x86_64':
            DEFAULT_PLATFORM = ("linux/amd64/v2"
                                if args.container_version == "9.0"
                                else "linux/amd64")
        case 'aarch64':
            DEFAULT_PLATFORM = "linux/aarch64"
        case arch:
            print(f"Note: no default container platform known for {arch}", file=sys.stderr)
            DEFAULT_PLATFORM = None

    docker_arch = args.platform or DEFAULT_PLATFORM
    if not docker_arch:
        raise Exception("cannot determine container platform to use")
    docker_args += ["--platform", docker_arch]

    if args.debug:
        docker_args += ["-e", "SCRIPT_DEBUG=1"]
        docker_args += ["--log-level=debug"]

    for repo in args.local_repo:
        repo_def = repo.split(":")
        assert len(repo_def) <= 2
        repo_nick = repo_def[0] if len(repo_def) == 2 else os.path.basename(repo)
        _setup_repo(repo_def[-1], repo_nick, docker_args)

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

        case 'builddep':
            build_dir = os.path.abspath(args.source_dir)
            docker_args += ["-v", f"{build_dir}:/home/builder/rpmbuild"]
            docker_args += ["-e", "BUILD_DEPS=1"]

            if args.builddep_dir:
                os.makedirs(args.builddep_dir, exist_ok=True)
                docker_args += ["-v", "%s:/home/builder/builddep:rw" %
                                os.path.abspath(args.builddep_dir)]

        case 'run':
            docker_args += ["-e", "COMMAND=%s" % ' '.join(args.command)]

        case 'shell':
            wants_interactive = True

    if wants_interactive:
        docker_args += ["--interactive", "--tty"]

    tag = args.container_version
    if args.bootstrap:
        tag += "-bootstrap"
    if args.isarpm:
        tag += "-isarpm"

    # exec "docker run"
    docker_args += [f"{CONTAINER_PREFIX}:{tag}",
                    "/usr/local/bin/init-container.sh"]
    print("Launching docker with args %s" % docker_args, file=sys.stderr)
    return subprocess.call(docker_args)

def main():
    """ Main entry point. """
    parser = buildparser()

    argcomplete.autocomplete(parser)

    args = parser.parse_args()

    return_code = args.func(args)

    sys.exit(return_code)

if __name__ == "__main__":
    main()
