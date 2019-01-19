#!/usr/bin/env python3
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
import json
import os.path

from lib.inventory import Inventory
from lib.config import Config
import lib.logger as logger
import lib.genesis as gen

SSH_USER = 'root'
SSH_PRIVATE_KEY = gen.get_ssh_private_key_file()
INVENTORY_INIT = {
    'all': {
        'vars': {
            'env_variables': {}
        },
        'hosts': ['deployer', 'localhost'],
        'children': ['client_nodes']
    },
    'client_nodes': {
        'children': [],
        'vars': {
        }
    },
    '_meta': {
        'hostvars': {}
    }
}


def generate_dynamic_inventory():
    config_pointer_file = gen.get_python_path() + '/config_pointer_file'
    if os.path.isfile(config_pointer_file):
        with open(config_pointer_file) as f:
            config_path = f.read()
    else:
        config_path = None

    inv = Inventory(config_path)
    cfg = Config(config_path)

    # Initialize the empty inventory
    dynamic_inventory = INVENTORY_INIT

    meta_hostvars = dynamic_inventory['_meta']['hostvars']

    # Add 'env_variables' to 'all' 'vars'
    dynamic_inventory['all']['vars']['env_variables'] = (
        cfg.get_globals_env_variables())

    # Add 'localhost' to inventory
    meta_hostvars['localhost'] = {}
    meta_hostvars['localhost']['ansible_connection'] = 'local'

    # Add 'deployer' (container) to inventory
    meta_hostvars['deployer'] = {}
    meta_hostvars['deployer']['ansible_host'] = cfg.get_depl_netw_cont_ip()
    meta_hostvars['deployer']['ansible_user'] = SSH_USER
    meta_hostvars['deployer']['ansible_ssh_private_key_file'] = SSH_PRIVATE_KEY

    # Add 'software_bootstrap' list to 'client_nodes' 'vars' if not empty
    software_bootstrap = cfg.get_software_bootstrap()
    if len(software_bootstrap) > 0:
        dynamic_inventory['client_nodes']['vars']['software_bootstrap'] = (
            software_bootstrap)

    # Add client nodes to inventory
    for index, hostname in enumerate(inv.yield_nodes_hostname()):
        # Add node to top-level group (node-template label & 'client-nodes')
        label = _sanitize(inv.get_nodes_label(index))
        if label not in dynamic_inventory:
            dynamic_inventory[label] = {'hosts': []}
            dynamic_inventory['client_nodes']['children'].append(label)
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
                _role = _sanitize(role)
                if _role not in dynamic_inventory:
                    dynamic_inventory[_role] = {'hosts': []}
                dynamic_inventory[_role]['hosts'].append(hostname)

    if 'solution_keys' not in dynamic_inventory:
        dynamic_inventory['solution_keys'] = {'hosts': []}

    if 'solution_inventory' not in dynamic_inventory:
        dynamic_inventory['solution_inventory'] = {'hosts': []}

    return dynamic_inventory


def _sanitize(str):
    return str.replace('-', '_')


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
