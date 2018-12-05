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
import sys
import os.path

from lib.inventory import Inventory
import lib.logger as logger
import lib.genesis as gen
import lib.utilities as util


def remove_client_host_keys(config_path=None):
    log = logger.getlogger()
    inv = Inventory(config_path)

    for ipaddr in inv.yield_nodes_pxe_ipaddr():
        log.info("Remove any stale ssh host keys for {}".format(ipaddr))
        if os.path.isfile(os.path.expanduser('~/.ssh/known_hosts')):
            util.bash_cmd("ssh-keygen -R {}".format(ipaddr))
        playbooks_known_hosts = (os.path.join(gen.get_playbooks_path(),
                                              'known_hosts'))
        if os.path.isfile(playbooks_known_hosts):
            util.bash_cmd("ssh-keygen -R {} -f {}"
                          .format(ipaddr, playbooks_known_hosts))


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
        args.config_path = gen.GEN_PATH + args.config_path
        print('Using config path: {}'.format(args.config_path))
    if not os.path.isfile(args.config_path):
        sys.exit('{} does not exist'.format(args.config_path))

    logger.create(args.log_lvl_print, args.log_lvl_file)
    remove_client_host_keys(args.config_path)
