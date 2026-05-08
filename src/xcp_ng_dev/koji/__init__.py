from xcp_ng_dev.koji.build import koji_build, koji_build_init_parser

# from icecream import ic

def koji_init_parser(subparsers_env):
    parser_koji = subparsers_env.add_parser('koji', help="Koji related commands")
    parser_koji.set_defaults(func=koji)
    subparsers_koji = parser_koji.add_subparsers(
        dest='command', required=True,
        help="Koji sub-commands")
    koji_build_init_parser(subparsers_koji)

def koji(args):
    match args.command:
        case 'build':
            koji_build(args)
