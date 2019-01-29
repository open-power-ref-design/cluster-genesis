"""Cluster Genesis 'gen' command argument parser"""

# Copyright 2018 IBM Corp.
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

from argparse import ArgumentParser, RawTextHelpFormatter

PROJECT = 'Cluster Genesis'
DEPLOYER_CMD = 'deployer'
SWITCHES_CMD = 'switches'
ALL_CMD = 'all'
DEPLOYER_DESC = 'Teardown {} deployer elements'.format(PROJECT)
SWITCHES_DESC = 'Deconfigure switches'
ALL_DESC = 'Teardown all deployer elements and switches'
DEPLOYER_NETWORKS_HELP = ('Deletes {} created interfaces and bridges. \nRemoves {} '
                          'added addresses from external interfaces.'.format(
                              PROJECT, PROJECT))
CFG_FILE_HELP = 'Specify relative to the power-up directory or provide full path.'
GITHUB = 'https://github.com/open-power-ref-design-toolkit/cluster-genesis'
EPILOG = 'home page:\n  %s' % GITHUB
LOG_LEVEL_CHOICES = ['nolog', 'debug', 'info', 'warning', 'error', 'critical']
LOG_LEVEL_FILE = ['debug']
LOG_LEVEL_PRINT = ['info']


def get_args(parser_args=False):
    """Get 'teardown' command arguments"""

    parser = ArgumentParser(
        description=PROJECT,
        epilog=EPILOG,
        formatter_class=RawTextHelpFormatter,
        prog='teardown')
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

    # Subparsers
    parser_deployer = subparsers.add_parser(
        DEPLOYER_CMD,
        description='%s - %s' % (PROJECT, DEPLOYER_DESC),
        help=DEPLOYER_DESC,
        epilog=EPILOG,
        parents=[common_parser],
        formatter_class=RawTextHelpFormatter)

    parser_switches = subparsers.add_parser(
        SWITCHES_CMD,
        description='%s - %s' % (PROJECT, SWITCHES_DESC),
        help=SWITCHES_DESC,
        epilog=EPILOG,
        parents=[common_parser],
        formatter_class=RawTextHelpFormatter)

    parser_all = subparsers.add_parser(
        ALL_CMD,
        description='%s - %s' % (PROJECT, SWITCHES_DESC),
        help=ALL_DESC,
        epilog=EPILOG,
        parents=[common_parser],
        formatter_class=RawTextHelpFormatter)

    # 'deployer' subcommand arguments
    parser_deployer.set_defaults(
        deployer=True)

    parser_deployer.add_argument(
        '--container',
        action='store_true',
        help=f'Destroy the {PROJECT} container.')

    parser_deployer.add_argument(
        '--gateway',
        action='store_true',
        help='Delete deployer network gateway and NAT record')

    parser_deployer.add_argument(
        '--networks',
        action='store_true',
        help=DEPLOYER_NETWORKS_HELP)

    parser_deployer.add_argument(
        '-a', '--all',
        action='store_true',
        help='Apply all actions')

    parser_deployer.add_argument(
        'config_file_name',
        nargs='?',
        default='config.yml',
        metavar='CONFIG-FILE-NAME',
        help=CFG_FILE_HELP)

    # 'switches' subcommand arguments
    parser_switches.set_defaults(
        switches=True)

    parser_switches.add_argument(
        '--data',
        action='store_true',
        help='Deconfigure data switches.  Deconfiguration is driven by the '
        'config.yml file.')

    parser_switches.add_argument(
        '--mgmt',
        action='store_true',
        help='Deconfigure Mgmt switches.  Deconfiguration is driven by the '
        'config.yml file.')

    parser_switches.add_argument(
        '-a', '--all',
        action='store_true',
        help='Deconfigure all switches.')

    parser_switches.add_argument(
        'config_file_name',
        nargs='?',
        default='config.yml',
        metavar='CONFIG-FILE-NAME',
        help=CFG_FILE_HELP)

    # 'all' subcommand arguments
    parser_all.set_defaults(
        all=True)

    parser_all.add_argument(
        'config_file_name',
        nargs='?',
        default='config.yml',
        metavar='CONFIG-FILE-NAME',
        help=CFG_FILE_HELP)

    if parser_args:
        return (parser, parser_deployer, parser_switches, parser_all)
    return parser


def _check_deployer(args, subparser):
    if not args.networks and not args.gateway and \
            not args.all and not args.container:
        subparser.error(
            'one of the arguments --networks --container'
            ' --gateway -a/--all is required')


def _check_switches(args, subparser):
    if not args.data and not args.mgmt and not args.all:
        subparser.error(
            'one of the arguments --data --mgmt'
            ' -a/--all is required')


def get_parsed_args():
    """Get parsed 'gen' command arguments"""

    parser, parser_deployer, parser_switches, parser_all = get_args(parser_args=True)
    args = parser.parse_args()

    # Check arguments
    if hasattr(args, 'deployer'):
        _check_deployer(args, parser_deployer)

    if hasattr(args, 'switches'):
        _check_switches(args, parser_switches)

    return args
