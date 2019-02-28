"""POWER-Up 'pup.py' command argument parser"""

# Copyright 2019 IBM Corp.
#
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from enum import Enum
from argparse import ArgumentParser, RawTextHelpFormatter

PROJECT = 'POWER-Up'
SETUP_CMD = 'setup'
CONFIG_CMD = 'config'
VALIDATE_CMD = 'validate'
DEPLOY_CMD = 'deploy'
SOFTWARE_CMD = 'software'
OSINSTALL_CMD = 'osinstall'
UTIL_CMD = 'utils'
POST_DEPLOY_CMD = 'post-deploy'
SETUP_DESC = 'Setup deployment environment (requires root privileges)'
CONFIG_DESC = 'Configure deployment environment'
VALIDATE_DESC = 'Validate deployment environment'
DEPLOY_DESC = 'Deploy cluster'
POST_DEPLOY_DESC = 'Configure cluster nodes and data switches'
UTIL_DESC = 'Execute utility functions'
SOFTWARE_DESC = 'Install software stack on client nodes'
OSINSTALL_DESC = 'Install an operating system on client nodes'
GITHUB = 'https://github.com/open-power-ref-design-toolkit/power-up'
EPILOG = 'home page:\n  %s' % GITHUB
ABSENT = '\u009fabsent\u009c'
LOG_LEVEL_CHOICES = ['nolog', 'debug', 'info', 'warning', 'error', 'critical']
LOG_LEVEL_FILE = ['debug']
LOG_LEVEL_PRINT = ['info']


class Cmd(Enum):
    SETUP = SETUP_CMD
    CONFIG = CONFIG_CMD
    VALIDATE = VALIDATE_CMD
    DEPLOY = DEPLOY_CMD
    POST_DEPLOY = POST_DEPLOY_CMD
    SOFTWARE = SOFTWARE_CMD
    OSINSTALL = OSINSTALL_CMD
    UTIL = UTIL_CMD


def get_args(parser_args=False):
    """Get 'pup' command arguments"""

    parser = ArgumentParser(
        description=PROJECT,
        epilog=EPILOG,
        formatter_class=RawTextHelpFormatter,
        prog='pup')
    subparsers = parser.add_subparsers()
    common_parser = ArgumentParser(add_help=False)

    # Common arguments
    common_parser.add_argument(
        '-f', '--log-level-file',
        nargs=1,
        default=LOG_LEVEL_FILE,
        choices=LOG_LEVEL_CHOICES,
        metavar='LOG-LEVEL',
        help='Add log to file\nChoices: {}\nDefault: {}'.format(
            ','.join(LOG_LEVEL_CHOICES), LOG_LEVEL_FILE[0]))

    common_parser.add_argument(
        '-p', '--log-level-print',
        nargs=1,
        default=LOG_LEVEL_PRINT,
        choices=LOG_LEVEL_CHOICES,
        metavar='LOG-LEVEL',
        help='Add log to stdout/stderr\nChoices: {}\nDefault: {}'.format(
            ','.join(LOG_LEVEL_CHOICES), LOG_LEVEL_PRINT[0]))

    common_parser.add_argument(
        '--extra-vars',
        nargs=1,
        metavar='EXTRA-VARS',
        help='Provide extra variables to PowerUp')

    # Subparsers
    parser_setup = subparsers.add_parser(
        SETUP_CMD,
        description='%s - %s' % (PROJECT, SETUP_DESC),
        help=SETUP_DESC,
        epilog=EPILOG,
        parents=[common_parser],
        formatter_class=RawTextHelpFormatter)

    parser_config = subparsers.add_parser(
        CONFIG_CMD,
        description='%s - %s' % (PROJECT, CONFIG_DESC),
        help=CONFIG_DESC,
        epilog=EPILOG,
        parents=[common_parser],
        formatter_class=RawTextHelpFormatter)

    parser_validate = subparsers.add_parser(
        VALIDATE_CMD,
        description='%s - %s' % (PROJECT, VALIDATE_DESC),
        help=VALIDATE_DESC,
        epilog=EPILOG,
        parents=[common_parser],
        formatter_class=RawTextHelpFormatter)

    parser_deploy = subparsers.add_parser(
        DEPLOY_CMD,
        description='%s - %s' % (PROJECT, DEPLOY_DESC),
        help=DEPLOY_DESC,
        epilog=EPILOG,
        parents=[common_parser],
        formatter_class=RawTextHelpFormatter)

    parser_post_deploy = subparsers.add_parser(
        POST_DEPLOY_CMD,
        description='%s - %s' % (PROJECT, POST_DEPLOY_DESC),
        help=POST_DEPLOY_DESC,
        epilog=EPILOG,
        parents=[common_parser],
        formatter_class=RawTextHelpFormatter)

    parser_software = subparsers.add_parser(
        SOFTWARE_CMD,
        description='%s - %s' % (PROJECT, SOFTWARE_DESC),
        help=SOFTWARE_DESC,
        epilog=EPILOG,
        parents=[common_parser],
        formatter_class=RawTextHelpFormatter)

    parser_osinstall = subparsers.add_parser(
        OSINSTALL_CMD,
        description='%s - %s' % (PROJECT, OSINSTALL_DESC),
        help=OSINSTALL_DESC,
        epilog=EPILOG,
        parents=[common_parser],
        formatter_class=RawTextHelpFormatter)

    parser_utils = subparsers.add_parser(
        UTIL_CMD,
        description='%s - %s' % (PROJECT, UTIL_DESC),
        help=UTIL_DESC,
        epilog=EPILOG,
        parents=[common_parser],
        formatter_class=RawTextHelpFormatter)

    # 'setup' subcommand arguments
    parser_setup.set_defaults(
        setup=True)

    parser_setup.add_argument(
        '--networks',
        action='store_true',
        help='Create deployer interfaces, vlans and bridges')

    parser_setup.add_argument(
        '--gateway',
        action='store_true',
        help='Configure PXE network gateway and NAT record')

    parser_setup.add_argument(
        'config_file_name',
        nargs='?',
        default='config.yml',
        metavar='CONFIG-FILE-NAME',
        help='Config file name. Specify relative to the power-up directory.')

    parser_setup.add_argument(
        '-a', '--all',
        action='store_true',
        help='Run all cluster setup steps')

    # 'config' subcommand arguments
    parser_config.set_defaults(
        config=True)

    parser_config.add_argument(
        '--mgmt-switches',
        action='store_true',
        help='Configure the cluster management switches')

    parser_config.add_argument(
        '--data-switches',
        action='store_true',
        help='Configure the cluster data switches')

    parser_config.add_argument(
        '--create-container',
        action='store_true',
        help='Create deployer container')

    parser_config.add_argument(
        'config_file_name',
        nargs='?',
        default='config.yml',
        metavar='CONFIG-FILE-NAME',
        help='Config file name. Specify relative to the power-up directory.')

    # 'validate' subcommand arguments
    parser_validate.set_defaults(
        validate=True)

    parser_validate.add_argument(
        '--config-file',
        action='store_true',
        help='Schema and logic config file validation')

    parser_validate.add_argument(
        'config_file_name',
        nargs='?',
        default='config.yml',
        metavar='CONFIG-FILE-NAME',
        help='Config file name. Specify relative to the power-up directory.')

    parser_validate.add_argument(
        '--cluster-hardware',
        action='store_true',
        help='Cluster hardware discovery and validation')

    # 'deploy' subcommand arguments
    parser_deploy.set_defaults(
        deploy=True)

    parser_deploy.add_argument(
        '--create-inventory',
        action='store_true',
        help='Create inventory')

    parser_deploy.add_argument(
        '--install-cobbler',
        action='store_true',
        help='Install Cobbler')

    parser_deploy.add_argument(
        '--download-os-images',
        action='store_true',
        help='Download OS images')

    parser_deploy.add_argument(
        '--inv-add-ports-ipmi',
        action='store_true',
        help='Discover and add IPMI ports to inventory')

    parser_deploy.add_argument(
        '--inv-add-ports-pxe',
        action='store_true',
        help='Discover and add PXE ports to inventory')

    parser_deploy.add_argument(
        '--reserve-ipmi-pxe-ips',
        action='store_true',
        help='Configure DHCP IP reservations for IPMI and PXE interfaces')

    parser_deploy.add_argument(
        '--add-cobbler-distros',
        action='store_true',
        help='Add Cobbler distros and profiles')

    parser_deploy.add_argument(
        '--add-cobbler-systems',
        action='store_true',
        help='Add Cobbler systems')

    parser_deploy.add_argument(
        '--install-client-os',
        action='store_true',
        help='Initiate client OS installation(s)')

    parser_deploy.add_argument(
        'config_file_name',
        nargs='?',
        default='config.yml',
        metavar='CONFIG-FILE-NAME',
        help='Config file name. Specify relative to the power-up directory.')

    parser_deploy.add_argument(
        '-a', '--all',
        action='store_true',
        help='Run all cluster deployment steps')

    # 'post-deploy' subcommand arguments
    parser_post_deploy.set_defaults(post_deploy=True)

    parser_post_deploy.add_argument(
        '--ssh-keyscan',
        action='store_true',
        help='Scan SSH keys')

    parser_post_deploy.add_argument(
        '--gather-mac-addr',
        action='store_true',
        help='Gather MAC addresses from switches and update inventory')

    parser_post_deploy.add_argument(
        '--lookup-interface-names',
        action='store_true',
        help=('Lookup OS assigned name of all interfaces configured with '
              '\'rename: false\' and update inventory'))

    parser_post_deploy.add_argument(
        '--config-client-os',
        action='store_true',
        help='Configure cluster nodes client OS')

    parser_post_deploy.add_argument(
        'config_file_name',
        nargs='?',
        default='config.yml',
        metavar='CONFIG-FILE-NAME',
        help='Config file name. Config files need to reside in the power-up directory.')

    parser_post_deploy.add_argument(
        '-a', '--all',
        action='store_true',
        help='Run all cluster post deployment steps')

    # 'osinstall' subcommand arguments
    parser_osinstall.set_defaults(osinstall=True)

    parser_osinstall.add_argument(
        '--setup-interfaces',
        action='store_true',
        help='Create deployer interfaces.')

    parser_osinstall.add_argument(
        '--gateway',
        action='store_true',
        help='Configure PXE network gateway and NAT record')

    parser_osinstall.add_argument(
        'config_file_name',
        nargs='?',
        default='profile.yml',
        metavar='CONFIG-FILE-NAME',
        help='OS installation profile file name. Specify relative to the power-up directory.')

    # 'software' subcommand arguments
    parser_software.set_defaults(software=True)

    parser_software.add_argument(
        'name', nargs='?',
        help='Software module name')

    parser_software.add_argument(
        '--prep',
        default=ABSENT,
        action='store_true',
        help='Download software packages and pre-requisite repositories and sets\n'
             'up this node as the server for the software')

    parser_software.add_argument(
        '--init-clients',
        default=ABSENT,
        action='store_true',
        help='Initialize the cluster clients to access the POWER-Up software server')

    parser_software.add_argument(
        '--install',
        default=ABSENT,
        action='store_true',
        help='Install the specified software to cluster nodes')

    parser_software.add_argument(
        '--README',
        default=ABSENT,
        action='store_true',
        help='Display software install module help')

    parser_software.add_argument(
        '--status',
        default=ABSENT,
        action='store_true',
        help='Display software install module preparation status')

    parser_software.add_argument(
        '--eval',
        default=False,
        action='store_true',
        help='Install the evaluation version of software if available')

    parser_software.add_argument(
        '--non-interactive',
        default=False,
        action='store_true',
        help='Runs the software phase with minimal user interaction')

    parser_software.add_argument(
        '-a', '--all',
        action='store_true',
        help='Run all software prep and install steps')

    parser_software.add_argument(
        '--arch',
        default="ppc64le",
        choices=['ppc64le', 'x86_64'],
        help='Runs the software phase with specified architecture')

    parser_software.add_argument(
        '--step',
        default=None,
        nargs='+',
        choices=['ibmai_repo', 'cuda_drv_repo',
                 'wmla_license', 'spectrum_dli',
                 'dependency_repo', 'conda_content_repo',
                 'conda_free_repo', 'conda_main_repo',
                 'conda_forge_repo', 'pypi_repo',
                 'epel_repo', 'custom_repo'],
        help='Runs the software phase with specified step')

    parser_software.add_argument(
        '--get_state',
        default=None,
        action="store_true",
        help='Get state of prep phase')
    # 'utils' subcommand arguments
    parser_utils.set_defaults(utils=True)
    parser_utils.add_argument(
        '--scan-pxe-network',
        action='store_true',
        help='Ping all addresses in PXE subnet')

    parser_utils.add_argument(
        '--scan-ipmi-network',
        action='store_true',
        help='Ping all addresses in IPMI subnet')

    parser_utils.add_argument(
        'config_file_name',
        nargs='?',
        default='config.yml',
        metavar='CONFIG-FILE-NAME',
        help='Config file name. Specify relative to the power-up directory.')

    if parser_args:
        return (parser, parser_setup, parser_config, parser_validate,
                parser_deploy, parser_post_deploy, parser_software,
                parser_osinstall, parser_utils)

    return parser


def _check_setup(args, subparser):
    if not args.bridges and not args.gateway and not args.all:
        subparser.error(
            'one of the arguments --networks --gateway -a/--all is required')


def _check_config(args, subparser):
    if not args.mgmt_switches and args.data_switches == ABSENT and \
            args.create_container == ABSENT:
        subparser.error(
            'one of the arguments --mgmt-switches --data-switches'
            ' --create-container is required')


def _check_validate(args, subparser):
    if args.config_file == ABSENT and args.cluster_hardware == ABSENT:
        subparser.error(
            'one of the arguments --config-file --cluster-hardware is'
            ' required')


def _check_deploy(args, subparser):
    if (not args.create_inventory and
            args.install_cobbler == ABSENT and
            args.download_os_images == ABSENT and
            args.inv_add_ports_ipmi == ABSENT and
            args.inv_add_ports_pxe == ABSENT and
            args.reserve_ipmi_pxe_ips == ABSENT and
            args.add_cobbler_distros == ABSENT and
            args.add_cobbler_systems == ABSENT and
            args.install_client_os == ABSENT and
            args.ssh_keyscan == ABSENT and
            args.gather_mac_addr == ABSENT and
            args.config_client_os == ABSENT and
            args.all == ABSENT):
        subparser.error(
            'one of the arguments --create-inventory --install-cobbler'
            ' --inv-add-ports-pxe --inv-add-ports-ipmi --download-os-images'
            ' --reserve-ipmi-pxe-ips --add-cobbler-distros'
            ' --add-cobbler-systems --install-client-os -a/--all is required')


def _check_post_deploy(args, subparser):
    if (args.ssh_keyscan == ABSENT and args.gather_mac_addr == ABSENT and
            args.config_client_os == ABSENT and args.data_switches == ABSENT and
            args.all == ABSENT):
        subparser.error(
            'one of the arguments --ssh-keyscan --gather-mac-addr'
            '--config-client-os -a/--all is required')


def _check_osinstall(args, subparser):
    if not (args.networks or args.gateway):
        subparser.error('one of the arguments --setup-interfaces --gateway '
                        'is required. Optionally a profile file name may be '
                        'included')


def _check_software(args, subparser):
    if not args.prep and not args.install and not args.name and not args.README \
            and not args.init_clients and not args.all:
        subparser.error('one of the arguments --about --prep --status --eval'
                        '--init-clients --install --non-interactive -a/--all '
                        'plus a software installer module name is required')


def _check_utils(args, subparser):
    if not args.scan_pxe_network and not args.scan_ipmi_network:
        subparser.error(
            'one of the arguments --scan-pxe-network --scan-ipmi-network is required')


def is_arg_present(arg):
    if arg == ABSENT or arg is False:
        return False
    return True


def get_parsed_args():
    """Get parsed 'pup' command arguments"""

    parser, parser_setup, parser_config, parser_validate, parser_deploy, \
        parser_post_deploy, parser_osinstall, parser_software, parser_utils = \
        get_args(parser_args=True)
    args = parser.parse_args()

    # Check arguments
    try:
        if args.setup:
            _check_setup(args, parser_setup)
    except AttributeError:
        pass
    try:
        if args.config:
            _check_config(args, parser_config)
    except AttributeError:
        pass
    try:
        if args.validate:
            _check_validate(args, parser_validate)
    except AttributeError:
        pass
    try:
        if args.deploy:
            _check_deploy(args, parser_deploy)
    except AttributeError:
        pass
    try:
        if args.post_deploy:
            _check_post_deploy(args, parser_post_deploy)
    except AttributeError:
        pass
    try:
        if args.software:
            _check_software(args, parser_software)
    except AttributeError:
        pass
    try:
        if args.osinstall:
            _check_osinstall(args, parser_osinstall)
    except AttributeError:
        pass
    try:
        if args.utils:
            _check_utils(args, parser_utils)
    except AttributeError:
        pass

    return args
