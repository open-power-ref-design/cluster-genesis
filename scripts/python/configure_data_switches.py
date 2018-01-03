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

import os
import sys
import pprint

import lib.logger as logger
from lib.config import Config
from lib.switch import SwitchFactory
# from write_switch_memory import WriteSwitchMemory

FILE_PATH = os.path.dirname(os.path.abspath(__file__))
CFG = Config()
PP = pprint.PrettyPrinter(indent=1, width=120)


class Tree(dict):
    """Instantiates a nested dictionary which allows assignment to arbitrary
    depths.
    """
    def __getitem__(self, key):
        if key in self:
            return self.get(key)
        return self.setdefault(key, Tree())


def _get_port_chan_list():
    """
    Args:

    Returns:
        Tree of switches and port channels or mlag port channels.  Switches in
        an MLAG are grouped in pairs.
    """
    log = logger.getlogger()

    ifcs = CFG.get_interfaces()

    # Gather bond definintions from interfaces list
    bond_ifcs = {}
    for ifc in ifcs:
        if 'bond_mode' in ifc:
            for _ifc in ifcs:
                if 'bond_master' in _ifc and _ifc['bond_master'] == ifc['label']:
                    if ifc['label'] in bond_ifcs:
                        bond_ifcs[ifc['label']].append(_ifc['label'])
                    else:
                        bond_ifcs[ifc['label']] = [_ifc['label']]

    # print('bond_ifcs')
    pretty_str = PP.pformat(bond_ifcs)
    log.debug('bond_ifcs')
    log.debug('\n' + pretty_str)
    # print(pretty_str)

    # Gather bond node template, switch and port information
    bonds = Tree()
    for ntmpl_ind, ntmpl_label in enumerate(CFG.yield_ntmpl_label()):
        ntmpl_ifcs = CFG.get_ntmpl_ifcs_all(ntmpl_ind)
        for bond in bond_ifcs:
            if bond in ntmpl_ifcs:
                for phyintf_idx in CFG.yield_ntmpl_phyintf_data_ind(ntmpl_ind):
                    phyintf = CFG.get_ntmpl_phyintf_data_ifc(
                        ntmpl_ind, phyintf_idx)
                    if phyintf in bond_ifcs[bond]:
                        switch = CFG.get_ntmpl_phyintf_data_switch(
                            ntmpl_ind, phyintf_idx)
                        ports = CFG.get_ntmpl_phyintf_data_ports(
                            ntmpl_ind, phyintf_idx)
                        bonds[bond][ntmpl_label][phyintf][switch] = ports

    # print(' Bonds')
    pretty_str = PP.pformat(bonds)
    log.debug('Bonds:')
    log.debug('\n' + pretty_str)
    # print(pretty_str)

    # Aggregate ports across node templates and group into port channel groups
    ports_list = Tree()
    for bond in bonds:
        for ntmpl in bonds[bond]:
            for ifc in bonds[bond][ntmpl]:
                for switch in bonds[bond][ntmpl][ifc]:
                    ports = bonds[bond][ntmpl][ifc][switch]
                    if ntmpl not in ports_list or switch not in ports_list[ntmpl]:
                        ports_list[ntmpl][switch] = [ports]
                    else:
                        ports_list[ntmpl][switch].append(ports)
            for switch in ports_list[ntmpl]:
                # group the ports into channel groups
                ports_list[ntmpl][switch] = zip(*ports_list[ntmpl][switch])

    chan_ports = Tree()
    # Aggregate port groups across switches or mlag switch pairs.
    # Final data structure is a dictionary organized by switch / switch pair.
    # The top level keys are the 'master' switch if mlag is specified
    # or simply the switch if mlag is not specified.
    for ntmpl in ports_list:
        for switch in ports_list[ntmpl]:
            peer_switch = CFG.get_sw_data_mlag_peer(switch)
            mstr_switch = CFG.get_sw_data_mstr_switch([switch, peer_switch])
            if switch == mstr_switch or \
                    switch == CFG.get_sw_data_mlag_peer(mstr_switch):
                if switch not in chan_ports[mstr_switch]:
                    chan_ports[mstr_switch][switch] = \
                        ports_list[ntmpl][switch]
                else:
                    chan_ports[mstr_switch][switch] += ports_list[ntmpl][switch]

    # print()
    # print('Port channel ports')
    pretty_str = PP.pformat(chan_ports)
    log.debug('Port channel ports:')
    log.debug('\n' + pretty_str)
    # print(pretty_str)
    return chan_ports


def _get_vlan_list():
    """ Aggregate vlan data.
    Args:
    Returns:
        Tree of switches and vlan information by port
    """
    log = logger.getlogger()
    ifcs = CFG.get_interfaces()

    vlan_list = Tree()
    for ntmpl_ind in CFG.yield_ntmpl_ind():
        ntmpl_ifcs = CFG.get_ntmpl_ifcs_all(ntmpl_ind)
        for phyintf_idx in CFG.yield_ntmpl_phyintf_data_ind(ntmpl_ind):
            phy_ifc_lbl = CFG.get_ntmpl_phyintf_data_ifc(ntmpl_ind, phyintf_idx)
            if phy_ifc_lbl in ntmpl_ifcs:
                ifc = CFG.get_interface(phy_ifc_lbl)
                if 'bond_master' in ifc:
                    bond_label = ifc['bond_master']
                    for _ifc in ifcs:
                        if 'vlan_raw_device' in _ifc and \
                                _ifc['vlan_raw_device'] == bond_label:
                            switch = CFG.get_ntmpl_phyintf_data_switch(
                                ntmpl_ind, phyintf_idx)
                            vlan_num = int(_ifc['iface'].rpartition('.')[2])
                            vlan_ports = CFG.get_ntmpl_phyintf_data_ports(
                                ntmpl_ind, phyintf_idx)
                            if vlan_num in vlan_list[switch]:
                                vlan_list[switch][vlan_num] += vlan_ports
                            else:
                                vlan_list[switch][vlan_num] = vlan_ports
            else:
                for _ifc in ifcs:
                    if _ifc['label'] in ntmpl_ifcs and 'vlan_raw_device' in _ifc \
                            and _ifc['vlan_raw_device'] == phy_ifc_lbl:
                        switch = CFG.get_ntmpl_phyintf_data_switch(
                            ntmpl_ind, phyintf_idx)
                        vlan_num = int(_ifc['iface'].rpartition('.')[2])
                        vlan_ports = CFG.get_ntmpl_phyintf_data_ports(
                            ntmpl_ind, phyintf_idx)
                        if vlan_num in vlan_list[switch]:
                            vlan_list[switch][vlan_num] += vlan_ports
                        else:
                            vlan_list[switch][vlan_num] = vlan_ports

    # print()
    # print('vlan list')
    pretty_str = PP.pformat(vlan_list)
    log.debug('vlan list')
    log.debug('\n' + pretty_str)
    # PP.pprint(vlan_list)

    # Aggregate by switch and port number
    port_vlans = Tree()
    for switch in vlan_list:
        for vlan in vlan_list[switch]:
            for port in vlan_list[switch][vlan]:
                if port in port_vlans[switch]:
                    port_vlans[switch][port].append(vlan)
                else:
                    port_vlans[switch][port] = [vlan]

    # print('port_vlans')
    pretty_str = PP.pformat(port_vlans)
    log.debug('port_vlans')
    log.debug('\n' + pretty_str)
    # print(pretty_str)
    return port_vlans


def _get_mtu_list():
    """ Aggregate mtu port data.
    Returns: Dictionary of {switch : {port : mtu value, ...}}
    """
    log = logger.getlogger()

    mtu_list = Tree()
    for ntmpl_ind in CFG.yield_ntmpl_ind():
        for phyintf_idx in CFG.yield_ntmpl_phyintf_data_ind(ntmpl_ind):
            phy_ifc = CFG.get_ntmpl_phyintf_data_ifc(ntmpl_ind, phyintf_idx)
            ifc = CFG.get_interface(phy_ifc)
            if 'mtu' in ifc:
                mtu = ifc['mtu']
                switch = CFG.get_ntmpl_phyintf_data_switch(ntmpl_ind, phyintf_idx)
                ports = CFG.get_ntmpl_phyintf_data_ports(ntmpl_ind, phyintf_idx)
                if switch in mtu_list and mtu in mtu_list[switch]:
                    mtu_list[switch][mtu] += ports
                else:
                    mtu_list[switch][mtu] = ports
    # print('mtu_list')
    pretty_str = PP.pformat(mtu_list)
    log.debug('mtu_list')
    log.debug('\n' + pretty_str)
    # print(pretty_str)
    return mtu_list


def _get_mlag_info():
    """ Get mlag switches and their config info
    Returns:
        dict of : mlag config info
    """
    log = logger.getlogger()

    mlag_list = Tree()
    for sw_lbl in CFG.yield_sw_data_label():
        peer_lbl = CFG.get_sw_data_mlag_peer(sw_lbl)
        mstr_sw = CFG.get_sw_data_mstr_switch([sw_lbl, peer_lbl])
        if peer_lbl and mstr_sw == sw_lbl and mstr_sw not in mlag_list:
            mlag_list[mstr_sw][sw_lbl]
            mlag_list[mstr_sw][peer_lbl]

    for mstr_sw in mlag_list:
        for sw in mlag_list[mstr_sw]:
            sw_idx = CFG.get_sw_data_index_by_label(sw)
            for link_idx, link in enumerate(CFG.yield_sw_data_links_target(sw_idx)):
                if link in mlag_list[mstr_sw]:
                    mlag_list[mstr_sw][sw]['vlan'] = \
                        CFG.get_sw_data_links_vlan(sw_idx, link_idx)
                    if sw == mstr_sw:
                        mlag_list[mstr_sw][sw]['vip'] = None
                    else:
                        mlag_list[mstr_sw][sw]['vip'] = \
                            CFG.get_sw_data_links_vip(sw_idx, link_idx) + ' /' + \
                            str(CFG.get_depl_netw_mgmt_prefix()[0])
                    mlag_list[mstr_sw][sw]['ports'] = \
                        CFG.get_sw_data_links_port(sw_idx, link_idx)
                    mlag_list[mstr_sw][sw]['cidr'] = \
                        CFG.get_sw_data_links_ip(sw_idx, link_idx) + ' /' + \
                        str(CFG.get_sw_data_links_prefix(sw_idx, link_idx))
                    if len(mlag_list[mstr_sw]) == 2:
                        keys = sorted(mlag_list[mstr_sw].keys())
                        mlag_list[mstr_sw][keys[0]]['peer_ip'] = \
                            str(mlag_list[mstr_sw][keys[1]]['cidr']).split(' /')[0]
                        mlag_list[mstr_sw][keys[1]]['peer_ip'] = \
                            str(mlag_list[mstr_sw][keys[0]]['cidr']).split(' /')[0]
                    break
    # print('mlag_list')
    pretty_str = PP.pformat(mlag_list)
    log.debug('mlag_list')
    log.debug('\n' + pretty_str)
    # print(pretty_str)

    return mlag_list


def _is_port_in_a_port_channel(switch, port, chan_ports):
    """ Returns True if port in a port channel, else returns False.
    Args:
        switch (str): switch label
        port (int or str): port number
    """
    for sw in chan_ports:
        for _sw in chan_ports[sw]:
            if switch == _sw:
                for port_group in chan_ports[sw][_sw]:
                    if port in port_group:
                        return True
                        break
    return False


def _get_port_vlans(switch, port, port_vlans):
    if port in port_vlans[switch]:
        return port_vlans[switch][port]


def _get_port_mtu(switch, port, mtu_list):
    for mtu in mtu_list[switch]:
        if port in mtu_list[switch][mtu]:
            return mtu


def configure_data_switch():
    """ Configures data (access) switches.  Configuration is driven by the
    config.yml file.
    Args:

    Returns:
    """
    log = logger.getlogger()

    port_vlans = _get_vlan_list()
    mtu_list = _get_mtu_list()
    chan_ports = _get_port_chan_list()
    mlag_list = _get_mlag_info()

    # Create switch class instances for each switch
    sw_dict = {}
    for sw_ai in CFG.yield_sw_data_access_info():
        label = sw_ai[0]
        sw_dict[label] = SwitchFactory.factory(*sw_ai[1:])

    # Program switch vlans
    for switch in port_vlans:
        for port in port_vlans[switch]:
            if not _is_port_in_a_port_channel(switch, port, chan_ports):
                sw_dict[switch].set_switchport_mode('trunk', port)
                log.debug('port: {} setting trunk mode'.format(port))
            sw_dict[switch].add_vlans_to_port(port, port_vlans[switch][port])
            log.debug('port: {} vlans: {}'.format(port, port_vlans[switch][port]))

    # Program switch mtu
    for switch in mtu_list:
        for mtu in mtu_list[switch]:
            for port in mtu_list[switch][mtu]:
                sw_dict[switch].set_mtu_for_port(port, mtu)
                log.debug('port: {} set mtu: {}'.format(port, mtu))

    # Configure MLAG
    for mstr_sw in mlag_list:
        log.debug('Configuring MLAG.  mlag switch mstr: ' + mstr_sw)
        for sw in mlag_list[mstr_sw]:
            log.debug('Configuring MLAG on switch {}'.format(sw))
            sw_dict[sw].configure_mlag(
                mlag_list[mstr_sw][sw]['vlan'],
                min(mlag_list[mstr_sw][mstr_sw]['ports']),
                mlag_list[mstr_sw][sw]['cidr'],
                mlag_list[mstr_sw][sw]['peer_ip'],
                mlag_list[mstr_sw][sw]['vip'],
                mlag_list[mstr_sw][sw]['ports'])
        for sw in mlag_list[mstr_sw]:
            sw_dict[sw].enable_mlag()

    for mstr_sw in chan_ports:
        if len(chan_ports[mstr_sw]) == 2:
            # MLAG
            for sw in chan_ports[mstr_sw]:
                for idx, port_grp in enumerate(chan_ports[mstr_sw][sw]):
                    chan_num = min(chan_ports[mstr_sw][mstr_sw][idx])
                    sw_dict[sw].remove_mlag_channel_group(chan_num)
                    sw_dict[sw].create_mlag_interface(chan_num)
                    log.debug('create mlag interface: {} on switch: {}'.format(
                        chan_num, sw))
                    vlans = _get_port_vlans(sw, chan_num, port_vlans)
                    mtu = _get_port_mtu(sw, chan_num, mtu_list)
                    if vlans:
                        log.debug('add_vlans_to_mlag_port_channel: {}'.format(vlans))
                        sw_dict[sw].add_vlans_to_mlag_port_channel(chan_num, vlans)
                    if mtu:
                        log.debug('set_mtu_for_mlag_port_channel: {}'.format(mtu))
                        sw_dict[sw].set_mtu_for_lag_port_channel(chan_num, mtu)
                    for port in port_grp:
                        log.debug('Adding port {} to mlag chan num: {}'.format(
                            port, chan_num))
                        sw_dict[sw].bind_port_to_mlag_interface(port, chan_num)
        else:
            # Configure LAG
            # NOT COMPLETE
            for port_grp in chan_ports[mstr_sw][mstr_sw]:
                chan_num = min(port_grp)
                log.debug('Lag channel group: {} on switch: {}'.format(
                    chan_num, mstr_sw))
                sw_dict[sw].remove_channel_group(chan_num)
                sw_dict[sw].create_lag_interface(chan_num)
                vlans = _get_port_vlans(mstr_sw, chan_num, port_vlans)
                mtu = _get_port_mtu(mstr_sw, chan_num, mtu_list)
                if vlans:
                    log.debug('add_vlans_to_lag_port_channel: {}'.format(vlans))
                    sw_dict[sw].add_vlans_to_lag_port_channel(chan_num, vlans)
                if mtu:
                    log.debug('set_mtu_for_lag_port_channel: {}'.format(mtu))
                    sw_dict[sw].set_mtu_for_lag_port_channel(chan_num, mtu)
                for port in port_grp:
                    log.debug('Adding port {} to mlag chan num: {}'.format(
                        port, chan_num))
                    sw_dict[sw].bind_port_to_lag_interface(port, chan_num)
            sw_dict[sw].activate_lag_interface(chan_num)


def deconfigure_data_switch():
    """ Deconfigures data (access) switches.  Deconfiguration is driven by the
    config.yml file.
    Args:

    Returns:
    """
    log = logger.getlogger()

    port_vlans = _get_vlan_list()
    mtu_list = _get_mtu_list()
    chan_ports = _get_port_chan_list()
    mlag_list = _get_mlag_info()

    # Create switch class instances for each switch
    sw_dict = {}
    for sw_ai in CFG.yield_sw_data_access_info():
        label = sw_ai[0]
        sw_dict[label] = SwitchFactory.factory(*sw_ai[1:])

    # Deconfigure channel ports
    for mstr_sw in chan_ports:
        if len(chan_ports[mstr_sw]) == 2:
            # Deconfigure mlag channel ports
            for sw in chan_ports[mstr_sw]:
                for idx, port_grp in enumerate(chan_ports[mstr_sw][sw]):
                    chan_num = min(chan_ports[mstr_sw][mstr_sw][idx])
                    log.debug('Delete mlag interface: {} on switch: {}'.format(
                        chan_num, sw))
                    sw_dict[sw].remove_mlag_interface(chan_num)
        else:
            # deconfigure LAG channel ports
            for port_grp in chan_ports[mstr_sw][mstr_sw]:
                chan_num = min(port_grp)
                log.debug('Deleting Lag interface {} on switch: {}'.format(
                          chan_num, mstr_sw))
                sw_dict[sw].remove_lag_interface(chan_num)

    # Deconfigure MLAG
    for mstr_sw in mlag_list:
        log.debug('Deconfiguring MLAG. mlag switch mstr: ' + mstr_sw)
        for sw in mlag_list[mstr_sw]:
            mlag_ifcs = sw_dict[sw].show_mlag_interfaces()
            if "Unrecognized command" in mlag_ifcs:
                log.debug('\nMLAG not configured on switch: {}'.format(sw))
            else:
                log.debug('Deconfiguring MLAG on switch: {}'.format(sw))
                sw_dict[sw].deconfigure_mlag()

    # Deconfigure switch vlans
    for switch in port_vlans:
        for port in port_vlans[switch]:
            if not _is_port_in_a_port_channel(switch, port, chan_ports):
                sw_dict[switch].set_switchport_mode('access', port)
                log.debug('setting port: {} to access mode'.format(port))
            sw_dict[switch].remove_vlans_to_port(port, port_vlans[switch][port])
            log.debug('port: {} removing vlans: {}'.format(
                port, port_vlans[switch][port]))

    # Deconfigure switch mtu
    for switch in mtu_list:
        for mtu in mtu_list[switch]:
            for port in mtu_list[switch][mtu]:
                sw_dict[switch].set_mtu_for_port(port, 0)
                log.debug('port: {} setting mtu: {}'.format(port, 'default mtu'))


def gather_and_display():
    port_vlans = _get_vlan_list()
    print('\n\nport_vlans:')
    PP.pprint(port_vlans)
    mtu_list = _get_mtu_list()
    print('\nmtu_list:')
    PP.pprint(mtu_list)
    chan_ports = _get_port_chan_list()
    print('\nchan_ports:')
    PP.pprint(chan_ports)
    mlag_list = _get_mlag_info()
    print('\nmlag_list:')
    PP.pprint(mlag_list)

#        if self.cfg.is_write_switch_memory():
#            switch = WriteSwitchMemory(LOG, INV_FILE)
#            switch.write_data_switch_memory()


if __name__ == '__main__':
    """ Configures or deconfigures data switches.
    Args: optional log level or optional deconfig in any order
    """

    log_lvl = list(set(['info', 'debug', 'warning']).intersection(set(sys.argv)))
    if log_lvl:
        logger.create(log_lvl[0], log_lvl[0])
    else:
        logger.create('info', 'info')

    if 'gather' in sys.argv:
        gather_and_display()
        sys.exit()

    if any([x in ['deconfigure', 'deconfig', 'de'] for x in sys.argv]):
        deconfigure_data_switch()
    elif log_lvl or len(sys.argv) == 1:
        configure_data_switch()
