#!/usr/bin/env python3
"""Create inventory"""

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

import argparse
import os.path
import sys

import lib.logger as logger
from lib.inv_items import InventoryNodes, InventorySwitches
from lib.genesis import GEN_PATH


class InventoryCreate(object):
    """Create inventory"""

    def __init__(self, config_path=None):
        self.config_path = config_path

    def create(self):
        """Create inventory"""

        nodes = InventoryNodes(cfg_path=self.config_path)
        nodes.create_nodes()

        switches = InventorySwitches(cfg_path=self.config_path)
        switches.create_switches()


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

    INV = InventoryCreate(args.config_path)
    INV.create()
