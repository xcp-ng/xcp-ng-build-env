#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Thin wrapper around "docker run" or "podman run".

Simplifies the creation of a build environment for XCP-ng packages.
"""

import argparse
import os
import subprocess
import shutil
import sys
import uuid

CONTAINER_PREFIX = "ghcr.io/xcp-ng/xcp-ng-build-env"

DEFAULT_BRANCH = '8.3'
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
    if subprocess.getoutput(f"{runner} --version").startswith("podman "):
        return True
    return False

def add_common_args(parser):
    parser.add_argument('-b', '--branch',
                        help='XCP-ng version: 7.6, %s, etc. If not set, '
                             'will default to %s.' % (DEFAULT_BRANCH, DEFAULT_BRANCH))
    parser.add_argument('-n', '--no-exit', action='store_true',
                        help='After finishing the execution of the action, drop user into a shell')
    parser.add_argument('-d', '--dir', action='append',
                        help='Local dir to mount in the '
                        'image. Will be mounted at /external/<dirname>')
    parser.add_argument('-e', '--env', action='append',
                        help='Environment variables passed directly to '
                             f'{RUNNER} -e')
    parser.add_argument('-a', '--enablerepo',
                        help='additional repositories to enable before installing build dependencies. '
                             'Same syntax as yum\'s --enablerepo parameter. Available additional repositories: '
                             'check files/xcp-ng.repo.*.x.in.')
    parser.add_argument('--disablerepo',
                        help='disable repositories. Same syntax as yum\'s --disablerepo parameter. '
                             'If both --enablerepo and --disablerepo are set, --disablerepo will be applied first')

def add_container_args(parser):
    parser.add_argument('-v', '--volume', action='append',
                        help=f'Volume mounts passed directly to {RUNNER} -v')
    parser.add_argument('--rm', action='store_true',
                        help='Destroy the container on exit')
    parser.add_argument('--syslog', action='store_true',
                        help='Enable syslog to host by mounting in /dev/log')
    parser.add_argument('--name', help='Assign a name to the container')
    parser.add_argument('--ulimit', action='append',
                        help=f'Ulimit options passed directly to {RUNNER} run')
    parser.add_argument('--platform', action='store',
                        help="Override the default platform for the build container. "
                        "Can notably be used to workaround podman bug #6185 fixed in v5.5.1.")
    parser.add_argument('--fail-on-error', action='store_true',
                        help='If container initialisation fails, exit rather than dropping the user '
                             'into a shell')
    parser.add_argument('--debug', action='store_true',
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
    parser_build.add_argument('build_local',
                              help="Root path where SPECS/ and SOURCES are available")
    parser_build.add_argument(
        '--define',
        help="Definitions to be passed to rpmbuild. Example: --define "
             "'xcp_ng_section extras', for building the 'extras' "
             "version of a package which exists in both 'base' and 'extras' versions.")
    parser_build.add_argument(
        '-o', '--output-dir',
        help="Directory where the RPMs, SRPMs and the build logs will appear. "
             "The directory is created if it doesn't exist")
    parser_build.add_argument(
        '--rpmbuild-opts', action='append',
        help="Pass additional option(s) to rpmbuild")
    parser_build.add_argument(
        '--rpmbuild-stage', action='store',
        help=f"Request given -bX stage rpmbuild, X in [{RPMBUILD_STAGES}]")
    add_container_args(parser_build)
    add_common_args(parser_build)

    # run -- execute commands inside a container
    parser_run = subparsers_container.add_parser(
        'run',
        help='Execute a command inside a container')
    parser_run.add_argument(
        'command', nargs=argparse.REMAINDER,
        help='Command to run inside the prepared container')
    add_container_args(parser_run)
    add_common_args(parser_run)

    # shell -- like run bash
    parser_shell = argparse.ArgumentParser()
    parser_shell = subparsers_container.add_parser(
        'shell',
        help='Drop a shell into the prepared container')
    add_container_args(parser_shell)
    add_common_args(parser_shell)

    return parser

def container(args):
    build = args.action == 'build'
    branch = args.branch or DEFAULT_BRANCH
    docker_arch = args.platform or ("linux/amd64/v2" if branch == "9.0" else "linux/amd64")

    docker_args = [RUNNER, "run", "-i", "-t",
                   "-u", "builder",
                   "--platform", docker_arch,
                   ]
    if is_podman(RUNNER):
        docker_args += ["--userns=keep-id", "--security-opt", "label=disable"]
    if args.rm:
        docker_args += ["--rm=true"]

    if hasattr(args, 'command') and args.command != []:
        docker_args += ["-e", "COMMAND=%s" % ' '.join(args.command)]
    if build:
        docker_args += ["-v", "%s:/home/builder/rpmbuild" %
                        os.path.abspath(args.build_local)]
        docker_args += ["-e", "BUILD_LOCAL=1"]
    if hasattr(args, 'define') and args.define:
        docker_args += ["-e", "RPMBUILD_DEFINE=%s" % args.define]
    if hasattr(args, 'rpmbuild_opts') and args.rpmbuild_opts:
        docker_args += ["-e", "RPMBUILD_OPTS=%s" % ' '.join(args.rpmbuild_opts)]
    if hasattr(args, 'rpmbuild_stage') and args.rpmbuild_stage:
        if args.rpmbuild_stage not in RPMBUILD_STAGES:
            parser.error(f"--rpmbuild-stage={args.rpmbuild_stage} not in '{RPMBUILD_STAGES}'")
        docker_args += ["-e", f"RPMBUILD_STAGE={args.rpmbuild_stage}"]
    if hasattr(args, 'output_dir') and args.output_dir:
        if not os.path.isdir(args.output_dir):
            print(f"{args.output_dir} is not a valid output directory.")
            sys.exit(1)
        docker_args += ["-v", "%s:/home/builder/output" %
                        os.path.abspath(args.output_dir)]
    if args.no_exit:
        docker_args += ["-e", "NO_EXIT=1"]
    if args.fail_on_error:
        docker_args += ["-e", "FAIL_ON_ERROR=1"]
    if args.debug:
        docker_args += ["-e", "SCRIPT_DEBUG=1"]
    if args.syslog:
        docker_args += ["-v", "/dev/log:/dev/log"]
    if args.name:
        docker_args += ["--name", args.name]
    if args.dir:
        for localdir in args.dir:
            if not os.path.isdir(localdir):
                print("Local directory argument is not a directory!")
                sys.exit(1)
            ext_path = os.path.abspath(localdir)
            int_path = os.path.basename(ext_path)
            docker_args += ["-v", "%s:/external/%s" % (ext_path, int_path)]
    if args.volume:
        for volume in args.volume:
            docker_args += ["-v", volume]
    if args.env:
        for env in args.env:
            docker_args += ["-e", env]
    if args.enablerepo:
        docker_args += ["-e", "ENABLEREPO=%s" % args.enablerepo]
    if args.disablerepo:
        docker_args += ["-e", "DISABLEREPO=%s" % args.disablerepo]
    ulimit_nofile = False
    if args.ulimit:
        for ulimit in args.ulimit:
            if ulimit.startswith('nofile='):
                ulimit_nofile = True
            docker_args += ["--ulimit", ulimit]
    if not ulimit_nofile:
        docker_args += ["--ulimit", "nofile=%s" % DEFAULT_ULIMIT_NOFILE]

    # exec "docker run"
    docker_args += ["%s:%s" % (CONTAINER_PREFIX, branch),
                    "/usr/local/bin/init-container.sh"]
    print("Launching docker with args %s" % docker_args, file=sys.stderr)
    return subprocess.call(docker_args)

def main():
    """ Main entry point. """
    parser = buildparser()

    args = parser.parse_args()

    return_code = args.func(args)

    sys.exit(return_code)

def build():
    bargs = [os.path.join(os.path.dirname(__file__), 'build.sh')] + sys.argv[1:]
    return_code = subprocess.call(bargs)
    sys.exit(return_code)

if __name__ == "__main__":
    main()
