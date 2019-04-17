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

import json
import argparse
import time

from lib.inventory import Inventory
import lib.logger as logger
import lib.bmc as _bmc


def set_power_clients(state, config_path=None, clients=None, max_attempts=5,
                      wait=6):
    """Set power on or off for multiple clients. If a list of ip addresses
    are given or no clients given then the credentials are looked up in an
    inventory file. If clients is a dictionary, then the credentials are
    taken from the dictionary values.

    Args:
        state (str) : 'on' or 'off'
        config_path (str): path to a config file
        clients (dict or list of str): list of IP addresses or
        dict of ip addresses with values of credentials as tuple
        ie {'192.168.1.2': ('user', 'password', 'bmc_type')}
    """
    log = logger.getlogger()
    if config_path:
        inv = Inventory(config_path)
    wait = float(wait)
    max_attempts = int(max_attempts)

    def _get_cred_list(client_list=None):
        """Returns dict with values of tuples.  Each tuple has the credentials
        for a node (userid, password, bmc_type). If no client list
        is passed, all nodes are returned
        Args:
            client_list (list of str): each list item is an ipv4 address
        """
        cred_list = {}
        for index, hostname in enumerate(inv.yield_nodes_hostname()):
            ipv4 = inv.get_nodes_ipmi_ipaddr(0, index)
            if client_list and ipv4 not in client_list:
                continue
            # rack_id = inv.get_nodes_rack_id(index)
            userid = inv.get_nodes_ipmi_userid(index)
            password = inv.get_nodes_ipmi_password(index)
            bmc_type = inv.get_nodes_bmc_type(index)
            cred_list[ipv4] = (userid, password, bmc_type)
        return cred_list

    if isinstance(clients, list) or not clients:
        log.debug('Retrieving IPMI address list from inventory')
        cred_list = _get_cred_list(clients)
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
            print('Retrying set power {}. Attempt {} of {}'
                  .format(state, attempt, max_attempts))
            print('Clients remaining: {}'.format(clients_left))
        clients_set = []
        bmc_dict = {}
        for client in clients_left:
            for i in range(3):
                log.debug(f'Attempting login to BMC: {client}')
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
                log.debug(f'Setting power state to {state}. '
                          f'Device: {client}')
                status = bmc_dict[client].chassis_power(state, wait)
                if status:
                    if attempt in [2, 4, 8]:
                        print(f'{client} - Power status: {status}')
                    # Allow delay between turn on to limit power surge
                    if state == 'on':
                        time.sleep(0.5)
                elif attempt == max_attempts:
                    log.error(f'Failed attempt {attempt} set power {state} '
                              f'for node {client}')

        time.sleep(wait + attempt)

        for client in clients_left:
            if client in bmc_dict:
                status = bmc_dict[client].chassis_power('status')
                if status:
                    if attempt in [2, 4, 8]:
                        print(f'{client} - Power status: {status}, '
                              f'required state: {state}')
                    if status == state:
                        log.debug(f'Successfully set power {state} for node {client}')
                        clients_set += [client]
                elif attempt == max_attempts:
                    log.error(f'Failed attempt {attempt} get power {state} '
                              f'for node {client}')

        for client in clients_set:
            clients_left.remove(client)

        if attempt == max_attempts and clients_left:
            log.error(f'Failed to power {state} some clients')
            log.error(f'Clients left: {clients_left}')

        del bmc_dict

    log.info('Powered {} {} of {} client devices.'
             .format(state, len(cred_list) - len(clients_left),
                     len(cred_list)))

    if state == 'off':
        print('Pausing 60 sec for client power off')
        time.sleep(60)

    if clients_left:
        return False
    return True


if __name__ == '__main__':
    """
    """
    logger.create()
    parser = argparse.ArgumentParser()
    parser.add_argument('state', default='none',
                        help='Boot device.  ie network or none...')

    parser.add_argument('config_path',
                        help='Config file path.')

    parser.add_argument('clients', default='',
                        help='dict of ip addresses with credentials in list.\n'
                        'in json format: {"192.168.30.21": ["root", "0penBmc", "openbmc"]}')

    parser.add_argument('max_attempts', default='2', nargs='*',
                        help='Max number of login / power attempts')

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

    set_power_clients(args.state, args.config_path, _clients,
                      max_attempts=args.max_attempts)
