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
                if 'bond_master' in _ifc and _ifc['bond_master'] == ifc['iface']:
                    if ifc['label'] in bond_ifcs:
                        bond_ifcs[ifc['label']].append(_ifc['label'])
                    else:
                        bond_ifcs[ifc['label']] = [_ifc['label']]
        elif 'BONDING_MASTER' in ifc:
            for _ifc in ifcs:
                if 'MASTER' in _ifc and _ifc['MASTER'] == ifc['DEVICE']:
                    if ifc['label'] in bond_ifcs:
                        bond_ifcs[ifc['label']].append(_ifc['label'])
                    else:
                        bond_ifcs[ifc['label']] = [_ifc['label']]

    pretty_str = PP.pformat(bond_ifcs)
    log.debug('bond_ifcs')
    log.debug('\n' + pretty_str)

    # Gather bond node template, switch and port information
    bonds = Tree()

    for bond in bond_ifcs:
        for ntmpl_ind, ntmpl_label in enumerate(CFG.yield_ntmpl_label()):
            ntmpl_ifcs = CFG.get_ntmpl_ifcs_all(ntmpl_ind)
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
    pretty_str = PP.pformat(bonds)
    log.debug('Bonds:')
    log.debug('\n' + pretty_str)

    # For each bond, aggregate ports across node templates and group into port
    # channel groups
    ports_list = Tree()
    for bond in bonds:
        for ntmpl in bonds[bond]:
            bond_ports_list = Tree()
            for ifc in bonds[bond][ntmpl]:
                for switch in bonds[bond][ntmpl][ifc]:
                    ports = bonds[bond][ntmpl][ifc][switch]
                    if switch not in bond_ports_list:
                        bond_ports_list[switch] = [ports]
                    else:
                        bond_ports_list[switch].append(ports)
            for switch in bond_ports_list:
                # group the ports into channel groups
                if switch not in ports_list[bond][ntmpl]:
                    ports_list[bond][ntmpl][switch] = zip(*bond_ports_list[switch])
                else:
                    ports_list[bond][ntmpl][switch] += zip(*bond_ports_list[switch])

    pretty_str = PP.pformat(ports_list)
    log.debug('ports_list:')
    log.debug('\n' + pretty_str)

    chan_ports = Tree()
    # Aggregate port groups across switches or mlag switch pairs.
    # Final data structure is a dictionary organized by bond, node template,
    # switch / switch pair.
    for bond in ports_list:
        for ntmpl in ports_list[bond]:
            for switch in ports_list[bond][ntmpl]:
                peer_switch = CFG.get_sw_data_mlag_peer(switch)
                mstr_switch = CFG.get_sw_data_mstr_switch([switch, peer_switch])
                chan_ports[bond][ntmpl][mstr_switch][switch] = \
                    ports_list[bond][ntmpl][switch]
    pretty_str = PP.pformat(chan_ports)
    log.debug('Port channel ports:')
    log.debug('\n' + pretty_str)
    return chan_ports


def _get_vlan_info(ifc):
    ifcs = CFG.get_interfaces()
    vlan_num = None
    vlan_ifc_name = ''

    for _ifc in ifcs:
        if _ifc['label'] == ifc:
            if 'vlan_raw_device' in _ifc:
                vlan_num = int(_ifc['iface'].rpartition('.')[2])
                vlan_ifc_name = _ifc['vlan_raw_device']
                break
            elif 'VLAN' in _ifc:
                vlan_num = int(_ifc['DEVICE'].rpartition('.')[2])
                vlan_ifc_name = _ifc['DEVICE'].rpartition('.')[0]
                break
    return vlan_num, vlan_ifc_name


def _get_vlan_slaves(vlan_ifc_name):
    ifcs = CFG.get_interfaces()
    vlan_slaves = []

    for _ifc in ifcs:
        if 'bond_master' in _ifc and _ifc['bond_master'] == vlan_ifc_name:
            vlan_slaves.append(_ifc['label'])
        elif 'MASTER' in _ifc and _ifc['MASTER'] == vlan_ifc_name:
            vlan_slaves.append(_ifc['label'])
    return vlan_slaves


def _get_vlan_list():
    """ Aggregate vlan data.
    Args:
    Returns:
        Tree of switches and vlan information by port
    """
    log = logger.getlogger()

    vlan_list = Tree()
    for ntmpl_ind in CFG.yield_ntmpl_ind():
        ntmpl_ifcs = CFG.get_ntmpl_ifcs_all(ntmpl_ind)
        for ifc in ntmpl_ifcs:
            vlan_num, vlan_ifc_name = _get_vlan_info(ifc)
            if vlan_num:
                vlan_slaves = _get_vlan_slaves(vlan_ifc_name)
                for phyintf_idx in CFG.yield_ntmpl_phyintf_data_ind(ntmpl_ind):
                    phy_ifc_lbl = CFG.get_ntmpl_phyintf_data_ifc(ntmpl_ind, phyintf_idx)
                    if phy_ifc_lbl in vlan_slaves:
                        vlan_ports = CFG.get_ntmpl_phyintf_data_ports(
                            ntmpl_ind, phyintf_idx)
                        switch = CFG.get_ntmpl_phyintf_data_switch(
                            ntmpl_ind, phyintf_idx)
                        if vlan_num in vlan_list[switch]:
                            vlan_list[switch][vlan_num] += vlan_ports
                        else:
                            vlan_list[switch][vlan_num] = vlan_ports

    pretty_str = PP.pformat(vlan_list)
    log.debug('vlan list')
    log.debug('\n' + pretty_str)

    # Aggregate by switch and port number
    port_vlans = Tree()
    for switch in vlan_list:
        for vlan in vlan_list[switch]:
            for port in vlan_list[switch][vlan]:
                if port in port_vlans[switch]:
                    port_vlans[switch][port].append(vlan)
                else:
                    port_vlans[switch][port] = [vlan]

    pretty_str = PP.pformat(port_vlans)
    log.debug('port_vlans')
    log.debug('\n' + pretty_str)

    return port_vlans


def _get_mtu_list():
    """ Aggregate mtu port data.
    Returns: Dictionary of {switch : {port : mtu value, ...}}
    """
    log = logger.getlogger()

    mtu_list = Tree()
    for ntmpl_ind in CFG.yield_ntmpl_ind():
        for phyintf_idx in CFG.yield_ntmpl_phyintf_data_ind(ntmpl_ind):
            mtu = ''
            phy_ifc = CFG.get_ntmpl_phyintf_data_ifc(ntmpl_ind, phyintf_idx)
            ifc = CFG.get_interface(phy_ifc)
            if 'mtu' in ifc:
                mtu = ifc['mtu']
            elif 'MTU' in ifc:
                mtu = ifc['MTU']
            if mtu:
                switch = CFG.get_ntmpl_phyintf_data_switch(ntmpl_ind, phyintf_idx)
                ports = CFG.get_ntmpl_phyintf_data_ports(ntmpl_ind, phyintf_idx)
                if switch in mtu_list and mtu in mtu_list[switch]:
                    mtu_list[switch][mtu] += ports
                else:
                    mtu_list[switch][mtu] = ports
    pretty_str = PP.pformat(mtu_list)
    log.debug('mtu_list')
    log.debug('\n' + pretty_str)

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
    pretty_str = PP.pformat(mlag_list)
    log.debug('mlag_list')
    log.debug('\n' + pretty_str)

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
        vlans = []
        for port in port_vlans[switch]:
            for vlan in port_vlans[switch][port]:
                if vlan not in vlans:
                    vlans.append(vlan)
                    sw_dict[switch].create_vlan(vlan)
                    log.debug('Creating vlan {} on switch {}'.format(vlan, switch))
            sw_dict[switch].set_switchport_mode('trunk', port)
            sw_dict[switch].add_vlans_to_port(port, port_vlans[switch][port])
            log.debug('switch: {} port: {} vlans: {}'.format(
                switch, port, port_vlans[switch][port]))

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
            if not sw_dict[sw].is_mlag_configured():
                log.debug('Configuring MLAG on switch {}'.format(sw))
                sw_dict[sw].configure_mlag(
                    mlag_list[mstr_sw][sw]['vlan'],
                    min(mlag_list[mstr_sw][mstr_sw]['ports']),
                    mlag_list[mstr_sw][sw]['cidr'],
                    mlag_list[mstr_sw][sw]['peer_ip'],
                    mlag_list[mstr_sw][sw]['vip'],
                    mlag_list[mstr_sw][sw]['ports'])
            else:
                log.info('MLAG already configured. Skipping'
                         ' MLAG configuration on switch {}.'.format(sw))
        for sw in mlag_list[mstr_sw]:
            if sw_dict[sw].is_mlag_configured():
                sw_dict[sw].enable_mlag()

    # Configure port channels and MLAG port channels
    for bond in chan_ports:
        for ntmpl in chan_ports[bond]:
            for mstr_sw in chan_ports[bond][ntmpl]:
                if len(chan_ports[bond][ntmpl][mstr_sw]) == 2:
                    # MLAG
                    for sw in chan_ports[bond][ntmpl][mstr_sw]:
                        for idx, port_grp in enumerate(
                                chan_ports[bond][ntmpl][mstr_sw][sw]):
                            chan_num = min(chan_ports[bond][ntmpl][mstr_sw]
                                           [mstr_sw][idx])
                            sw_dict[sw].remove_mlag_interface(chan_num)
                            sw_dict[sw].create_mlag_interface(chan_num)
                            log.debug('create mlag interface {} on switch {}'.
                                      format(chan_num, sw))
                            # All ports in a port group should have the same vlans
                            # So use any one for setting the MLAG port channel vlans
                            vlan_port = chan_ports[bond][ntmpl][mstr_sw][sw][idx]
                            vlan_port = min(vlan_port)
                            vlans = _get_port_vlans(sw, vlan_port, port_vlans)
                            mtu = _get_port_mtu(sw, chan_num, mtu_list)
                            if vlans:
                                log.debug('Switch {}, add vlans {} to mlag port '
                                          'channel {}.'.format(sw, vlans, chan_num))
                                sw_dict[sw].add_vlans_to_mlag_port_channel(
                                    chan_num, vlans)
                            if mtu:
                                log.debug('set_mtu_for_mlag_port_channel: {}'.
                                          format(mtu))
                                sw_dict[sw].set_mtu_for_lag_port_channel(
                                    chan_num, mtu)
                            for port in port_grp:
                                log.debug('Switch {}, adding port {} to mlag chan '
                                          'num: {}'.format(sw, port, chan_num))
                                sw_dict[sw].bind_port_to_mlag_interface(
                                    port, chan_num)
                else:
                    # Configure LAG
                    for sw in chan_ports[bond][ntmpl][mstr_sw]:
                        for port_grp in chan_ports[bond][ntmpl][mstr_sw][sw]:
                            chan_num = min(port_grp)
                            log.debug('Lag channel group: {} on switch: {}'.format(
                                chan_num, sw))
                            sw_dict[sw].remove_channel_group(chan_num)
                            sw_dict[sw].create_lag_interface(chan_num)
                            vlans = _get_port_vlans(sw, chan_num, port_vlans)
                            mtu = _get_port_mtu(sw, chan_num, mtu_list)
                            if vlans:
                                log.debug('switch {}, add vlans {} to lag port '
                                          'channel {}'.format(sw, vlans, chan_num))
                                sw_dict[sw].add_vlans_to_lag_port_channel(
                                    chan_num, vlans)
                            if mtu:
                                log.debug('set mtu for lag port channel: {}'.format(mtu))
                                sw_dict[sw].set_mtu_for_lag_port_channel(chan_num, mtu)
                            sw_dict[sw].bind_ports_to_lag_interface(port_grp, chan_num)


def deconfigure_data_switch():
    """ Deconfigures data (access) switches.  Deconfiguration is driven by the
    config.yml file. Generally deconfiguration is done in reverse order of
    configuration.
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

    # Deconfigure channel ports and MLAG channel ports
    for bond in chan_ports:
        for ntmpl in chan_ports[bond]:
            for mstr_sw in chan_ports[bond][ntmpl]:
                if len(chan_ports[bond][ntmpl][mstr_sw]) == 2:
                    # Deconfigure mlag channel ports
                    for sw in chan_ports[bond][ntmpl][mstr_sw]:
                        if sw_dict[sw].is_mlag_configured():
                            for idx, port_grp in enumerate(chan_ports[bond][ntmpl]
                                                           [mstr_sw][sw]):
                                chan_num = min(chan_ports[bond][ntmpl][mstr_sw]
                                               [mstr_sw][idx])
                                log.info('Deleting mlag interface: {} on'
                                         ' switch: {}'.format(chan_num, sw))
                                sw_dict[sw].remove_mlag_interface(chan_num)
                else:
                    # deconfigure LAG channel ports
                    for sw in chan_ports[bond][ntmpl][mstr_sw]:
                        for port_grp in chan_ports[bond][ntmpl][mstr_sw][sw]:
                            chan_num = min(port_grp)
                            log.debug('Deleting Lag interface {} on switch: {}'.format(
                                      chan_num, sw))
                            sw_dict[sw].remove_lag_interface(chan_num)
    # Deconfigure MLAG
    for mstr_sw in mlag_list:
        for sw in mlag_list[mstr_sw]:
            if sw_dict[sw].is_mlag_configured():
                print('\n\nAbout to deconfigure MLAG on switch {}'.format(sw))
                print('This will stop all MLAG communication on all switch ports')
                print('OK to deconfigure MLAG?')
                resp = raw_input("Enter (Y/yes/n): ")
                if resp in ['Y', 'yes']:
                    log.debug('Deconfiguring MLAG on switch: {}'.format(sw))
                    sw_dict[sw].deconfigure_mlag()
            else:
                log.debug('\nMLAG not configured on switch: {}'.format(sw))

    # Deconfigure switch vlans - first remove from ports
    for switch in port_vlans:
        for port in port_vlans[switch]:
            for vlan in port_vlans[switch][port]:
                log.debug('port: {} removing vlans: {}'.format(
                          port, port_vlans[switch][port]))
                sw_dict[switch].remove_vlans_from_port(port, vlan)
                log.debug('Switch {}, setting port: {} to access mode'.format(
                    switch, port))
                sw_dict[switch].set_switchport_mode('access', port)
    # Delete the vlans
    for switch in port_vlans:
        vlans = []
        for port in port_vlans[switch]:
            for vlan in port_vlans[switch][port]:
                if vlan not in vlans:
                    vlans.append(vlan)
                    sw_dict[switch].delete_vlan(vlan)
                    log.debug('Switch {}, deleting vlan {}'.format(switch, vlan))

    # Deconfigure switch mtu
    for switch in mtu_list:
        for mtu in mtu_list[switch]:
            for port in mtu_list[switch][mtu]:
                sw_dict[switch].set_mtu_for_port(port, 0)
                log.debug('port: {} setting mtu: {}'.format(port, 'default mtu'))


def gather_and_display():
    port_vlans = _get_vlan_list()
    mtu_list = _get_mtu_list()
    chan_ports = _get_port_chan_list()
    mlag_list = _get_mlag_info()

    print('\n\nport_vlans:')
    PP.pprint(port_vlans)
    print('\nmtu_list:')
    PP.pprint(mtu_list)
    print('\nmlag_list:')
    PP.pprint(mlag_list)
    print('\nchan_ports:')
    PP.pprint(chan_ports)

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
