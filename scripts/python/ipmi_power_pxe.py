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

import sys
import time
from pyghmi import exceptions as pyghmi_exception
from tabulate import tabulate

from lib.inventory import Inventory
from lib.ipmi_power import IpmiPower
from lib.logger import Logger
from get_dhcp_lease_info import GetDhcpLeases
from lib.utilities import bmc_ipmi_login


class IpmiPowerPXE(object):
    def __init__(self, log, inv_file, dhcp_leases_path, time_out, wait):
        self.log = log

        inv = Inventory(self.log, inv_file)
        self.ipmi_power = IpmiPower(self.log)

        # Get list of BMCs from DHCP lease file
        dhcp_leases = GetDhcpLeases(dhcp_leases_path, self.log)
        bmc_leases = dhcp_leases.get_mac_ip()
        bmc_list = []
        unsuccessful_ip_list = []
        for mac, ipv4 in bmc_leases.items():
            bmc = {}
            bmc['ipv4'] = ipv4
            bmc['rack_id'] = 'passive'
            for userid, password in inv.yield_ipmi_credential_sets():
                bmc['userid'] = userid
                bmc['password'] = password

                self.log.debug(
                    'Attempting IPMI connection to IP: %s  userid: %s  '
                    'password: %s' % (ipv4, userid, password))

                try:
                    _rc, _ = self.ipmi_power.is_power_off(bmc)
                except SystemExit:
                    continue

                self.log.info(
                    'Successful IPMI connection to IP: %s  userid: %s  '
                    'password: %s' % (ipv4, userid, password))
                bmc_list.append(bmc)
                break
            else:
                self.log.warning(
                    'Unsuccessful IPMI connection to IP: %s' % ipv4)
                bmc.pop('userid')
                bmc.pop('password')
                unsuccessful_ip_list.append(bmc)

        if len(bmc_list) > 0:
            print("-" * 47)
            print("Successful IPMI connections:")
            print("-" * 47)
            print(tabulate(bmc_list, headers="keys"))

        if len(bmc_list) < inv.get_expected_node_count():
            msg = ('\nFAIL: %d BMC(s) defined in config.yml but only %d IPMI '
                   'connection(s) found!' %
                   (inv.get_expected_node_count(), len(bmc_list)))
            self.log.error(msg)
            print(msg)
            if len(unsuccessful_ip_list) > 0:
                print("-" * 54)
                print("IPs with DHCP leases but IPMI connection unsuccessful:")
                print("-" * 54)
                print(tabulate(unsuccessful_ip_list, headers="keys"))
            sys.exit

        # Power off
        for bmc in bmc_list:
            _rc, _ = self.ipmi_power.is_power_off(bmc)
            if _rc:
                self.log.debug(
                    'Already powered off - Rack: %s - IP: %s' %
                    (bmc['rack_id'], bmc['ipv4']))
            else:
                self.ipmi_power.set_power_off(bmc)
        start_time = time.time()
        attempt = 1
        bmcs = list(bmc_list)
        while bmcs:
            if time.time() > start_time + time_out:
                break
            time.sleep(wait)
            bmcs[:] = [
                bmc
                for bmc in bmcs
                if self._is_not_power_off(bmc, attempt) is not None]
            attempt += 1

        for bmc in bmcs:
            self.log.error(
                'Power off unsuccessful - Rack: %s - IP: %s - State: %s' %
                (bmc['rack_id'], bmc['ipv4'], bmc['power_state']))
        for bmc in bmcs:
            sys.exit(1)

        # Set boot device to pxe (not persistent)
        bootdev = 'pxe'
        persist = False
        for bmc in bmc_list:
            ipmi_cmd = bmc_ipmi_login(bmc['ipv4'],
                                      bmc['userid'],
                                      bmc['userid'])
            try:
                ipmi_cmd.set_bootdev(bootdev, persist)
            except pyghmi_exception.IpmiException as error:
                log.error(
                    'set_bootdev failed (device=%s persist=%s) - '
                    'IP: %s, %s' %
                    (bootdev, persist, bmc['ipv4'], str(error)))
                sys.exit(1)
            log.info(
                'set_bootdev success (device=%s persist=%s) - '
                'IP: %s' %
                (bootdev, persist, bmc['ipv4']))

        # Power on
        for bmc in bmc_list:
            _rc, _ = self.ipmi_power.is_power_on(bmc)
            if _rc:
                self.log.info(
                    'Already powered on - Rack: %s - IP: %s' %
                    (bmc['rack_id'], bmc['ipv4']))
            else:
                self.ipmi_power.set_power_on(bmc)
        start_time = time.time()
        attempt = 1
        bmcs = list(bmc_list)
        while bmcs:
            if time.time() > start_time + time_out:
                break
            time.sleep(wait)
            bmcs[:] = [
                bmc
                for bmc in bmcs
                if self._is_not_power_on(bmc, attempt) is not None]
            attempt += 1

        for bmc in bmcs:
            self.log.error(
                'Power on unsuccessful - Rack: %s - IP: %s - State: %s' %
                (bmc['rack_id'], bmc['ipv4'], bmc['power_state']))
        for bmc in bmcs:
            sys.exit(1)

    def _is_not_power_on(self, bmc, attempt):
        _rc, power_state = self.ipmi_power.is_power_on(bmc)
        if _rc:
            self.log.info(
                'Power on successful - Rack: %s - IP: %s' %
                (bmc['rack_id'], bmc['ipv4']))
            return None
        bmc['power_state'] = power_state
        self.log.debug(
            'Power on pending - Rack: %s - IP: %s - State: %s - Attempt: %s' %
            (bmc['rack_id'], bmc['ipv4'], bmc['power_state'], attempt))
        return bmc

    def _is_not_power_off(self, bmc, attempt):
        _rc, power_state = self.ipmi_power.is_power_off(bmc)
        if _rc:
            self.log.info(
                'Power off successful - Rack: %s - IP: %s' %
                (bmc['rack_id'], bmc['ipv4']))
            return None
        bmc['power_state'] = power_state
        self.log.debug(
            'Power off pending - Rack: %s - IP: %s - State: %s - Attempt: %s' %
            (bmc['rack_id'], bmc['ipv4'], bmc['power_state'], attempt))
        return bmc


if __name__ == '__main__':
    """
    Arg1: inventory file
    Arg2: dhcp leases file path
    Arg3: time out
    Arg4: wait time
    Arg5: log level
    """
    LOG = Logger(__file__)

    if len(sys.argv) != 6:
        try:
            raise Exception()
        except Exception:
            LOG.error('Invalid argument count')
            sys.exit(1)

    INV_FILE = sys.argv[1]
    DHCP_LEASES_PATH = sys.argv[2]
    TIME_OUT = int(sys.argv[3])
    WAIT = int(sys.argv[4])
    LOG.set_level(sys.argv[5])

    IpmiPowerPXE(LOG, INV_FILE, DHCP_LEASES_PATH, TIME_OUT, WAIT)
