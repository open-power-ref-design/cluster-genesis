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


def ipmi_set_power(state, client_list=None, max_attempts=5, wait=6):
    """Set power on or off
    Args:
        state (str) : 'on' or 'off'
        client_list (list of str): list of IP addresses
    """
    log = logger.getlogger()
    inv = Inventory()
    wait = float(wait)
    max_attempts = int(max_attempts)

    if not client_list:
        log.debug('Retrieving IPMI address list from inventory')
        client_list = inv.get_nodes_ipmi_ipaddr(0)

    clients_left = client_list[:]

    attempt = 0
    clients_left.sort()
    while clients_left and attempt < max_attempts:
        nodes = {}
        attempt += 1
        if attempt > 1:
            print('Retrying set power {}. Attempt {} of {}'
                  .format(state, attempt, max_attempts))
            print('Clients remaining: {}'.format(clients_left))
        clients_set = []
        bmc_dict = {}
        for index, hostname in enumerate(inv.yield_nodes_hostname()):
            ipv4 = inv.get_nodes_ipmi_ipaddr(0, index)
            if ipv4 not in clients_left:
                continue
            rack_id = inv.get_nodes_rack_id(index)
            userid = inv.get_nodes_ipmi_userid(index)
            password = inv.get_nodes_ipmi_password(index)
            nodes[ipv4] = [rack_id, ipv4]
            for i in range(2):
                try:
                    bmc_dict[ipv4] = ipmi_command.Command(
                        bmc=ipv4,
                        userid=userid,
                        password=password)
                except pyghmi_exception.IpmiException as error:
                    log.error('IPMI login attempt {}, address {}\nIPMI error'
                              'message: {}'.format(i, ipv4, error.message))
                    time.sleep(1)
                else:
                    break

        for client in clients_left:
            if client in bmc_dict:
                try:
                    log.debug('Setting power state to {}. Device: {}'
                              .format(state, client))
                    status = bmc_dict[client].set_power(state, wait)
                    if attempt in [2, 4, 8]:
                        print('{} - {}'.format(client, status))
                except pyghmi_exception.IpmiException as error:
                    msg = ('set_power failed Rack: %s - IP: %s, \n%s' %
                           (nodes[client][0], nodes[client][1], str(error)))
                    log.error(msg)
                else:
                    # Allow delay between turn on to limit power surge
                    if state == 'on':
                        time.sleep(0.5)
                finally:
                    if 'error' in status:
                        log.error(status)

        time.sleep(wait + attempt)

        for client in clients_left:
            if client in bmc_dict:
                try:
                    status = bmc_dict[client].get_power()
                    if attempt in [2, 4, 8]:
                        print('{} - {}'.format(client, status))
                except pyghmi_exception.IpmiException as error:
                    msg = ('get_power failed - Rack: %s - IP: %s, %s' %
                           (rack_id, ipv4, str(error)))
                    log.error(msg)
                else:
                    if status['powerstate'] == state:
                        log.debug('set_power successful Rack: %s - IP: %s' %
                                  (nodes[client][0], nodes[client][1]))
                        clients_set += [client]
                finally:
                    if 'error' in status:
                        log.error(status)
                bmc_dict[client].ipmi_session.logout()

        for client in clients_set:
            clients_left.remove(client)

        if attempt == max_attempts and clients_left:
            log.error('Failed to power {} some clients'.format(state))
            log.error(clients_left)

        del bmc_dict

    log.info('Powered {} {} of {} client devices.'
             .format(state, len(client_list) - len(clients_left), len(client_list)))

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
    parser.add_argument('state', default='none', nargs='?',
                        help='Boot device.  ie network or none...')

    parser.add_argument('client_list', default='', nargs='*',
                        help='List of ip addresses.')

    parser.add_argument('--print', '-p', dest='log_lvl_print',
                        help='print log level', default='info')

    parser.add_argument('--file', '-f', dest='log_lvl_file',
                        help='file log level', default='info')

    args = parser.parse_args()

    if args.log_lvl_print == 'debug':
        print(args)

    ipmi_set_power(args.state, args.client_list)
