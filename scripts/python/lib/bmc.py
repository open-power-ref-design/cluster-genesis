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
import requests.exceptions

import lib.logger as logger
import lib.open_bmc as open_bmc
import lib.ipmi as ipmi


class Bmc(object):
    """ Creates a 'bmc' class instance. The created class establishes a
    connection to a BMC. The connection can be openBMC rest API or IPMI.
    Args:
        host (str): ip address or resolvable hostname.
        user (str): User id
        pw (str): Pass word
        bmc_type (str): Indicates the type of BMC ('ipmi' or 'openbmc')
    """

    def __init__(self, host, user, pw, bmc_type='ipmi', timeout=10):
        self.log = logger.getlogger()
        self.host = host
        self.user = user
        self.pw = pw
        self.bmc_type = bmc_type
        self.timeout = timeout
        self.connected = False

        if bmc_type == 'openbmc':
            self.bmc = open_bmc.login(host, user, pw)
            if isinstance(self.bmc, requests.sessions.Session):
                self.connected = True
        elif bmc_type == 'ipmi':
            self.bmc = ipmi.login(host, user, pw, timeout=timeout)
            if isinstance(self.bmc, ipmi.command.Command):
                self.connected = True
        else:
            self.log.error(f'Unsupported BMC type: {bmc_type}')

    def is_connected(self):
        return self.connected

    def get_host(self):
        return self.host

    def get_system_sn_pn(self, timeout=5):
        if self.bmc_type == 'openbmc':
            return open_bmc.get_system_sn_pn(self.host, self.bmc)
        if self.bmc_type == 'ipmi':
            return ipmi.get_system_sn_pn(self.host, self.user, self.pw)

    def get_system_info(self, timeout=5):
        if self.bmc_type == 'openbmc':
            return open_bmc.get_system_info(self.host, self.bmc)
        if self.bmc_type == 'ipmi':
            return ipmi.get_system_info(self.host, self.user, self.pw)

    def get_system_inventory_in_background(self):
        if self.bmc_type == 'openbmc':
            self.error('Not implemented')
            return
            # return open_bmc.get_system_info(self.host, self.bmc)
        if self.bmc_type == 'ipmi':
            return ipmi.get_system_inventory_in_background(self.host,
                                                           self.user, self.pw)

    def extract_system_info(self, inventory):
        if self.bmc_type == 'openbmc':
            self.error('Not implemented')
            return
            # return open_bmc.extract_system_info(inventory)
        if self.bmc_type == 'ipmi':
            return ipmi.extract_system_info(inventory)

    def extract_system_sn_pn(self, inventory):
        if self.bmc_type == 'openbmc':
            self.error('Not implemented')
            return
            # return open_bmc.extract_system_info(inventory)
        if self.bmc_type == 'ipmi':
            return ipmi.extract_system_sn_pn(inventory)

    def logout(self):
        if self.bmc_type == 'openbmc':
            return open_bmc.logout(self.host, self.user, self.pw, self.bmc)
        elif self.bmc_type == 'ipmi':
            return ipmi.logout(self.host, self.user, self.pw, self.bmc)

    def chassis_power(self, op, timeout=5):
        if self.bmc_type == 'openbmc':
            return open_bmc.chassisPower(self.host, op, self.bmc)
        if self.bmc_type == 'ipmi':
            return ipmi.chassisPower(self.host, op, self.bmc)

    def host_boot_source(self, source='', timeout=5):
        if self.bmc_type == 'openbmc':
            return open_bmc.hostBootSource(self.host, source, self.bmc)
        elif self.bmc_type == 'ipmi':
            return ipmi.hostBootSource(self.host, source, self.bmc)

    def host_boot_mode(self, mode='', timeout=5):
        if self.bmc_type == 'openbmc':
            return open_bmc.hostBootMode(self.host, mode, self.bmc)
        elif self.bmc_type == 'ipmi':
            return ipmi.hostBootMode(self.host, mode, self.bmc)

    def bmc_reset(self, op):
        if self.bmc_type == 'openbmc':
            return open_bmc.bmcReset(self.host, op, self.bmc)
        elif self.bmc_type == 'ipmi':
            return ipmi.bmcReset(self.host, op, self.bmc)

    def bmc_status(self, timeout=5):
        if self.bmc_type == 'openbmc':
            return open_bmc.bmcPowerState(self.host, self.bmc, timeout)
        elif self.bmc_type == 'ipmi':
            return 'Ready'


if __name__ == '__main__':
    """Show status of the POWER-Up environment
    Args:
        INV_FILE (string): Inventory file.
        LOG_LEVEL (string): Log level.

    Raises:
       Exception: If parameter count is invalid.
    """

    logger.create('debug', 'debug')
    log = logger.getlogger()

    parser = argparse.ArgumentParser()
    parser.add_argument('host', nargs='?',
                        help='bmc ip address',
                        default='')

    parser.add_argument('user', nargs='?',
                        help='bmc user',
                        default='ADMIN')

    parser.add_argument('pw', nargs='?',
                        help='bmc password',
                        default='admin')

#    parser.add_argument('user', nargs='?',
#                        help='bmc user',
#                        default='root')
#
#    parser.add_argument('pw', nargs='?',
#                        help='bmc password',
#                        default='0penBmc')

    parser.add_argument('bmc_type', nargs='?', choices=['open', 'ipmi'],
                        help='bmc type (open, ipmi)',
                        default='ipmi')

    parser.add_argument('--print', '-p', dest='log_lvl_print',
                        help='print log level', default='info')

    parser.add_argument('--file', '-f', dest='log_lvl_file',
                        help='file log level', default='info')

    args = parser.parse_args()

    if not args.host:
        args.host = input('Enter bmc ip address: ')

    bmc = Bmc(args.host, args.user, args.pw, args.bmc_type)

    if bmc.is_connected():
        print(f'logged into BMC {bmc}')
        if args.bmc_type in ('open', 'ipmi'):
            bmc_status = bmc.bmc_status()
            print(f'BMC status: {bmc_status}')
            # print('Rebooting bmc')
            # r = bmc.bmc_reset('cold')
            # print(f'BMC response: {r}')
            # if not r:
            #     log.error(f'Failed reboot of bmc {args.host}.')
            # else:
            #     print('Attempting BMC logout...')
            #     if bmc.logout():
            #         print(f'Logged out of BMC {args.host}')
            #     else:
            #         log.debug(f'Failed to log out of BMC {args.host}')
            #         del bmc

            # print('Setting host boot mode')
            # r = bmc.host_boot_mode('regular')

            # get boot source
            # r = bmc.host_boot_source()
            # print(f'host boot source: {r}')

            # source = 'network'
            # source = 'default'
            # print(f'Setting host boot source to {source}')
            # r = bmc.host_boot_source(source)

            # print('clossing BMC connection')
            # bmc.logout()

        print('Attempting to log back into BMC')
        while True:
            bmc = Bmc(args.host, args.user, args.pw, args.bmc_type)
            if bmc.is_connected():
                print(f'\nsuccessfully logged back into {args.host}')
                break
            else:
                print('Failed login attempt')
                time.sleep(3)
    else:
        log.error('Failed to instantiate the bmc class')

    print('done')
