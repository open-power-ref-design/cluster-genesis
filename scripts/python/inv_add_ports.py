#!/usr/bin/env python
# Copyright 2017 IBM Corp.
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

import sys
import time
import os.path
from orderedattrdict import AttrDict
from tabulate import tabulate

import lib.logger as logger
from lib.config import Config
from lib.inventory import Inventory
from lib.switch import SwitchFactory
from lib.switch_common import SwitchCommon
from get_dhcp_lease_info import GetDhcpLeases
from lib.genesis import GEN_PASSIVE_PATH


class InventoryAddPorts(object):
    """Class instance for adding port information to the Cluster Genesis
    inventory file.
    Args:
        dhcp_leases_file (str): file path for the dnsmasq.leases file.
        port_type (str): 'ipmi' or 'pxe'
    """
    def __init__(self, dhcp_leases_file, port_type, config_path=None):
        self.log = logger.getlogger()
        self.cfg = Config(config_path)
        self.dhcp_leases_file = dhcp_leases_file
        self.port_type = port_type
        self.inv = Inventory(cfg_file=config_path)
        self.log.debug('Add ports, port type: {}'.format(self.port_type))
        self.sw_dict = {}
        for sw_ai in self.cfg.yield_sw_mgmt_access_info():
            label = sw_ai[0]
            self.sw_dict[label] = SwitchFactory.factory(*sw_ai[1:])

    def get_ports(self):
        dhcp_leases = GetDhcpLeases(self.dhcp_leases_file)
        dhcp_mac_ip = dhcp_leases.get_mac_ip()
        self.log.debug('DHCP leases: {}'.format(dhcp_mac_ip))

        mgmt_sw_cfg_mac_lists = AttrDict()

        if self.cfg.is_passive_mgmt_switches():
            self.log.debug('passive mode')
            for switch_label in self.cfg.yield_sw_mgmt_label():
                file_path = os.path.join(GEN_PASSIVE_PATH, switch_label)
                mac_info = {}
                try:
                    with open(file_path, 'r') as f:
                        mac_info = f.read()

                except IOError as error:
                    self.log.error(
                        'Passive switch MAC address table file not found {}'
                        .format(error))
                    raise
                mgmt_sw_cfg_mac_lists[switch_label] = \
                    SwitchCommon.get_port_to_mac(mac_info, self.log)
        else:
            for switch in self.sw_dict:
                self.log.debug('Switch: {}'.format(switch))
                mgmt_sw_cfg_mac_lists[switch] = \
                    self.sw_dict[switch].show_mac_address_table(format='std')

        self.log.debug('Management switches MAC address tables: {}'.format(
            mgmt_sw_cfg_mac_lists))

        # Remove all the mac address table entries which do not have a matching
        # MAC address in the DHCP leases table, then remove any MAC addresses
        # which do not have a  DHCP table entry.
        for switch in mgmt_sw_cfg_mac_lists.keys():
            for port in mgmt_sw_cfg_mac_lists[switch]:
                port_macs = mgmt_sw_cfg_mac_lists[switch][port]
                found_mac = False
                for mac in dhcp_mac_ip.keys():
                    if mac in port_macs:
                        found_mac = True
                        # keep only the mac which has a dhcp address
                        mgmt_sw_cfg_mac_lists[switch][port] = [mac]
                if not found_mac:
                    del mgmt_sw_cfg_mac_lists[switch][port]
        self.log.debug('Management switches MAC address table of ports with'
                       'dhcp leases: {}'.format(mgmt_sw_cfg_mac_lists))

        if self.port_type == "ipmi":
            self.inv.add_macs_ipmi(mgmt_sw_cfg_mac_lists)
            self.inv.add_ipaddrs_ipmi(dhcp_mac_ip)
        elif self.port_type == "pxe":
            self.inv.add_macs_pxe(mgmt_sw_cfg_mac_lists)
            self.inv.add_ipaddrs_pxe(dhcp_mac_ip)

        if self.port_type == 'ipmi':
            self.node_table, self.ports_found, self.ports_total = \
                self._build_node_table_ipmi(self.cfg, dhcp_mac_ip, mgmt_sw_cfg_mac_lists)

        if self.port_type == 'pxe':
            self.node_table, self.ports_found, self.ports_total = \
                self._build_node_table_pxe(self.cfg, dhcp_mac_ip, mgmt_sw_cfg_mac_lists)

    def _build_node_table_ipmi(self, cfg, dhcp_list, mac_lists):
        # Tabulate results by Node type (template)
        node_table = {}
        ports_total = 0
        ports_found = 0
        for idx_ntmplt in self.cfg.yield_ntmpl_ind():
            node_label = self.cfg.get_ntmpl_label(idx_ntmplt)
            self.log.debug('node label: {}'.format(node_label))
            ports_list = []

            for idx_ipmi in self.cfg.yield_ntmpl_phyintf_ipmi_ind(idx_ntmplt):
                switch_label = self.cfg.get_ntmpl_phyintf_ipmi_switch(
                    idx_ntmplt, idx_ipmi)
                ports_total += self.cfg.get_ntmpl_phyintf_ipmi_pt_cnt(
                    idx_ntmplt, idx_ipmi)

                for idx_port in self.cfg.yield_ntmpl_phyintf_ipmi_pt_ind(
                        idx_ntmplt, idx_ipmi):
                    port = self.cfg.get_ntmpl_phyintf_ipmi_ports(
                        idx_ntmplt, idx_ipmi, idx_port)
                    result = self.inv.get_port_mac_ip(switch_label, port)
                    if None not in result:
                        ports_found += 1
                        ports_list.append(
                            [True, switch_label, port, result[0], result[1], 'ipmi'])
                        self.log.debug(
                            'Node Port Defined in Inventory - Template: {}'
                            'Switch: {} Port: {} MAC: {} IP: {}'.format(
                                node_label, switch_label, port, result[0],
                                result[1], 'ipmi'))
                    elif str(port) in mac_lists[switch_label]:
                        for mac in mac_lists[switch_label][str(port)]:
                            if mac in dhcp_list:
                                ipaddr = dhcp_list[mac]
                                ports_list.append(
                                    [False, switch_label, port, mac,
                                     ipaddr, 'ipmi'])
                                self.log.debug(
                                    'Node Port MAC/IP NOT Defined in Inventory - '
                                    'Template: {} Switch: {} Port: {} '
                                    'MAC: {} IP: {}'.format(
                                        node_label, switch_label, port, mac, ipaddr))
                            else:
                                ports_list.append(
                                    [False, switch_label, port, mac, '-', 'ipmi'])
                                self.log.debug(
                                    'No DHCP Lease Found for Port MAC Address - '
                                    'Template: {} Switch: {} Port: {} '
                                    'MAC: {}'.format(
                                        node_label, switch_label, port, mac))
                    else:
                        ports_list.append(
                            [False, switch_label, port, '-', '-', 'ipmi'])
                        self.log.debug(
                            'No Entries Found in MGMT Switch MAC Address Table - '
                            'Template: {} Switch: {} Port: {}'.format(
                                node_label, switch_label, port))
            node_table[node_label] = ports_list
        self.log.debug('node table: {}'.format(node_table))
        return node_table, ports_found, ports_total

    def _build_node_table_pxe(self, cfg, dhcp_list, mac_lists):
        # Tabulate results by Node type (template)
        node_table = {}
        ports_total = 0
        ports_found = 0
        for idx_ntmplt in cfg.yield_ntmpl_ind():
            node_label = cfg.get_ntmpl_label(idx_ntmplt)
            self.log.debug('node label: {}'.format(node_label))
            ports_list = []

            for idx_pxe in cfg.yield_ntmpl_phyintf_pxe_ind(idx_ntmplt):
                switch_label = cfg.get_ntmpl_phyintf_pxe_switch(idx_ntmplt, idx_pxe)
                ports_total += cfg.get_ntmpl_phyintf_pxe_pt_cnt(idx_ntmplt, idx_pxe)

                for idx_port in cfg.yield_ntmpl_phyintf_pxe_pt_ind(
                        idx_ntmplt, idx_pxe):
                    port = cfg.get_ntmpl_phyintf_pxe_ports(
                        idx_ntmplt, idx_pxe, idx_port)
                    result = self.inv.get_port_mac_ip(switch_label, port)
                    if None not in result:
                        ports_found += 1
                        ports_list.append(
                            [True, switch_label, port, result[0], result[1], 'pxe'])
                        self.log.debug(
                            'Node Port Defined in Inventory - Template: {}'
                            'Switch: {} Port: {} MAC: {} IP: {}'.format(
                                node_label, switch_label, port, result[0],
                                result[1], 'pxe'))
                    elif str(port) in mac_lists[switch_label]:
                        for mac in mac_lists[switch_label][str(port)]:
                            if mac in dhcp_list:
                                ipaddr = dhcp_list[mac]
                                ports_list.append(
                                    [False, switch_label, port, mac,
                                     ipaddr, 'pxe'])
                                self.log.debug(
                                    'Node Port MAC/IP NOT Defined in Inventory - '
                                    'Template: {} Switch: {} Port: {} '
                                    'MAC: {} IP: {}'.format(
                                        node_label, switch_label, port, mac, ipaddr))
                            else:
                                ports_list.append(
                                    [False, switch_label, port, mac, '-', 'pxe'])
                                self.log.debug(
                                    'No DHCP Lease Found for Port MAC Address - '
                                    'Template: {} Switch: {} Port: {} '
                                    'MAC: {}'.format(
                                        node_label, switch_label, port, mac))
                    else:
                        ports_list.append(
                            [False, switch_label, port, '-', '-', 'pxe'])
                        self.log.debug(
                            'No Entries Found in MGMT Switch MAC Address Table - '
                            'Template: {} Switch: {} Port: {}'.format(
                                node_label, switch_label, port))
            node_table[node_label] = ports_list
        self.log.debug('node table: {}'.format(node_table))
        return node_table, ports_found, ports_total

    def get_table(self):
        return self.node_table

    def get_table_pretty(self):
        """Generates a list of node template names and pretty tables. To
        print, simply print the list items. ie;
        for item in add_ports.get_table_pretty():
            print item
        """
        blue = '\033[94m'
        endc = '\033[0m'
        table_pretty = []
        table_header = ['In-Inventory', 'Switch', 'Port',
                        'MAC', 'IP', 'Port type']
        for template in self.node_table.keys():
            table_pretty.append('\n{}Node Type: {}:{}'.format(blue, template, endc))
            table_pretty.append(tabulate(self.node_table[template], table_header))

        return table_pretty

    def get_status(self):
        return (self.ports_found, self.ports_total)


def get_port_status(dhcp_leases_file, port_type, config_path):
    log = logger.getlogger()
    found_all = False
    max_cnt = 30
    yellow = '\033[93m'
    endc = '\033[0m'

    INV_PORTS = InventoryAddPorts(dhcp_leases_file, port_type, config_path)
    while found_all is not True:
        print()
        for cnt in range(max_cnt):
            print(' Gathering port info - ', cnt, '\r', end="")
            sys.stdout.flush()
            time.sleep(5)
            INV_PORTS.get_ports()
            status = INV_PORTS.get_status()
            if status[0] == status[1]:
                for item in INV_PORTS.get_table_pretty():
                    print(item)
                print()
                log.info('Complete. Found {} of {} nodes'.format(status[0], status[1]))
                found_all = True
                break
        if found_all:
            break
        for item in INV_PORTS.get_table_pretty():
            print(item)
        print()
        log.warning('Incomplete! Found {} of {} nodes'.format(status[0], status[1]))
        print('{}-------------------------------------------{}'.format(yellow, endc))
        print("\nPress enter to continue gathering port information.")
        resp = raw_input("Enter C to continue Cluster Genesis or 'T' to terminate ")
        if resp == 'T':
            log.info("'{}' entered. Terminating Genesis at user request".format(resp))
            sys.exit(1)
        elif resp == 'C':
            log.info("'{}' entered. Continuing Genesis".format(resp))
            break


if __name__ == '__main__':
    """
    Arg1: DHCP leases file
    Arg2: Port Type
    """
    logger.create('nolog', 'info')
    LOG = logger.getlogger()

    if len(sys.argv) != 4:
        sys.exit('Invalid argument count')

    DHCP_LEASES_FILE = sys.argv[1]
    PORT_TYPE = sys.argv[2]
    CONFIG_PATH = sys.argv[3]

    get_port_status(DHCP_LEASES_FILE, PORT_TYPE, CONFIG_PATH)
