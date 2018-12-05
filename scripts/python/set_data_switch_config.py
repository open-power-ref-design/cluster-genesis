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
import os.path

from lib.inventory import Inventory
from lib.logger import Logger
from lib.switch import SwitchFactory
from write_switch_memory import WriteSwitchMemory

FILE_PATH = os.path.dirname(os.path.abspath(__file__))


class ConfigureDataSwitch(object):
    ENABLE_REMOTE_CONFIG = 'cli enable "configure terminal" "%s"'
    FORCE = 'force'
    SET_VLAN = 'vlan %d'
    SET_MTU = 'mtu %d'
    INTERFACE_ETHERNET = 'interface ethernet 1/%s'
    SWITCHPORT_MODE_HYBRID = 'switchport mode hybrid'
    SWITCHPORT_HYBRID_ALLOWED_VLAN = \
        'switchport hybrid allowed-vlan add %d'
    SHUTDOWN = 'shutdown'
    NO_SHUTDOWN = 'no shutdown'
    IP_ROUTING = 'ip routing'
    ENABLE_LACP = 'lacp'
    QOS_ENABLE = 'dcb priority-flow-control enable force'
    MLAG = 'protocol mlag'
    LAG_PORT_CHANNEL = 'interface port-channel %d'
    LACP = 'channel-group %d mode active'
    IPL = 'ipl 1'
    QOS_ON = 'dcb priority-flow-control mode on force'
    INTERFACE_VLAN = 'interface vlan %d'
    IP_CIDR = 'ip address %s'
    PEER_ADDR = 'peer-address %s'
    MLAG_VIP = 'mlag-vip my-mlag-vip-domain ip %s force'
    ENABLE_MLAG = 'no mlag shutdown'
    MLAG_PORT_CHANNEL = 'interface mlag-port-channel %d'
    STP_PORT_TYPE_EDGE = 'spanning-tree port type edge'
    STP_BPDUFILTER_ENABLE = 'spanning-tree bpdufilter enable'
    MLAG_ACTIVE = 'mlag-channel-group %d mode active'
    NO_CHANNEL_GROUP = 'no channel-group'

    def __init__(self, log, inv_file):
        self.inv = Inventory(log, inv_file)
        self.log = log
        self.userid = self.inv.get_userid_data_switch()
        self.password = self.inv.get_password_data_switch()
        self.switch_dict = {}
        self.switch_name = self.inv.get_data_switch_name()

        for ipv4 in self.inv.yield_data_switch_ip():
            self.switch_dict[ipv4] = self.switch = SwitchFactory.factory(
                log,
                self.switch_name,
                ipv4,
                self.userid,
                self.password,
                mode='active')

        for self.ipv4, userid, password, vlans in self.inv.yield_data_vlans(self.userid, self.password):
            for vlan in vlans:
                self.switch_dict[self.ipv4].create_vlan(vlan)

        switch_index = 0
        for self.ipv4, port_vlans, port_mtu, port_bonds \
                in self.inv.yield_data_switch_ports(self.userid, self.password):
            if port_bonds:
                for ports in port_bonds.values():
                    for port in ports:
                        # Set port mode and add VLANs
                        if port in port_vlans:
                            self.switch_dict[self.ipv4].add_vlans_to_port(port, port_vlans[port])
                        # Specify MTU
                        if port in port_mtu:
                            self.switch_dict[self.ipv4].set_mtu_for_port(port, port_mtu[port])
            else:
                for port, vlans in port_vlans.items():
                    # Set port mode and add VLANs
                    self.switch_dict[self.ipv4].set_switchport_mode('trunk', port)
                    self.switch_dict[self.ipv4].add_vlans_to_port(port, vlans)
                for port, mtu in port_mtu.items():
                    # Specify MTU
                    self.switch_dict[self.ipv4].set_mtu_for_port(port, mtu)

            if port_bonds:
                # Enable LACP
                self.switch_dict[self.ipv4].enable_lacp()
                # Configure port for MLAG
                if self.inv.is_mlag():
                    vlan = self.inv.get_mlag_vlan()
                    port_channel = self.inv.get_mlag_port_channel()
                    cidr_mlag_ipl = self.inv.get_cidr_mlag_ipl(switch_index)
                    ipaddr_mlag_ipl_peer = self.inv.get_ipaddr_mlag_ipl_peer(switch_index)
                    ipaddr_mlag_vip = self.inv.get_ipaddr_mlag_vip()
                    mlag_ports = self.inv.get_mlag_ports(switch_index)
                    self.switch_dict[self.ipv4].configure_mlag(
                        vlan,
                        port_channel,
                        cidr_mlag_ipl,
                        ipaddr_mlag_ipl_peer,
                        ipaddr_mlag_vip,
                        mlag_ports)
                    for port_channel, ports in port_bonds.items():
                        # Remove any channel-group from port
                        self.switch_dict[self.ipv4].remove_channel_group(ports[0])
                        self.switch_dict[self.ipv4].create_mlag_interface(port_channel)
                        if ports[0] in port_vlans:
                            self.switch_dict[self.ipv4].add_vlans_to_mlag_port_channel(
                                port_channel, port_vlans[ports[0]])
                        if ports[0] in port_mtu:
                            self.switch_dict[self.ipv4].set_mtu_for_mlag_port_channel(
                                port_channel, port_mtu[ports[0]])
                        self.switch_dict[self.ipv4].bind_port_to_mlag_interface(port_channel)
                    # Enable MLAG
                    self.switch_dict[self.ipv4].enable_mlag()
                # Configure port for LAG
                else:
                    for port_channel, ports in port_bonds.items():
                        for port in ports:
                            self.switch_dict[self.ipv4].remove_channel_group(port)
                        if ports[0] in port_vlans:
                            self.switch_dict[self.ipv4].add_vlans_to_lag_port_channel(
                                port_channel, port_vlans[ports[0]])
                        if ports[0] in port_mtu:
                            self.switch_dict[self.ipv4].set_mtu_for_lag_port_channel(
                                port_channel, port_mtu[ports[0]])
                        self.switch_dict[self.ipv4].create_lag(port_channel)
                        self.switch_dict[self.ipv4].activate_lag(port_channel, ports)

            switch_index += 1

        if self.inv.is_write_switch_memory():
            switch = WriteSwitchMemory(LOG, INV_FILE)
            switch.write_data_switch_memory()


if __name__ == '__main__':
    """
    Arg1: inventory file
    Arg2: log level
    """
    LOG = Logger(__file__)

    if len(sys.argv) != 3:
        try:
            raise Exception()
        except:
            LOG.error('Invalid argument count')
            sys.exit(1)

    INV_FILE = sys.argv[1]
    LOG.set_level(sys.argv[2])

    ConfigureDataSwitch(LOG, INV_FILE)
