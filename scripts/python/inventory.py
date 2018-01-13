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
import json
from itertools import chain

from lib.inventory import Inventory
from lib.config import Config
import lib.logger as logger
from lib import genesis

SSH_USER = 'root'
SSH_PRIVATE_KEY = genesis.get_ssh_private_key_file()
INVENTORY_INIT = {
    'all': {
        'vars': {}
    },
    'client-nodes': {
        'children': []
    },
    '_meta': {
        'hostvars': {}
    }
}


def generate_dynamic_inventory():
    inv = Inventory()
    cfg = Config()

    # Initialize the empty inventory
    dynamic_inventory = INVENTORY_INIT

    meta_hostvars = dynamic_inventory['_meta']['hostvars']

    # Add 'deployer' (container) to inventory
    meta_hostvars['deployer'] = {}
    for ip in chain(cfg.yield_depl_netw_mgmt_cont_ip(),
                    cfg.yield_depl_netw_client_cont_ip()):
        if ip is not None:
            meta_hostvars['deployer']['ansible_host'] = ip
            meta_hostvars['deployer']['ansible_user'] = SSH_USER
            meta_hostvars['deployer']['ansible_ssh_private_key_file'] = (
                SSH_PRIVATE_KEY)
            break

    # Add client nodes to inventory
    for index, hostname in enumerate(inv.yield_nodes_hostname()):
        # Add node to top-level group (node-template label & 'client-nodes')
        label = inv.get_nodes_label(index)
        if label not in dynamic_inventory:
            dynamic_inventory[label] = {'hosts': []}
            dynamic_inventory['client-nodes']['children'].append(label)
        dynamic_inventory[label]['hosts'].append(hostname)

        # Add node hostvars in '_meta' dictionary
        meta_hostvars[hostname] = inv.get_node_dict(index)
        meta_hostvars[hostname]['ansible_host'] = (
            inv.get_nodes_pxe_ipaddr(0, index))
        meta_hostvars[hostname]['ansible_user'] = SSH_USER
        meta_hostvars[hostname]['ansible_ssh_private_key_file'] = (
            SSH_PRIVATE_KEY)

        # Add node to any additional groups ('roles')
        roles = inv.get_nodes_roles(index)
        if roles is not None:
            for role in roles:
                if role not in dynamic_inventory:
                    dynamic_inventory[role] = {'hosts': []}
                dynamic_inventory[role]['hosts'].append(hostname)

    return dynamic_inventory


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--host', action='store')
    args = parser.parse_args()

    logger.create()
    LOG = logger.getlogger()

    if args.list:
        dynamic_inventory = generate_dynamic_inventory()
    else:
        dynamic_inventory = INVENTORY_INIT

    print(json.dumps(dynamic_inventory, indent=4))
