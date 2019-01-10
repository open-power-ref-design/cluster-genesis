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
import os
from shutil import copy2
import fileinput
from orderedattrdict import AttrDict
import netaddr

from lib.logger import Logger
from lib.inventory import Inventory
from inv_add_switches import InventoryAddSwitches
from allocate_ip_addresses import allocate_ips


def mock_inventory(cfg_file, inv_file, log):

    # install.yml - include: lxc-update.yml
    copy2(cfg_file, inv_file)
    os.chmod(inv_file, 0o644)
    for line in fileinput.input(inv_file, inplace=1):
        print(line, end='')
        if line.startswith('password-default'):
            print('ansible_user: root')
            print('ansible_ssh_private_key_file: '
                  '/home/ubuntu/.ssh/id_rsa_ansible-generated')

    # install.yml - include: container/inv_add_ports.yml port_type=ipmi
    inv = Inventory(log, inv_file)
    (dhcp_mac_ip, mgmt_sw_cfg) = get_port_mac_ip(inv)
    inv.create_nodes(dhcp_mac_ip, mgmt_sw_cfg)

    # install.yml - include: container/inv_add_switches.yml
    InventoryAddSwitches(log, inv_file)

    # install.yml - include: container/inv_add_ports.yml port_type=pxe
    inv = Inventory(log, inv_file)
    inv.add_pxe(dhcp_mac_ip, mgmt_sw_cfg)

    # install.yml - include: container/inv_add_ipmi_data.yml
    inv = Inventory(log, inv_file)
    add_ipmi_data(inv)

    # install.yml - include: container/allocate_ip_addresses.yml
    inv = Inventory(log, inv_file)
    allocate_ips(inv_file)

    # gather_mac_addresses.yml
    inv = Inventory(log, inv_file)
    switch_ip_to_port_to_macs = get_switch_ip_to_mac_map(inv)
    inv.add_data_switch_port_macs(switch_ip_to_port_to_macs)


def get_port_mac_ip(inv):

    dhcp_mac_ip = AttrDict()
    mgmt_sw_cfg = AttrDict()
    port_mac = []

    network = '192.168.50.100/24'
    ipv4_start = netaddr.IPNetwork(network)
    ipmi_ip = 1
    pxe_ip = 2

    for _, template in inv.inv['node-templates'].items():
        if 'ports' in template:
            for inv_port_type, racks in template['ports'].items():
                rack_num = -1
                if inv_port_type in ['ipmi', 'pxe']:
                    for rack, ports in racks.items():
                        rack_num += 1
                        for port in ports:
                            mac = (b'00:00:00:00:%02d:%02d' %
                                   (rack_num, int(port)))
                            _dict = AttrDict()
                            _dict[port] = mac
                            port_mac.append(_dict)
                            if inv_port_type == 'ipmi':
                                dhcp_mac_ip[mac] = str(ipv4_start.ip + ipmi_ip)
                                ipmi_ip += 2
                            if inv_port_type == 'pxe':
                                dhcp_mac_ip[mac] = str(ipv4_start.ip + pxe_ip)
                                pxe_ip += 2
                    mgmt_sw_cfg[rack] = port_mac

    return (dhcp_mac_ip, mgmt_sw_cfg)


def get_switch_ip_to_mac_map(inv):

    switch_ip_to_mac_map = AttrDict()
    rack_id_to_ip = AttrDict()

    for rack_id, rack_ip in inv.inv['ipaddr-data-switch'].items():
        rack_id_to_ip[rack_id] = rack_ip

    for _, template in inv.inv['node-templates'].items():
        if 'ports' in template:
            for inv_port_type, racks in template['ports'].items():
                rack_num = -1
                if inv_port_type not in ['ipmi', 'pxe']:
                    for rack, ports in racks.items():

                        switch_ip = rack_id_to_ip[rack]

                        if type(switch_ip) == list:
                            for mlag_switch_ip in switch_ip:
                                if mlag_switch_ip not in switch_ip_to_mac_map:
                                    switch_ip_to_mac_map[mlag_switch_ip] = {}

                                rack_num += 1

                                for port in ports:
                                    mac = (b'00:A1:%02d:%02d:00:00' %
                                           (rack_num, int(port)))
                                    switch_ip_to_mac_map[mlag_switch_ip][str(port)] = (
                                        [mac])

                        else:
                            if switch_ip not in switch_ip_to_mac_map:
                                switch_ip_to_mac_map[switch_ip] = {}

                            rack_num += 1

                            for port in ports:
                                mac = (b'00:00:%02d:%02d:00:00' %
                                       (rack_num, int(port)))
                                switch_ip_to_mac_map[switch_ip][str(port)] = (
                                    [mac])

    return switch_ip_to_mac_map


def add_ipmi_data(inv):

    ppc_index = 0

    for _, _, _key, index, node in inv.yield_nodes():

        cobbler_profile = (
            inv.inv['node-templates'][node['template']]['cobbler-profile'])

        # currently architecture key only gets added for power nodes
        if 'ppc64' in cobbler_profile:
            architecture = b'ppc64'
            part_number = (b'PN0MOCK0PPC0 P%02d' % ppc_index)
            serial_number = (b'SN0MOCK0PPC0%02d' % ppc_index)
            ppc_index += 1
            inv.add_to_node(
                _key,
                index,
                inv.INV_ARCHITECTURE,
                architecture)
            inv.add_to_node(
                _key,
                index,
                inv.INV_CHASSIS_PART_NUMBER,
                part_number)
            inv.add_to_node(
                _key,
                index,
                inv.INV_CHASSIS_SERIAL_NUMBER,
                serial_number)


if __name__ == '__main__':
    """
    Arg1: Input config.yml
    Arg2: Output inventory.yml
    """

    LOG = Logger(__file__)

    PARSER = argparse.ArgumentParser()
    PARSER.add_argument("config_file",
                        help="Input config.yml to process",
                        nargs='?',
                        default='config.yml',
                        type=str)
    PARSER.add_argument("inventory_file",
                        help="Output inventory.yml path",
                        nargs='?',
                        default='inventory.yml',
                        type=str)
    ARGS = PARSER.parse_args()

    mock_inventory(ARGS.config_file,
                   ARGS.inventory_file,
                   LOG)
