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

import argparse
import os
import re
import sys
import subprocess
import platform
import time
from netaddr import IPNetwork
from pyroute2 import IPRoute

import lib.logger as logger
from lib.config import Config
from lib.exception import UserCriticalException
from lib.genesis import Color, GEN_PATH

IPR = IPRoute()


def enable_deployer_network(config_path=None):
    """creates or modifies the network elements on the deployer which allow
    communication between the Genesis container and the cluster nodes
    and switches. The management networks can utilize the default linux
    container bridge in which case they carry untagged traffic or they can
    specify a bridge with a tagged vlan. PXE and IPMI networks always include a
    bridge. The IPMI bridge can be tagged or untagged. The PXE bridge must be
    tagged.  Networks can share a physical port or specify unique ports.
    This function is idempotent.
    """
    global LOG
    cfg = Config(config_path)
    LOG = logger.getlogger()
    LOG.debug('------------------- enable_deployer_networks ----------------------')

    # if inv.is_passive_mgmt_switches():
    #     self.LOG.info('Passive Management Switch(es) specified')
    # return

    LOG.debug('=== Configuring deployer management networks ===')
    dev_label = cfg.get_depl_netw_mgmt_device()
    interface_ipaddr = cfg.get_depl_netw_mgmt_intf_ip()
    container_ipaddr = cfg.get_depl_netw_mgmt_cont_ip()
    bridge_ipaddr = cfg.get_depl_netw_mgmt_brg_ip()
    vlan = cfg.get_depl_netw_mgmt_vlan()
    netprefix = cfg.get_depl_netw_mgmt_prefix()

    for i, dev in enumerate(dev_label):
        _create_network(dev_label[i],
                        interface_ipaddr[i],
                        netprefix[i],
                        container_ipaddr=container_ipaddr[i],
                        bridge_ipaddr=bridge_ipaddr[i],
                        vlan=vlan[i])

    LOG.debug('=== Configuring deployer client networks ===')
    type_ = cfg.get_depl_netw_client_type()
    dev_label = cfg.get_depl_netw_client_device()
    interface_ipaddr = cfg.get_depl_netw_client_intf_ip()
    container_ipaddr = cfg.get_depl_netw_client_cont_ip()
    bridge_ipaddr = cfg.get_depl_netw_client_brg_ip()
    vlan = cfg.get_depl_netw_client_vlan()
    netprefix = cfg.get_depl_netw_client_prefix()

    for i, dev in enumerate(dev_label):
        _create_network(dev_label[i],
                        interface_ipaddr[i],
                        netprefix[i],
                        container_ipaddr=container_ipaddr[i],
                        bridge_ipaddr=bridge_ipaddr[i],
                        vlan=vlan[i],
                        type_=type_[i])


def _create_network(
        dev_label,
        interface_ipaddr,
        netprefix,
        container_ipaddr=None,
        bridge_ipaddr=None,
        vlan=None,
        type_='mgmt'):

    ifc_addresses = _get_ifc_addresses()

    if not IPR.link_lookup(ifname=dev_label):
        LOG.error('External interface {} not found'.format(dev_label))
        raise UserCriticalException('External interface {} not found.'
                                    .format(dev_label))

    # if a bridge_ipaddr is not specied, then a bridge will not be created.
    if not bridge_ipaddr:
        # if address not already on device, then add it.
        if not interface_ipaddr + '/' + str(netprefix) in ifc_addresses[dev_label]:
            LOG.debug('Adding address {} to link {}'.
                      format(interface_ipaddr, dev_label))
            index = IPR.link_lookup(ifname=dev_label)
            IPR.addr('add', index=index, address=interface_ipaddr, mask=netprefix)
        else:
            LOG.debug('Address {} already exists on link {}'.
                      format(interface_ipaddr, dev_label))

        # Check to see if the device and address is configured in any interface
        # definition file. If not, then write a definition file.
        ifc_file_list = _get_ifcs_file_list()

        ifc_cfgd = False
        addr_cfgd = False
        for filename in ifc_file_list:
            f = open(filename, 'r')
            interfaces = f.read()
            f.close()
            if re.findall(r'^ *auto\s+' + dev_label + '\s', interfaces, re.MULTILINE):
                ifc_cfgd = True
                LOG.debug('Device {} already configured in network configuration file {}'.
                          format(dev_label, filename))
            interfaces = interfaces.split('iface')
            for line in interfaces:
                if dev_label in line:
                    if re.findall(r'^ *address\s+' + interface_ipaddr, line, re.MULTILINE):
                        addr_cfgd = True
                        LOG.debug('Address {} configured in {}'.
                                  format(interface_ipaddr, filename))

        broadcast = None
        netmask = str(IPNetwork('255.255.255.255/' + str(netprefix)).netmask)
        if not addr_cfgd:
            _write_ifc_cfg_file(
                dev_label,
                ip=interface_ipaddr,
                mask=netmask,
                broadcast=broadcast,
                ifc_cfgd=ifc_cfgd)
    # bridge
    else:
        # Check for existing addresses on the external interface and
        # remove any that lie within the mgmt subnet. You only need to remove
        # the first address found in the subnet since any additional ones are
        # secondary and removed when the first (primary) is removed.

        cidr = IPNetwork(bridge_ipaddr + '/' + str(netprefix))
        network = IPNetwork(cidr)
        network_addr = str(network.network)

        for addr in IPR.get_addr(label=dev_label):
            pfx = int(addr['prefixlen'])
            adr = addr.get_attr('IFA_ADDRESS')
            existing_network = IPNetwork(
                addr.get_attr('IFA_ADDRESS') + '/' + str(addr['prefixlen']))
            existing_network_addr = str(existing_network.network)
            if existing_network_addr == network_addr:
                LOG.debug(
                    'Removing address {}/{} from interface {}'
                    .format(adr, pfx, dev_label))
                IPR.addr(
                    'delete',
                    index=IPR.link_lookup(ifname=dev_label),
                    address=adr,
                    mask=pfx)

        # Prepare to setup the bridge
        br_label = 'br-' + type_
        if vlan and vlan != 4095:
            br_label = br_label + '-' + str(vlan)
        link = dev_label
        # if a vlan other than 1 or 4095 is specified, create the vlan link
        if vlan and vlan != 4095:
            link = dev_label + '.{}'.format(vlan)
        # if the vlan link already exists on another bridge then display warning
        if _is_ifc_attached_elsewhere(link, br_label):
            LOG.warning('Link {} already in use on another bridge.'.format(link))
            print('Warning: Link {} already in use on another bridge.'.format(link))

        if not IPR.link_lookup(ifname=link):
            LOG.debug('creating vlan interface: {}'.format(link))
            IPR.link(
                "add",
                ifname=link,
                kind="vlan",
                link=IPR.link_lookup(ifname=dev_label)[0],
                vlan_id=vlan)
        IPR.link("set", index=IPR.link_lookup(ifname=link)[0], state="up")
        if not _wait_for_ifc_up(link):
            raise UserCriticalException('Failed to bring up interface {} '.
                                        format(link))

        # set bridge file write mode to 'w' (write) or 'a' (add)
        if type_ == 'mgmt':
            mode = 'a'
        else:
            mode = 'w'

        if IPR.link_lookup(ifname=br_label):
            LOG.info('{}NOTE: bridge {} is already configured.{}'.format(Color.bold,
                     br_label, Color.endc))
            print("Enter to continue, or 'T' to terminate deployment")
            resp = raw_input("\nEnter or 'T': ")
            if resp == 'T':
                sys.exit('POWER-Up stopped at user request')

        _write_br_cfg_file(
            br_label,
            ip=bridge_ipaddr,
            prefix=netprefix,
            ifc=link,
            mode=mode)
        _setup_bridge(br_label, bridge_ipaddr, netprefix, link)


def _write_ifc_cfg_file(ifc, ip=None, mask=None, broadcast=None, ifc_cfgd=False):
    """ Writes an interface specific configuration file
    Args:
        ifc (str) interface name
        ip (str) interface ipv4 address
        mask (str) interface netmask
        broadcast (str) interface broadcast address
    """
    file_name = GEN_PATH + ifc + '-genesis-generated'
    LOG.debug('Writing {} config file'.format(file_name))
    f = open(file_name, 'w')
    f.write('# Cluster genesis generated\n')
    if not ifc_cfgd:
        f.write('auto {}\n'.format(ifc))
    if ip:
        f.write('iface {} inet static\n'.format(ifc))
        f.write('    address {}\n'.format(ip))
        f.write('    netmask {}\n'.format(mask))
        if broadcast:
            f.write('    broadcast {}\n'.format(broadcast))
    else:
        f.write('iface {} inet dhcp\n'.format(ifc))
    f.close()
    os.system(
        'sudo cp {} /etc/network/interfaces.d/{}'
        .format(file_name, ifc + '-genesis-generated'))
    os.system('rm ' + file_name)


def _write_br_cfg_file(bridge, ip=None, prefix=None, ifc=None, mode='w'):
    """ Writes the config file for the specified bridge.  If the specified
    interface is not configured, a config file is created for it also.  If
    mode is set to 'a' (append) and the bridge config file exists, the
    specified interface is added to the bridge config file.  If mode is
    unspecified or set to 'w' (write), the config file is created or
    overwritten.
    Args:
        bridge (str) bridge name
        ip (str) ipv4 address to be added to the bridge
        prefix (int or str) network prefix length.  ie the length of the
            network portion of the ip address
        ifc (str) name of the interface to be added to the bridge.
    """
    opsys = platform.dist()[0]
    LOG.debug('OS: ' + opsys)
    if opsys not in ('Ubuntu', 'redhat'):
        LOG.error('Unsupported Operating System')
        raise UserCriticalException('Unsupported Operating System')
    network = IPNetwork(ip + '/' + str(prefix))
    network_addr = str(network.network)
    broadcast = str(network.broadcast)
    netmask = str(network.netmask)
    if opsys == 'Ubuntu':
        if mode == 'a' and os.path.exists('/etc/network/interfaces.d/' + bridge):
            LOG.debug('Appending to bridge config file {} IP addr {}'.
                      format(bridge, ip))
            os.system(
                'cp /etc/network/interfaces.d/{} {}{} '
                .format(bridge, GEN_PATH, bridge))
            f = open(GEN_PATH + bridge, 'r')
            data = f.read()
            f.close()
            data = data.split('auto')
            f = open(GEN_PATH + bridge, 'w')
            # Write the specified interface if it is a vlan interface
            # If the interface already exists in the file it will be replaced
            f.write(data[0])
            if '.' in ifc:
                f.write('auto {}\n'.format(ifc))
                f.write('iface {} inet manual\n'.format(ifc))
                f.write('    vlan-raw-device {}\n\n'.format(ifc[:ifc.find('.')]))
            for item in data[1:len(data) - 1]:
                if not ('iface ' + ifc + ' ') in item:
                    f.write('auto' + item)
            # rewrite the bridge config
            data = ('auto' + data[len(data) - 1]).splitlines()
            for item in data:
                item = item + ' '
                if 'bridge_ports' in item and not ifc + ' ' in item:
                    item = item + ifc
                f.write(item.rstrip(' ') + '\n')
            f.close()
            os.system(
                'sudo cp {}{} /etc/network/interfaces.d/{}'
                .format(GEN_PATH, bridge, bridge))
            os.system('rm ' + GEN_PATH + bridge)

        else:
            LOG.debug('Wrting bridge configuration file: {} IP addr: {}'.
                      format(bridge, ip))
            f = open(GEN_PATH + bridge, 'w')
            f.write("# This file should not be edited manually\n")
            f.write('auto {}\n'.format(ifc))
            f.write('iface {} inet manual\n'.format(ifc))
            f.write('    vlan-raw-device {}\n\n'.format(ifc[:ifc.find('.')]))
            f.write('auto {}\n'.format(bridge))
            f.write('iface {} inet static\n'.format(bridge))
            f.write('    address {}\n'.format(ip))
            f.write('    netmask {}\n'.format(netmask))
            f.write('    broadcast {}\n'.format(broadcast))
            f.write('    network {}\n'.format(network_addr))
            f.write('    bridge_ports {}\n'.format(ifc))
            f.write('    bridge fd 0\n')
            f.close()
            os.system(
                'sudo cp {}{} /etc/network/interfaces.d/{}'
                .format(GEN_PATH, bridge, bridge))
            os.system('rm ' + GEN_PATH + bridge)

        os.system('cp /etc/lxc/lxc-usernet ' + GEN_PATH)
        f = open(GEN_PATH + 'lxc-usernet', 'r')
        data = f.read()
        f.close()
        username = os.getlogin()
        perm = re.findall(username + r'\s+veth\s+' + bridge, data, re.MULTILINE)
        permlxcbr0 = re.findall(username + r'\s+veth\s+lxcbr0', data, re.MULTILINE)
        if not perm or not permlxcbr0:
            LOG.debug('Updating lxc user network permissions')
            f = open(GEN_PATH + 'lxc-usernet', 'a')
            if not permlxcbr0:
                f.write(username + ' veth lxcbr0 10\n')
            if not perm:
                f.write(username + ' veth ' + bridge + ' 10\n')
            f.close()

            os.system('sudo cp ' + GEN_PATH + 'lxc-usernet /etc/lxc/lxc-usernet')
        return
    LOG.error('Support for Red Hat not yet implemented')
    raise UserCriticalException('Support for Red Hat not yet implemented')


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


def _setup_bridge(bridge, ip=None, prefix=None, ifc=None):
    """ Sets up a bridge. If the bridge does not exist, it is created.
    If an ip address and prefix are given it will be added to the bridge.
    If an interface name is specified it will be attached to the bridge
    Args:
        bridge (str) bridge name
        ip (str) ipv4 address (ie '1.2.3.4')
        prefix (int or str) Network mask length (ie 24)
        ifc (str) An interface name
    """
    LOG.debug('Setting up bridge {} with ifc {} and address {}'
              .format(bridge, ifc, ip))
    if not IPR.link_lookup(ifname=bridge):
        IPR.link("add", ifname=bridge, kind="bridge")
    IPR.link("set", ifname=bridge, state="up")
    if ip and prefix:
        if not _is_addr_on_link(ip, bridge):
            IPR.addr(
                'add', index=IPR.link_lookup(ifname=bridge)[0],
                address=ip,
                mask=int(prefix))
    if ifc:
        IPR.link(
            'set',
            index=IPR.link_lookup(ifname=ifc)[0],
            master=IPR.link_lookup(ifname=bridge)[0])
    if not _wait_for_ifc_up(ifc):
        LOG.error('Failed to bring up interface {}'.format(ifc))
        raise UserCriticalException('Failed to bring up interface {}'.format(ifc))
    if not _wait_for_ifc_up(bridge):
        LOG.error('Failed to bring up bridge {}'.format(bridge))
        raise UserCriticalException('Failed to bring up bridge {}'.format(bridge))


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


def _is_ifc_attached(ifc, bridge):
    br_list = subprocess.check_output(['bash', '-c', 'brctl show']).splitlines()
    output = []
    for line in br_list[1:]:
        if line.startswith('\t'):
            output[len(output) - 1] = output[len(output) - 1] + line
        else:
            output.append(line)
        if ifc in output[len(output) - 1] and bridge in output[len(output) - 1]:
            return True
    return False


def _is_ifc_up(ifname):
    if 'UP' == IPR.get_links(
            IPR.link_lookup(ifname=ifname))[0].get_attr('IFLA_OPERSTATE'):
        return True
    return False


def _wait_for_ifc_up(ifname, timespan=10):
    """ Waits up to timespan seconds for the specified interface to be up.
    Prints a message if the interface is not up in 2 seconds.
    Args:
        ifname (str) : Name of the interface
        timespan (int) : length of time to wait in seconds
    Returns:
        True if interface is up, False if not.
    """
    for _ in range(2 * timespan):
        if _ == 4:
            print('Waiting for interface {} to come up. '.format(ifname))
        if _is_ifc_up(ifname):
            LOG.debug('Interface {} is up'.format(ifname))
            return True
        time.sleep(0.5)
    LOG.info('Timeout waiting for interface {} to come up'.format(ifname))
    return False


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('config_path', default='config.yml',
                        help='Config file path.  Absolute path or relative to '
                        'power-up/ sudo env "PATH=$PATH"  '
                        'enable_deployer_networks.py config-name')

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
    enable_deployer_network(args.config_path)
