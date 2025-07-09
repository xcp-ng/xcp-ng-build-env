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

CONTAINER_PREFIX = "xcp-ng/xcp-ng-build-env"
SRPMS_MOUNT_ROOT = "/tmp/docker-SRPMS"

DEFAULT_BRANCH = '8.3'
DEFAULT_ULIMIT_NOFILE = 2048

RUNNER = os.getenv("XCPNG_OCI_RUNNER")
if RUNNER is None:
    SUPPORTED_RUNNERS = "docker podman"
    for command in SUPPORTED_RUNNERS.split():
        if shutil.which(command):
            RUNNER = command
            break
    else:
        raise Exception(f"cannot find a supported runner: {SUPPORTED_RUNNERS}")

def make_mount_dir():
    """ Make a randomly-named directory under SRPMS_MOUNT_ROOT. """
    srpm_mount_dir = os.path.join(SRPMS_MOUNT_ROOT, str(uuid.uuid4()))
    try:
        os.makedirs(srpm_mount_dir)
    except OSError:
        pass
    return srpm_mount_dir


def copy_srpms(srpm_mount_dir, srpms):
    """ Copy each SRPM into the mount directory. """
    for srpm in srpms:
        srpm_name = os.path.basename(srpm)
        shutil.copyfile(srpm, os.path.join(srpm_mount_dir, srpm_name))

def is_podman(runner):
    if os.path.basename(runner) == "podman":
        return True
    if subprocess.getoutput(f"{runner} --version").startswith("podman "):
        return True
    return False

def main():
    """ Main entry point. """
    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--branch',
                        help='XCP-ng version: 7.6, %s, etc. If not set, '
                             'will default to %s.' % (DEFAULT_BRANCH, DEFAULT_BRANCH))
    parser.add_argument('-l', '--build-local',
                        help="Install dependencies for the spec file(s) found in the SPECS/ subdirectory "
                             "of the directory passed as parameter, then build the RPM(s). "
                             "Built RPMs and SRPMs will be in RPMS/ and SRPMS/ subdirectories. "
                             "Any preexisting BUILD, BUILDROOT, RPMS or SRPMS directories will be removed first. "
                             "If --output-dir is set, the RPMS and SRPMS directories will be copied to it "
                             "after the build.")
    parser.add_argument('--define',
                        help="Definitions to be passed to rpmbuild (if --build-local or --rebuild-srpm are "
                             "passed too). Example: --define 'xcp_ng_section extras', for building the 'extras' "
                             "version of a package which exists in both 'base' and 'extras' versions.")
    parser.add_argument('-r', '--rebuild-srpm',
                        help="Install dependencies for the SRPM passed as parameter, then build it. "
                             "Requires the --output-dir parameter to be set.")
    parser.add_argument('-o', '--output-dir',
                        help="Output directory for --rebuild-srpm and --build-local.")
    parser.add_argument('-n', '--no-exit', action='store_true',
                        help='After executing either an automated build or a custom command passed as parameter, '
                             'drop user into a shell')
    parser.add_argument('-s', '--srpm', action='append',
                        help='SRPMs for which dependencies will be installed')
    parser.add_argument('-d', '--dir', action='append',
                        help='Local dir to mount in the '
                        'image. Will be mounted at /external/<dirname>')
    parser.add_argument('-e', '--env', action='append',
                        help='Environment variables passed directly to '
                             'docker -e')
    parser.add_argument('-v', '--volume', action='append',
                        help='Volume mounts passed directly to docker -v')
    parser.add_argument('--rm', action='store_true',
                        help='Destroy the container on exit')
    parser.add_argument('--syslog', action='store_true',
                        help='Enable syslog to host by mounting in /dev/log')
    parser.add_argument('--name', help='Assign a name to the container')
    parser.add_argument('--ulimit', action='append',
                        help='Ulimit options passed directly to docker run')
    parser.add_argument('-a', '--enablerepo',
                        help='additional repositories to enable before installing build dependencies. '
                             'Same syntax as yum\'s --enablerepo parameter. Available additional repositories: '
                             'check files/xcp-ng.repo.*.x.in.')
    parser.add_argument('--disablerepo',
                        help='disable repositories. Same syntax as yum\'s --disablerepo parameter. '
                             'If both --enablerepo and --disablerepo are set, --disablerepo will be applied first')
    parser.add_argument('--fail-on-error', action='store_true',
                        help='If container initialisation fails, exit rather than dropping the user '
                             'into a command shell')
    parser.add_argument('command', nargs=argparse.REMAINDER,
                        help='Command to run inside the prepared container')

    args = parser.parse_args(sys.argv[1:])

    docker_args = [RUNNER, "run", "-i", "-t",
                   "-u", "builder",
                   "--platform", "linux/amd64",
                   ]
    if is_podman(RUNNER):
        docker_args += ["--userns=keep-id"]
    if args.rm:
        docker_args += ["--rm=true"]
    branch = args.branch or DEFAULT_BRANCH

    if args.command != []:
        docker_args += ["-e", "COMMAND=%s" % ' '.join(args.command)]
    if args.build_local:
        docker_args += ["-v", "%s:/home/builder/rpmbuild" %
                        os.path.abspath(args.build_local)]
        docker_args += ["-e", "BUILD_LOCAL=1"]
    if args.define:
        docker_args += ["-e", "RPMBUILD_DEFINE=%s" % args.define]
    if args.rebuild_srpm:
        if not os.path.isfile(args.rebuild_srpm) or not args.rebuild_srpm.endswith(".src.rpm"):
            parser.error("%s is not a valid source RPM." % args.rebuild_srpm)
        if not args.output_dir:
            parser.error(
                "Missing --output-dir parameter, required by --rebuild-srpm.")
        docker_args += ["-e", "REBUILD_SRPM=%s" %
                        os.path.basename(args.rebuild_srpm)]
        if args.srpm is None:
            args.srpm = []
        args.srpm.append(args.rebuild_srpm)
    if args.output_dir:
        if not os.path.isdir(args.output_dir):
            parser.error("%s is not a valid output directory." %
                         args.output_dir)
        docker_args += ["-v", "%s:/home/builder/output" %
                        os.path.abspath(args.output_dir)]
    if args.no_exit:
        docker_args += ["-e", "NO_EXIT=1"]
    if args.fail_on_error:
        docker_args += ["-e", "FAIL_ON_ERROR=1"]
    # Copy all the RPMs to the mount directory
    srpm_mount_dir = None
    if args.srpm:
        srpm_mount_dir = make_mount_dir()
        copy_srpms(srpm_mount_dir, args.srpm)
        docker_args += ["-v", "%s:/mnt/docker-SRPMS" % srpm_mount_dir]
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
    return_code = subprocess.call(docker_args)

    if srpm_mount_dir:
        print("Cleaning up temporary mount directory")
        shutil.rmtree(srpm_mount_dir)

    sys.exit(return_code)


if __name__ == "__main__":
    main()
