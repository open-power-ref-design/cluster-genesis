#!/usr/bin/env python3
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

import argparse
import os.path
import sys
from tabulate import tabulate

import lib.logger as logger
from lib.config import Config
from lib.inventory import Inventory
from lib.switch import SwitchFactory
from lib.genesis import GEN_PATH


def main(config_path=None):
    log = logger.getlogger()
    cfg = Config(config_path)
    inv = Inventory(config_path)

    macs = {}
    for sw_info in cfg.yield_sw_data_access_info():
        switch = SwitchFactory.factory(
            sw_info[1],
            sw_info[2],
            sw_info[3],
            sw_info[4],
            mode='active')
        port_to_macs = switch.show_mac_address_table(format='std')
        log.debug(
            (
                "Data switch port to MAC mapping - "
                "Switch: '{}', Class: '{}' - IP: '{}' - {}").format(
                    sw_info[0], sw_info[1], sw_info[2], port_to_macs))
        macs.update({sw_info[0]: port_to_macs})
    inv.add_macs_data(macs)

    if not inv.check_data_interfaces_macs():
        _print_data_macs(inv)


def _print_data_macs(inv):
    blue = '\033[94m'
    endc = '\033[0m'
    header = ['Switch', 'Port', 'Device', 'MAC']
    for node, info in inv.get_data_interfaces().items():
        print(f'\n{blue}Client Node: {node}:{endc}')
        print(tabulate(info, header))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('config_path', default='config.yml',
                        help='Config file path.  Absolute path or relative '
                        'to power-up/')

    parser.add_argument('--print', '-p', dest='log_lvl_print',
                        help='print log level', default='info')

    parser.add_argument('--file', '-f', dest='log_lvl_file',
                        help='file log level', default='info')

    args = parser.parse_args()

    if not os.path.isfile(args.config_path):
        args.config_path = GEN_PATH + args.config_path
        print('Using config path: {}'.format(args.config_path))
    if not os.path.isfile(args.config_path):
        sys.exit('{} does not exist'.format(args.config_path))

    logger.create(args.log_lvl_print, args.log_lvl_file)
    main(args.config_path)
