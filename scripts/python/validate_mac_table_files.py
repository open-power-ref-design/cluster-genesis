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

import sys
import os.path
import re
import filecmp

from lib.logger import Logger
from lib.inventory import Inventory


def validate_mgmt_mac_table_files(log, inv):
    """Validate Management Switch Passive MAC Address Table Files

    Args:
        log (:obj:`Logger`): Log file object.
        inv (:obj:`Inventory`): Cluster Genesis Inventory object.

    Returns:
        boolean: True if all passive MAC address table files look good,
                 False otherwise
    """
    validation = True

    if inv.is_passive_mgmt_switches():
        for rack, switch_ip in inv.yield_mgmt_rack_ipv4():
            file_path = get_mac_table_file_path(switch_ip)
            if not os.path.isfile(file_path):
                validation = False
                msg = ("No MAC Address Table File Found For Mgmt Switch '%s'"
                       " ('%s')" % (switch_ip, file_path))
                LOG.error(msg)
                print("Error: " + msg)
            elif os.path.getsize(file_path) == 0:
                validation = False
                msg = ("Empty MAC Address Table File Found For Mgmt Switch"
                       " '%s' ('%s')" % (switch_ip, file_path))
                LOG.error(msg)
                print("Error: " + msg)
            elif check_duplicate_files(log, inv):
                validation = False

    return validation


def validate_data_mac_table_files(log, inv):
    """Validate Data Switch Passive MAC Address Table Files

    Args:
        log (:obj:`Logger`): Log file object.
        inv (:obj:`Inventory`): Cluster Genesis Inventory object.

    Returns:
        boolean: True if all passive MAC address table files look good,
                 False otherwise
    """
    validation = True

    if inv.is_passive_data_switches():
        for switch_ip, x in inv.get_data_switches().items():
            file_path = get_mac_table_file_path(switch_ip)
            if not os.path.isfile(file_path):
                validation = False
                msg = ("No MAC Address Table File Found For Data Switch '%s'"
                       " ('%s')" % (switch_ip, file_path))
                log.error(msg)
                print("Error: " + msg)
            elif os.path.getsize(file_path) == 0:
                validation = False
                msg = ("Empty MAC Address Table File Found For Data Switch"
                       " '%s' ('%s')" % (switch_ip, file_path))
                log.error(msg)
                print("Error: " + msg)
            elif check_duplicate_files(log, inv):
                validation = False

    return validation


def get_mac_table_file_path(switch_ip):
    """Get Passive MAC Address Table File Path

    Args:
        switch_ip (string): Passive switch alias found in Inventory
                            switch_ip

    Returns:
        string: Expected MAC address table file path
    """
    scripts_path = os.path.abspath(__file__)
    passive_path = (
        re.match(r'(.*cluster\-genesis).*', scripts_path).group(1) +
        '/passive/')
    file_path = passive_path + switch_ip

    return file_path


def check_duplicate_files(log, inv):
    """Check if any passive MAC address table files are identical

    Args:
        log (:obj:`Logger`): Log file object.
        inv (:obj:`Inventory`): Cluster Genesis Inventory object.

    Returns:
        boolean: True if duplicate files found, False otherwise
    """
    if inv.is_passive_mgmt_switches():
        for rack, switch_ip_1 in inv.yield_mgmt_rack_ipv4():
            file_path_1 = get_mac_table_file_path(switch_ip_1)

            if os.path.isfile(file_path_1):
                for rack, switch_ip_2 in inv.yield_mgmt_rack_ipv4():
                    if switch_ip_1 != switch_ip_2:
                        file_path_2 = get_mac_table_file_path(switch_ip_2)
                        if os.path.isfile(file_path_2):
                            if compare_files(file_path_1, file_path_2, log):
                                return True

                if inv.is_passive_data_switches():
                    for switch_ip_2, x in inv.get_data_switches().items():
                        file_path_2 = get_mac_table_file_path(switch_ip_2)
                        if os.path.isfile(file_path_2):
                            if compare_files(file_path_1, file_path_2, log):
                                return True

    if inv.is_passive_data_switches():
        for switch_ip_1, x in inv.get_data_switches().items():
            file_path_1 = get_mac_table_file_path(switch_ip_1)

            if os.path.isfile(file_path_1):
                for switch_ip_2, x in inv.get_data_switches().items():
                    if switch_ip_1 != switch_ip_2:
                        file_path_2 = get_mac_table_file_path(switch_ip_2)
                        if compare_files(file_path_1, file_path_2, log):
                            return True


def compare_files(file1, file2, log):
    """Compare two files

    Use Python's filecmp module to compare two files and log/print
    results.

    Args:
        file1 (string): Path of first file to compare
        file2 (string): Path of second file to compare
        log (:obj:`Logger`): Log file object.

    Returns:
        boolean: True if they seem equal, False otherwise
    """
    if filecmp.cmp(file1, file2):
        msg = ("Two MAC Address Table Files Are Identical! '%s' & '%s'"
               % (file1, file2))
        log.error(msg)
        print("Error: " + msg)
        return True
    else:
        return False


if __name__ == '__main__':
    """
    Arg1: inventory file
    Arg2: switch type
    Arg3: log level
    """
    LOG = Logger(__file__)

    if len(sys.argv) != 4:
        try:
            raise Exception()
        except:
            LOG.error('Invalid argument count')
            sys.exit(1)

    INV_FILE = sys.argv[1]
    SWITCH_TYPE = sys.argv[2]
    LOG.set_level(sys.argv[3])

    INV = Inventory(LOG, INV_FILE)

    if SWITCH_TYPE == 'mgmt':
        result = validate_mgmt_mac_table_files(LOG, INV)
    elif SWITCH_TYPE == 'data':
        result = validate_data_mac_table_files(LOG, INV)
    else:
        LOG.error('Invalid "switch type" argument')
        sys.exit(1)

    if not result:
        sys.exit(1)
