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
import time
from pyghmi.ipmi import command as ipmi_command
from pyghmi import exceptions as pyghmi_exception

from lib.inventory import Inventory
import lib.logger as logger


def ipmi_set_bootdev(bootdev, persist=False, client_list=None):
    log = logger.getlogger()
    inv = Inventory()

    if type(persist) is not bool:
        persist = (persist == 'True')

    # if client list passed, then use the passed client list,
    # otherwise use the entire inventory list. This allows a
    # subset of nodes to have their bootdev updated during install
    if not client_list:
        client_list = inv.get_nodes_pxe_ipaddr(0)
    max_attempts = 5
    attempt = 0
    clients_left = client_list
    clients_left.sort()
    while clients_left and attempt < max_attempts:
        nodes = {}
        attempt += 1
        if attempt > 1:
            print('Retrying set bootdev. Attempt {} of {}'.format(attempt, max_attempts))
            print('Clients remaining: {}'.format(clients_left))
        clients_set = []
        bmc_dict = {}
        for index, hostname in enumerate(inv.yield_nodes_hostname()):
            ipv4 = inv.get_nodes_ipmi_ipaddr(0, index)
            ipv4_pxe = inv.get_nodes_pxe_ipaddr(0, index)
            if ipv4_pxe not in clients_left:
                continue
            rack_id = inv.get_nodes_rack_id(index)
            userid = inv.get_nodes_ipmi_userid(index)
            password = inv.get_nodes_ipmi_password(index)
            nodes[ipv4_pxe] = [rack_id, ipv4]
            for i in range(2):
                try:
                    bmc_dict[ipv4_pxe] = ipmi_command.Command(
                        bmc=ipv4,
                        userid=userid,
                        password=password)
                except pyghmi_exception.IpmiException as error:
                    log.error('IPMI login try {}, address {} - {}'.
                              format(i, ipv4, error.message))
                    time.sleep(1)
                else:
                    break

        for client in clients_left:
            if client in bmc_dict:
                try:
                    status = bmc_dict[client].set_bootdev(bootdev, persist)
                    if attempt in [2, 4, 8]:
                        print('{} - {}'.format(client, status))
                except pyghmi_exception.IpmiException as error:
                    msg = ('set_bootdev failed (device=%s persist=%s), '
                           'Rack: %s - IP: %s, %s' %
                           (bootdev, persist, nodes[client][0],
                            nodes[client][1], str(error)))
                    log.warning(msg)
                finally:
                    if 'error' in status:
                        log.error(status)

        time.sleep(2)

        for client in clients_left:
            if client in bmc_dict:
                try:
                    status = bmc_dict[client].get_bootdev()
                    if attempt in [2, 4, 8]:
                        print('{} - {}'.format(client, status))
                except pyghmi_exception.IpmiException as error:
                    msg = (
                        'get_bootdev failed - '
                        'Rack: %s - IP: %s, %s' %
                        (rack_id, ipv4, str(error)))
                    log.error(msg)
                else:
                    if status['bootdev'] == bootdev and str(status['persistent']) \
                            == str(persist):
                        log.debug('set_bootdev successful (device=%s persist=%s) - '
                                  'Rack: %s - IP: %s' %
                                  (bootdev, persist, nodes[client][0], nodes[client][1]))
                        clients_set += [client]
                finally:
                    if 'error' in status:
                        log.error(status)
                bmc_dict[client].ipmi_session.logout()

        for client in clients_set:
            clients_left.remove(client)
            if not clients_left:
                print('Successfully set {} client boot devices to {}'
                      .format(len(client_list), bootdev))
        if attempt == max_attempts and clients_left:
            log.error('Failed to set boot device for some clients')
            log.debug(clients_left)

        del bmc_dict


if __name__ == '__main__':
    """
    Arg1: boot device
    Arg2: persistence (boolean)
    Arg3: client list (specify None to use the entire client list)
    """
    logger.create()

    parser = argparse.ArgumentParser()
    parser.add_argument('boot_dev', default='none', nargs='?',
                        help='Boot device.  ie network or none...')

    parser.add_argument('--persist', action='store_true',
                        help='Persist this boot device setting.')

    parser.add_argument('client_list', default='', nargs='*',
                        help='List of ip addresses.')

    parser.add_argument('--print', '-p', dest='log_lvl_print',
                        help='print log level', default='info')

    parser.add_argument('--file', '-f', dest='log_lvl_file',
                        help='file log level', default='info')

    args = parser.parse_args()

    if args.log_lvl_print == 'debug':
        print(args)

    ipmi_set_bootdev(args.bootdev, args.persist, args.client_list)
