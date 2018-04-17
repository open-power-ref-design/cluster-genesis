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

from lib.inventory import Inventory
from lib.config import Config
from lib.exception import UserException
from lib.genesis import get_python_path


def _get_pxe_ips(inv):
    ip_list = ''
    for index, hostname in enumerate(inv.yield_nodes_hostname()):
        ip = inv.get_nodes_pxe_ipaddr(0, index)
        if ip is None:
            raise UserException('No PXE IP Address in Inventory for client '
                                '\'%s\'' % hostname)
        if ip_list != '':
            ip = ',' + ip
        ip_list += ip

    return ip_list


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--deployer', action='store_true')
    args = parser.parse_args()

    config_pointer_file = get_python_path() + '/config_pointer_file'
    if os.path.isfile(config_pointer_file):
        with open(config_pointer_file) as f:
            config_path = f.read()
    else:
        config_path = None

    inv = Inventory(config_path)
    cfg = Config(config_path)

    ip_list = _get_pxe_ips(inv)

    if args.deployer:
        ip_list += "," + cfg.get_depl_netw_cont_ip()

    print(ip_list)
