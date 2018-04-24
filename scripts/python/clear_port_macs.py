#!/usr/bin/env python
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

from __future__ import nested_scopes, generators, division, absolute_import, \
    with_statement, print_function, unicode_literals

import argparse
import os.path
from lib.genesis import GEN_PATH
import sys

import lib.logger as logger
from lib.config import Config
from lib.switch import SwitchFactory


def main(config_path=None):
    cfg = Config(config_path)
    for sw_info in cfg.yield_sw_data_access_info():
        switch = SwitchFactory.factory(
            sw_info[1],
            sw_info[2],
            sw_info[3],
            sw_info[4],
            mode='active')
        switch.clear_mac_address_table()


if __name__ == '__main__':
    logger.create()

    parser = argparse.ArgumentParser()
    parser.add_argument('config_path', default='config.yml',
                        help='Config file path.  Absolute path or relative '
                        'to power-up/')
    args = parser.parse_args()

    if not os.path.isfile(args.config_path):
        args.config_path = GEN_PATH + args.config_path
        print('Using config path: {}'.format(args.config_path))
    if not os.path.isfile(args.config_path):
        sys.exit('{} does not exist'.format(args.config_path))

    main(args.config_path)
