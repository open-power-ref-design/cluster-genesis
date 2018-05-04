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
import os
import re
import subprocess
import platform
from pyroute2 import IPRoute

from lib.config import Config
import lib.logger as logger

IPR = IPRoute()


def teardown_deployer_network(config_path=None):
    """Teardown the network elements on the deployer.
    This function is idempotent.
    """
    cfg = Config(config_path)
    global LOG
    LOG = logger.getlogger()
    LOG.debug('----------------------------------------')

    # if inv.is_passive_mgmt_switches():
    #     self.LOG.info('Passive Management Switch(es) specified')
    # return

    LOG.info('Teardown deployer management networks')
    dev_label = cfg.get_depl_netw_mgmt_device()
    interface_ipaddr = cfg.get_depl_netw_mgmt_intf_ip()
    container_ipaddr = cfg.get_depl_netw_mgmt_cont_ip()
    bridge_ipaddr = cfg.get_depl_netw_mgmt_brg_ip()
    vlan = cfg.get_depl_netw_mgmt_vlan()
    netprefix = cfg.get_depl_netw_mgmt_prefix()

    for i, dev in enumerate(dev_label):
        _delete_network(dev_label[i],
                        interface_ipaddr[i],
                        netprefix[i],
                        container_ipaddr=container_ipaddr[i],
                        bridge_ipaddr=bridge_ipaddr[i],
                        vlan=vlan[i])

    LOG.info('Teardown deployer client networks')
    type_ = cfg.get_depl_netw_client_type()
    dev_label = cfg.get_depl_netw_client_device()
    interface_ipaddr = cfg.get_depl_netw_client_intf_ip()
    container_ipaddr = cfg.get_depl_netw_client_cont_ip()
    bridge_ipaddr = cfg.get_depl_netw_client_brg_ip()
    vlan = cfg.get_depl_netw_client_vlan()
    netprefix = cfg.get_depl_netw_client_prefix()

    for i, dev in enumerate(dev_label):
        _delete_network(dev_label[i],
                        interface_ipaddr[i],
                        netprefix[i],
                        container_ipaddr=container_ipaddr[i],
                        bridge_ipaddr=bridge_ipaddr[i],
                        vlan=vlan[i],
                        type_=type_[i])


def _delete_network(
        dev_label,
        interface_ipaddr,
        netprefix,
        container_ipaddr=None,
        bridge_ipaddr=None,
        vlan=None,
        type_='mgmt'):

    ifc_addresses = _get_ifc_addresses()

    if not bridge_ipaddr:
        if not IPR.link_lookup(ifname=dev_label):
            LOG.info('External interface {} not found'.format(dev_label))
            return
        # if address is on device, then remove it.
        if interface_ipaddr + '/' + str(netprefix) in ifc_addresses[dev_label]:
            LOG.info('Removing address {} from link {}'
                     .format(interface_ipaddr, dev_label))
            index = IPR.link_lookup(ifname=dev_label)
            IPR.addr('del', index=index, address=interface_ipaddr, mask=netprefix)
        else:
            LOG.debug('Address {} does not exist on link {}'.
                      format(interface_ipaddr, dev_label))

        # Check to see if the device and address is configured in any interface
        # definition file. If it is and it was Genesis created, then delete the
        # definition file.
        ifc_file_list = _get_ifcs_file_list()
        addr_cfgd = False
        for filename in ifc_file_list:
            f = open(filename, 'r')
            interfaces = f.read()
            f.close()
            if re.findall(r'^ *auto\s+' + dev_label + '\s',
                          interfaces, re.MULTILINE):
                LOG.debug('Device {} already configured in network configuration '
                          'file {}'.format(dev_label, filename))
            interfaces = interfaces.split('iface')
            for line in interfaces:
                if dev_label in line:
                    if re.findall(r'^ *address\s+' +
                                  interface_ipaddr, line, re.MULTILINE):
                        addr_cfgd = True
                        LOG.debug('Address {} already configured in {}'.
                                  format(interface_ipaddr, filename))
        if addr_cfgd:
            _delete_ifc_cfg_file(dev_label)
    else:
        # bridge specified
        # Prepare to delete the bridge
        br_label = 'br-' + type_
        if vlan and vlan != 4095:
            br_label = br_label + '-' + str(vlan)
        link = dev_label
        # if a vlan other than 4095 is specified, delete the vlan link
        if vlan and vlan != 4095:
            link = dev_label + '.{}'.format(vlan)
        # if the vlan link already exists on another bridge then display warning
        if _is_ifc_attached_elsewhere(link, br_label):
            LOG.warning('Link {} in use on another bridge. Not deleted'.
                        format(link))
            print('Warning: Link {} in use on another bridge. Not deleted'.
                  format(link))
        else:
            # Delete the tagged interface
            if IPR.link_lookup(ifname=link):
                LOG.debug('Deleting vlan interface: {}'.format(link))
                IPR.link("del", ifname=link)
        _delete_bridge(br_label)

        _delete_br_cfg_file(br_label)


def _delete_ifc_cfg_file(ifc):
    """ Deletes a Genesis created interface specific configuration file
    Args:
        ifc (str) interface name
        ip (str) interface ipv4 address
        mask (str) interface netmask
        broadcast (str) interface broadcast address
    """
    file_name = '/etc/network/interfaces.d/' + ifc + '-genesis-generated'
    if os.path.exists(file_name):
        LOG.info('Deleting {} config file'.format(file_name))
        os.system('sudo rm ' + file_name)


def _delete_br_cfg_file(bridge):
    """ Deletes the config file for the specified bridge.
    Args:
        bridge (str) bridge name
    """
    opsys = platform.dist()[0]
    LOG.debug('OS: ' + opsys)
    if opsys not in ('Ubuntu', 'redhat'):
        LOG.error('Unsupported Operating System')
        sys.exit('Unsupported Operating System')
    if opsys == 'Ubuntu':
        if os.path.exists('/etc/network/interfaces.d/' + bridge):
            LOG.info('Deleting bridge config file {}'.format(bridge))
            os.system('sudo rm /etc/network/interfaces.d/{}'.format(bridge))
        return
    LOG.error('Support for Red Hat not yet implemented')
    sys.exit('Support for Red Hat not yet implemented')


def _get_ifc_addresses():
    """ Create a dictionary of links.  For each link, create list of cidr
    addresses
    """
    ifc_addresses = {}
    for link in IPR.get_links():
        link_name = link.get_attr('IFLA_IFNAME')
        ifc_addresses[link_name] = []
        for addr in IPR.get_addr(index=link['index']):
            ifc_addresses[link_name].append(
                addr.get_attr('IFA_ADDRESS') + '/' + str(addr['prefixlen']))
    return ifc_addresses


def _get_ifcs_file_list():
    """ Returns the absolute path for all interface definition files
    """
    opsys = platform.dist()[0]
    if opsys == 'Ubuntu':
        path = '/etc/network/'
        pathd = '/etc/network/interfaces.d/'
        file_list = []
        file_list.append(path + 'interfaces')
        for filename in os.listdir(pathd):
            file_list.append(pathd + filename)
    return file_list


def _delete_bridge(bridge):
    """ Deletes a bridge if the bridge exists.
    Args:
        bridge (str) bridge name
    """
    if IPR.link_lookup(ifname=bridge):
        LOG.info('Deleting bridge {}'.format(bridge))
        IPR.link("del", ifname=bridge)


def _is_addr_on_link(ip, link):
    """ Checks to see if address ip is already added to link
    Args:
        ip (str) ipv4 address
        link (str) link name
    Returns: True/False
    """
    addr_list = IPR.get_addr(label=link)
    for addr in addr_list:
        if ip == addr.get_attr('IFA_ADDRESS'):
            LOG.debug(
                'Address {} found on link {}'.format(ip, link))
            return True
    LOG.debug('Address {} not found on link {}'.format(ip, link))
    return False


def _is_ifc_attached_elsewhere(ifc, bridge):
    """ Checks to see if ifc is in use on a bridge other than that specified
    Args:
        ifc (str) interface name
        bridge (str) name of bridge the interface is intended for
    Returns:
        True if the interface is already being used (is unavailable)
    """
    br_list = subprocess.check_output(['bash', '-c', 'brctl show']).splitlines()
    output = []
    for line in br_list[1:]:
        if line.startswith('\t'):
            output[len(output) - 1] = output[len(output) - 1] + line
        else:
            output.append(line)
        if ifc in output[len(output) - 1] \
                and bridge not in output[len(output) - 1]:
            return True
    return False


if __name__ == '__main__':
    logger.create('nolog', 'info')
    teardown_deployer_network()
