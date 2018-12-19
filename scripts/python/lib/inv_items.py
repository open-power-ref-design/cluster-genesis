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

from netaddr import iter_iprange
from netaddr import IPAddress

import lib.logger as logger
from lib.config import Config
from lib.inventory import Inventory
from lib.exception import UserException


class InventorySwitches(object):

    def __init__(self, inv_path=None, cfg_path=None):
        self.log = logger.getlogger()

        self.cfg_path = cfg_path
        self.inv = Inventory(cfg_path, inv_path)

    def __del__(self):
        self.inv.update_switches()

    def create_switches(self):
        pass
        # cfg = Config(self.cfg_path)


class InventoryNodes(object):
    SWITCH_NOT_FOUND = \
        "Node template '%s' did not have corresponding management switch '%s'"

    def __init__(self, inv_path=None, cfg_path=None):
        self.log = logger.getlogger()

        self.cfg_path = cfg_path
        self.inv = Inventory(cfg_path, inv_path)

    def __del__(self):
        self.inv.update_nodes()

    def create_nodes(self):
        cfg = Config(self.cfg_path)
        interface_ip_lists = _gen_interface_ip_lists(cfg)
        # Iterate over node templates
        for index_ntmplt in cfg.yield_ntmpl_ind():
            # Get Label
            label = cfg.get_ntmpl_label(index_ntmplt)
            # Get Hostname
            hostname = cfg.get_ntmpl_os_hostname_prefix(index_ntmplt)
            if hostname is None:
                hostname = label
            # Get bmc_type
            bmc_type = cfg.get_ntmpl_bmc_type(index_ntmplt)
            # Get Rack
            switch_label = cfg.get_ntmpl_phyintf_ipmi_switch(index_ntmplt, 0)
            switch_index = cfg.get_sw_mgmt_index_by_label(switch_label)
            if switch_index is None:
                node_template = cfg.get_ntmpl_label(index_ntmplt)
                self.log.error(self.SWITCH_NOT_FOUND % (
                    node_template, switch_label))
            # Iterate over client systems
            index_host = 0
            for index_port in cfg.yield_ntmpl_phyintf_ipmi_pt_ind(
                    index_ntmplt, 0):
                # Set Label
                self.inv.add_nodes_label(label)
                # Set Hostname
                self.inv.add_nodes_hostname(
                    hostname + '-' + str(index_host + 1))
                # Set bmc_type
                self.inv.add_nodes_bmc_type(bmc_type)
                # Set Rack ID
                switch_label = cfg.get_ntmpl_phyintf_ipmi_switch(
                    index_ntmplt, 0)
                switch_index = cfg.get_sw_mgmt_index_by_label(switch_label)
                self.inv.add_nodes_rack_id(cfg.get_sw_mgmt_rack_id(
                    switch_index))
                # Copy OS settings dictionary
                self.inv.add_nodes_os_dict(cfg.get_ntmpl_os_dict(index_ntmplt))
                # Copy roles
                self.inv.add_nodes_roles(cfg.get_ntmpl_roles(index_ntmplt))

                ports_ipmi = []
                ports_pxe = []
                switches_ipmi = []
                switches_pxe = []
                macs_ipmi = []
                macs_pxe = []
                ipaddrs_ipmi = []
                ipaddrs_pxe = []
                devices_pxe = []
                rename_pxe = []
                # Iterate over IPMI members
                for index_ipmi in cfg.yield_ntmpl_phyintf_ipmi_ind(
                        index_ntmplt):
                    # Create client system IPMI switch list
                    switches_ipmi.append(cfg.get_ntmpl_phyintf_ipmi_switch(
                        index_ntmplt, index_ipmi))
                    # Create client system PXE switch list
                    switches_pxe.append(cfg.get_ntmpl_phyintf_pxe_switch(
                        index_ntmplt, index_ipmi))
                    # Create client system IPMI port list
                    ports_ipmi.append(cfg.get_ntmpl_phyintf_ipmi_ports(
                        index_ntmplt, index_ipmi, index_port))
                    # Create client system PXE port list
                    ports_pxe.append(cfg.get_ntmpl_phyintf_pxe_ports(
                        index_ntmplt, index_ipmi, index_port))
                    # Create client system IPMI mac list
                    macs_ipmi.append(None)
                    # Create client system PXE mac list
                    macs_pxe.append(None)
                    # Create client system IPMI ipaddrs list
                    ipaddrs_ipmi.append(None)
                    # Create client system PXE ipaddrs list
                    ipaddrs_pxe.append(None)
                    # Create client PXE network device list
                    devices_pxe.append(cfg.get_ntmpl_phyintf_pxe_dev(
                        index_ntmplt))
                    # Create client PXE device rename list
                    rename_pxe.append(cfg.get_ntmpl_phyintf_pxe_rename(
                        index_ntmplt))
                # Set client system IPMI switches
                self.inv.add_nodes_switches_ipmi(switches_ipmi)
                # Set client system PXE switches
                self.inv.add_nodes_switches_pxe(switches_pxe)
                # Set client system IPMI ports
                self.inv.add_nodes_ports_ipmi(ports_ipmi)
                # Set client system PXE ports
                self.inv.add_nodes_ports_pxe(ports_pxe)

                # Set client system IPMI macs
                self.inv.add_nodes_macs_ipmi(macs_ipmi)
                # Set client system PXE macs
                self.inv.add_nodes_macs_pxe(macs_pxe)
                # Set client system IPMI apaddrs
                self.inv.add_nodes_ipaddrs_ipmi(ipaddrs_ipmi)
                # Set client system PXE ipaddrs
                self.inv.add_nodes_ipaddrs_pxe(ipaddrs_pxe)
                # Set client system PXE rename
                self.inv.add_nodes_rename_pxe(rename_pxe)

                # Set client system IPMI userids
                self.inv.add_nodes_userid_ipmi(cfg.get_ntmpl_ipmi_userid(
                    index_ntmplt))
                # Set client system IPMI passwords
                self.inv.add_nodes_password_ipmi(cfg.get_ntmpl_ipmi_password(
                    index_ntmplt))
                # Set PXE network device
                self.inv.add_nodes_devices_pxe(devices_pxe)

                ports_data = []
                switches_data = []
                macs_data = []
                devices_data = []
                rename_data = []
                # Iterate over data members
                for index_data in cfg.yield_ntmpl_phyintf_data_ind(
                        index_ntmplt):
                    # Create client system data switch list
                    switches_data.append(cfg.get_ntmpl_phyintf_data_switch(
                        index_ntmplt, index_data))
                    # Create client system data port list
                    ports_data.append(cfg.get_ntmpl_phyintf_data_ports(
                        index_ntmplt, index_data, index_port))
                    # Create client system data mac list
                    macs_data.append(None)
                    # Create client data network device list
                    devices_data.append(cfg.get_ntmpl_phyintf_data_dev(
                        index_ntmplt, index_data))
                    # Create client data device rename list
                    rename_data.append(cfg.get_ntmpl_phyintf_data_rename(
                        index_ntmplt, index_data))

                # Set client system data switches
                self.inv.add_nodes_switches_data(switches_data)
                # Set client system data ports
                self.inv.add_nodes_ports_data(ports_data)
                # Set client system data macs
                self.inv.add_nodes_macs_data(macs_data)
                # Set client system data devices
                self.inv.add_nodes_devices_data(devices_data)
                # Set client system data rename
                self.inv.add_nodes_rename_data(rename_data)
                index_host += 1

                interfaces = cfg.get_ntmpl_interfaces(index_ntmplt)
                interfaces, interface_ip_lists = _assign_interface_ips(
                    interfaces, interface_ip_lists)
                self.inv.add_nodes_interfaces(interfaces)
        self.log.info('Successfully created inventory file')


def _gen_interface_ip_lists(cfg):
    interface_ip_lists = {}
    interfaces = cfg.get_interfaces()

    for interface in interfaces:
        label = interface.label
        ip_list_prelim = []
        ip_list = []

        if 'address_list' in interface.keys():
            ip_list_prelim = interface.address_list
        elif 'IPADDR_list' in interface.keys():
            ip_list_prelim = interface.IPADDR_list

        for ip in ip_list_prelim:
            if '-' in ip:
                ip_range = ip.split('-')
                for _ip in iter_iprange(ip_range[0], ip_range[1]):
                    ip_list.append(str(_ip))
            else:
                ip_list.append(ip)

        if 'address_start' in interface.keys():
            ip_list = [IPAddress(interface.address_start)]
        elif 'IPADDR_start' in interface.keys():
            ip_list = [IPAddress(interface.IPADDR_start)]

        interface_ip_lists[label] = ip_list

    return interface_ip_lists


def _assign_interface_ips(interfaces, interface_ip_lists):
    for interface in interfaces:
        list_key = ''
        if 'address' in interface.keys():
            list_key = 'address'
        if 'IPADDR' in interface.keys():
            list_key = 'IPADDR'
        if list_key:
            try:
                ip = interface_ip_lists[interface.label].pop(0)
            except IndexError:
                raise UserException("Not enough IP addresses listed for "
                                    "interface \'%s\'" % interface.label)
            if isinstance(ip, IPAddress):
                interface[list_key] = str(ip)
                interface_ip_lists[interface.label].append(IPAddress(ip + 1))
            else:
                interface[list_key] = ip

    return interfaces, interface_ip_lists
