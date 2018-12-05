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

import argparse
import sys
import os
import re
import platform
from pyroute2 import IPRoute

from lib.config import Config
from lib.genesis import GEN_PATH
from lib.container import Container
import lib.logger as logger
from lib.utilities import sub_proc_exec, remove_line, get_netmask

IPR = IPRoute()
OPSYS = platform.dist()[0]
IFCFG_PATH = '/etc/sysconfig/network-scripts/'


def teardown_deployer_network(config_path=None):
    """Teardown the network elements on the deployer.
    This function is idempotent.
    """
    cfg = Config(config_path)
    global LOG
    LOG = logger.getlogger()
    LOG.debug('----------------------------------------')
    LOG.info('Teardown Docker networks')
    _remove_docker_networks(cfg)
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
        # definition file. If it is and it was PowerUp created, then delete the
        # definition file.
        ifc_path_list = _get_ifcs_path_list()
        for filename in ifc_path_list:
            ifc_cfgd, addr_cfgd = _is_ifc_configured(filename, dev_label, interface_ipaddr)
            if ifc_cfgd:
                break
        if addr_cfgd:
            _delete_ifc_cfg(dev_label, interface_ipaddr, get_netmask(netprefix))
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

        _delete_br_cfg_file(br_label, dev_label)


def _delete_ifc_cfg(ifc, ipaddr='', netmask=''):
    """ Deletes a PowerUp created interface specific configuration. For Ubuntu
    this involves removing the PowerUp generated config file. For Red Hat, this
    involves removing the interface IP address and netmask from the 'ifcfg' file.
    There may be additional PowerUp changes to the Red Hat ifcfg file which are
    not undone. The original interface configuration can be restored from the
    PowerUp generated backup (ifcfg-{ifc}.orig)
    Args:
        ifc (str) interface name
        ip (str) interface ipv4 address
        mask (str) interface netmask
        broadcast (str) interface broadcast address
    """
    if OPSYS == 'Ubuntu':
        file_path = '/etc/network/interfaces.d/' + ifc + '-genesis-generated'
        if os.path.exists(file_path):
            LOG.info('Deleting {} config file'.format(file_path))
            os.remove(file_path)
    elif OPSYS == 'redhat':
        file_path = f'/etc/sysconfig/network-scripts/ifcfg-{ifc}'
        regex = rf'IPADDR\d*={ipaddr}'
        LOG.info(f'Removing {ipaddr} from {file_path}')
        remove_line(file_path, regex)
        regex = fr'NETMASK\d*={netmask}'
        remove_line(file_path, regex)
    else:
        LOG.warning(f'Unsupported OS: {OPSYS}')


def _delete_br_cfg_file(bridge, ifc=''):
    """ Deletes the config file for the specified bridge.
    Args:
        bridge (str) bridge name
    """
    if OPSYS in ('debian', 'Ubuntu'):
        if os.path.exists('/etc/network/interfaces.d/' + bridge):
            LOG.info(f'Deleting bridge config file {bridge}')
            os.remove(f'/etc/network/interfaces.d/{bridge}')
    elif OPSYS == 'redhat':
        path = f'/etc/sysconfig/network-scripts/ifcfg-{bridge}'
        if os.path.isfile(path):
            LOG.info(f'Deleting bridge config file {path}')
            os.remove(path)
        else:
            LOG.info(f'Bridge config file {path} not found')
        # Delete the vlan interface
        vlan = bridge[1 + bridge.rfind('-'):]
        path = f'/etc/sysconfig/network-scripts/ifcfg-{ifc}.{vlan}'
        if os.path.isfile(path):
            LOG.info(f'Deleting vlan config file {path}')
            os.remove(path)
    else:
        LOG.warning(f'Unsupported OS: {OPSYS}')


def _is_ifc_configured(ifc_cfg_file, dev_label, interface_ipaddr):
    """Looks through an interface config file to see if the interface specified
    by dev_label is configured and if the address specified by interface_ipaddr
    is configured on that interface.
    """
    ifc_cfgd = False
    addr_cfgd = False
    f = open(ifc_cfg_file, 'r')
    interfaces = f.read()
    f.close()
    if OPSYS == 'Ubuntu':
        ssdl = fr'^ *auto\s+{dev_label}\s'
        ssad = fr'^ *address\s+{interface_ipaddr}'
        split_str = 'iface'
    elif OPSYS == 'redhat':
        ssdl = fr'^ *DEVICE="?{dev_label}"?'
        ssad = fr'^ *IPADDR="?{interface_ipaddr}"?'
        split_str = 'NAME='
    if re.search(ssdl, interfaces, re.MULTILINE):
        ifc_cfgd = True
        LOG.debug('Device {} already configured in network configuration file {}'.
                  format(dev_label, ifc_cfg_file))
    interfaces = interfaces.split(split_str)
    for line in interfaces:
        if dev_label in line:
            if re.findall(ssad, line, re.MULTILINE):
                addr_cfgd = True
                LOG.debug('Address {} configured in {}'.
                          format(interface_ipaddr, ifc_cfg_file))
    return ifc_cfgd, addr_cfgd


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


def _get_ifcs_path_list():
    """ Returns the absolute path for all interface definition files
    """
    if OPSYS in ('debian', 'Ubuntu'):
        path = '/etc/network/'
        pathd = '/etc/network/interfaces.d/'
        path_list = []
        path_list.append(path + 'interfaces')
        for filename in os.listdir(pathd):
            path_list.append(pathd + filename)
    elif OPSYS == 'redhat':
        path = '/etc/sysconfig/network-scripts/'
        path_list = []
        for filename in os.listdir(path):
            _file = re.search(r'(?!.*\.orig$)ifcfg-.+', filename)
            if _file:
                path_list.append(path + _file.group(0))
    return path_list


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
    br_list, err, rc = sub_proc_exec('brctl show')
    br_list = br_list.splitlines()
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


def _remove_docker_networks(cfg):
    container = Container(cfg.config_path)
    container.create_networks(remove=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('config_path', default='config.yml',
                        help='Config file path.  Absolute path or relative to '
                        'power-up/ sudo env "PATH=$PATH"  '
                        'teardown_deployer_networks.py config-name')

    parser.add_argument('--print', '-p', dest='log_lvl_print',
                        help='print log level', default='info')

    parser.add_argument('--file', '-f', dest='log_lvl_file',
                        help='file log level', default='info')

    args = parser.parse_args()

    if not os.path.isfile(args.config_path):
        args.config_path = GEN_PATH + args.config_path
        print('Using config path: {}'.format(args.config_path))
    if not os.path.isfile(args.config_path):
        sys.exit('{} does not exist'.format(args.config_path))

    logger.create(args.log_lvl_print, args.log_lvl_file)
    # logger.create('nolog', 'info')
    teardown_deployer_network(args.config_path)
