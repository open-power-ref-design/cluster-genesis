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
import time
import json

from lib.inventory import Inventory
import lib.logger as logger
import lib.bmc as _bmc


def set_bootdev_clients(bootdev, persist=False, config_path=None, clients=None,
                        max_attempts=5):
    log = logger.getlogger()
    if config_path:
        inv = Inventory(cfg_file=config_path)

    if type(persist) is not bool:
        persist = (persist == 'True')

    def _get_cred_list(client_list=None):
        """Returns dict with values of tuples or list.  Each tuple/list
         has the credentials for a node (userid, password, bmc_type).
        If no client list is passed, all nodes are returned
        Args:
            client_list (list of str): each list item is an ipv4 address
        """
        cred_list = {}
        for index, hostname in enumerate(inv.yield_nodes_hostname()):
            ipv4 = inv.get_nodes_ipmi_ipaddr(0, index)
            if client_list and ipv4 not in client_list:
                continue
            userid = inv.get_nodes_ipmi_userid(index)
            password = inv.get_nodes_ipmi_password(index)
            bmc_type = inv.get_nodes_bmc_type(index)
            cred_list[ipv4] = (userid, password, bmc_type)
        return cred_list

    # if client list passed, it is assumed to be pxe addresses which
    # are used to look up the associated bmc addresses for the node.
    # otherwise use the entire ipmi inventory list. This allows a
    # subset of nodes to have their bootdev updated during install
    if isinstance(clients, list):
        # Get corresponing ipmi addresses
        _clients = []
        for index, hostname in enumerate(inv.yield_nodes_hostname()):
            ipv4_ipmi = inv.get_nodes_ipmi_ipaddr(0, index)
            ipv4_pxe = inv.get_nodes_pxe_ipaddr(0, index)
            if ipv4_pxe is not None and ipv4_pxe in clients:
                _clients.append(ipv4_ipmi)
    if not clients:
        log.debug('Retrieving IPMI address list from inventory')
        clients = inv.get_nodes_ipmi_ipaddr(0)
        _clients = clients[:]

    if isinstance(clients, list):
        log.debug('Retrieving client credentials from inventory')
        cred_list = _get_cred_list(_clients)
    else:
        # insure cred info in tuple
        cred_list = {}
        for client in clients:
            cred_list[client] = tuple(clients[client])

    clients_left = list(cred_list.keys())
    attempt = 0
    clients_left.sort()
    while clients_left and attempt < max_attempts:
        attempt += 1
        if attempt > 1:
            print('Retrying set bootdev. Attempt {} of {}'.format(attempt, max_attempts))
            print('Clients remaining: {}'.format(clients_left))
        clients_set = []
        bmc_dict = {}
        for client in clients_left:
            for i in range(3):
                tmp = _bmc.Bmc(client, *cred_list[client])
                if tmp.is_connected():
                    bmc_dict[client] = tmp
                    break
                else:
                    log.debug(f'Failed BMC login attempt {i + 1} BMC: {client}')
                    if i > 0:
                        log.info(f'BMC login attempt {i + 1} BMC: {client}')
                    if attempt == max_attempts and i == 2:
                        log.error(f'Failed BMC login. BMC: {client}')
                    time.sleep(1)
                    del tmp

        for client in clients_left:
            if client in bmc_dict:
                log.debug(f'Setting boot device to {bootdev}. '
                          f'Device: {client}')
                if bootdev in ('setup'):
                    status = bmc_dict[client].host_boot_mode(bootdev)
                else:
                    status = bmc_dict[client].host_boot_source(bootdev)
                    log.debug(f'status1 from set bootdev: {status}')

                if status:
                    if attempt in [2, 4, 8]:
                        print(f'{client} - Boot source: {status} Required source: '
                              f'{bootdev}')
                elif attempt == max_attempts:
                    log.error(f'Failed attempt {attempt} set boot source {bootdev} '
                              f'for node {client}')

        time.sleep(1 + attempt)

        for client in clients_left:
            if client in bmc_dict:
                if bootdev in ('setup'):
                    status = bmc_dict[client].host_boot_mode()
                else:
                    status = bmc_dict[client].host_boot_source()
                    log.debug(f'status2 from set bootdev: {status}')

                if status:
                    if attempt in [2, 4, 8]:
                        print(f'{client} - Boot source: {bootdev}')
                    if status == bootdev:
                        log.debug(f'Successfully set boot source to {bootdev} for '
                                  f'node {client}')
                        clients_set += [client]
                elif attempt == max_attempts:
                    log.error(f'Failed attempt {attempt} set host boot source to'
                              f'{bootdev} for node {client}')

                bmc_dict[client].logout()

        for client in clients_set:
            clients_left.remove(client)

        if attempt == max_attempts and clients_left:
            log.error('Failed to set boot device for some clients')
            log.debug(clients_left)

        del bmc_dict
    log.info('Set boot device to {} on {} of {} client devices.'
             .format(bootdev, len(cred_list) - len(clients_left),
                     len(cred_list)))


if __name__ == '__main__':
    """
    """
    logger.create()

    parser = argparse.ArgumentParser()
    parser.add_argument('bootdev', choices=['default', 'network', 'disk', 'setup'],
                        help='Boot device.  ie network or none...')

    parser.add_argument('config_path', default='',
                        help='Path to a Power-Up config file')

    parser.add_argument('clients', default='',
                        help='dict of ip addresses with credentials in list.\n'
                        'in json format: {"192.168.30.21": ["root", "0penBmc", "openbmc"]}')

    parser.add_argument('max_attempts', default=2, nargs='*',
                        help='Max number of login / power attempts')

    parser.add_argument('--persist', action='store_true', default=False,
                        help='Persist this boot device setting.')

    parser.add_argument('--print', '-p', dest='log_lvl_print',
                        help='print log level', default='info')

    parser.add_argument('--file', '-f', dest='log_lvl_file',
                        help='file log level', default='info')

    args = parser.parse_args()

    if args.log_lvl_print == 'debug':
        print(args)

    if args.clients:
        _clients = json.loads(args.clients)
    else:
        _clients = ''

    set_bootdev_clients(args.bootdev, args.persist, args.config_path,
                        _clients, max_attempts=args.max_attempts)
