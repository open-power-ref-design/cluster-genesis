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

from lib.logger import Logger
from lib.switch import SwitchFactory


def print_dict(dict):
    if not dict:
        print('{}')
    for key in dict.keys():
        print(key.ljust(10) + ' ' + str(dict[key]))
    print()


def main(log):
    sw = SwitchFactory.factory(log, 'lenovo', ip_addr='192.168.32.20', mode='passive', outfile='switch2_cmds.txt')

    sw.set_switchport_mode('trunk', 18)

    vlan_info = sw.show_vlans()
    print('vlan info: ')
    print(vlan_info)
    print()

    print('MAC address table: ')
    print(sw.show_mac_address_table())
    print()

    print('MAC address table dictionary: ')
    print_dict(sw.show_mac_address_table(format='dict'))
    print()

    print('Is pingable: ' + str(sw.is_pingable()))

    sw.set_switchport_mode('trunk', 18)
    resp = sw.is_port_in_trunk_mode(18)
    print('Port 18 is in trunk mode: ' + str(resp))
    print('Port 18 native vlan: ' + str(sw.show_native_vlan(18)))
    sw.set_switchport_native_vlan(1, 45)
    print('Port 45 native vlan: ' + str(sw.show_native_vlan(45)))
    sw.set_switchport_native_vlan(16, 45)
    print('Port 45 native vlan: ' + str(sw.show_native_vlan(45)))
    sys.exit(0)

    sw2 = SwitchFactory.factory(log, 'mellanox', '192.168.16.25', 'admin', 'admin')
    vlan_info = sw2.show_vlans()
    print(vlan_info)
    print(sw2.show_mac_address_table())

    sw3 = SwitchFactory.factory(log, 'mellanox', '192.168.16.30', 'admin', 'admin')
    print(sw3.show_vlans())
    print(sw3.show_mac_address_table())


if __name__ == '__main__':
    """Show status of the Cluster Genesis environment

    Args:
        INV_FILE (string): Inventory file.
        LOG_LEVEL (string): Log level.

    Raises:
       Exception: If parameter count is invalid.
    """

    LOG = Logger(__file__)
    ARGV_MAX = 3
    ARGV_COUNT = len(sys.argv)
    if ARGV_COUNT > ARGV_MAX:
        try:
            raise Exception()
        except:
            LOG.error('Invalid argument count')
            sys.exit(1)

    LOG.set_level('debug')

    main(LOG)
