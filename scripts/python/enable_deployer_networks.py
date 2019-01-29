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
from lib.utilities import line_in_file, sub_proc_exec

IPR = IPRoute()
OPSYS = platform.dist()[0]
IFCFG_PATH = '/etc/sysconfig/network-scripts/'


def enable_deployer_network(config_path=None):
    """creates or modifies the network elements on the deployer which allow
    communication between the POWER-Up container and the cluster nodes
    and switches. Management networks such as those used for switch
    management port access can utilize the default linux
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
    # type; ie pxe or ipmi
    _type = cfg.get_depl_netw_client_type()
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
                        _type=_type[i])


def _create_network(
        dev_label,
        interface_ipaddr,
        netprefix,
        container_ipaddr=None,
        bridge_ipaddr=None,
        vlan=None,
        _type='mgmt'):
    """ Creates a network between the container interface and a physical interface.
    If no bridge ip address is specified, the connection is via the default lxc
    bridge. If a bridge ip address and vlan are specified, a bridge is created.
    Inputs:
        dev_label (str): Name of the physical device providing external connectivity
            for the network.
        interface_ipaddr (str): ipv4 address of the phsical device specified by
            dev_label. If the address does not already exist on the interface it is
            added.
        netprefix (int): Size in bits of the network address.
        container_ipaddr (str): ip address of the management interface in the
        PowerUp container.
        bridge_ipaddr (str): ip address of the bridge connecting the container and
        the physical device.
        vlan (int):
        type (str): Type of interface being served by the network (mgmt, pxe, ipmi)
        to be created.
    """

    ifc_addresses = _get_ifc_addresses()

    if not IPR.link_lookup(ifname=dev_label):
        LOG.error('External interface {} not found'.format(dev_label))
        raise UserCriticalException('External interface {} not found.'
                                    .format(dev_label))

    # if no bridge_ipaddr is specied (ie None), then a bridge will not be created.
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

        for filename in ifc_file_list:
            ifc_cfgd, addr_cfgd = _is_ifc_configured(filename, dev_label, interface_ipaddr)
            if ifc_cfgd:
                break

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
        # secondary and removed when the first (primary) is removed. Note that
        # this does not remove addresses from network config files.
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
        br_label = 'br-' + _type
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

        # set bridge file write mode to 'w' (write) or 'a' (append)
        mode = 'a' if _type == 'mgmt' else 'w'

        if IPR.link_lookup(ifname=br_label):
            LOG.info('{}NOTE: bridge {} is already configured.{}'.format(Color.bold,
                     br_label, Color.endc))
            print("Enter to continue, or 'T' to terminate deployment")
            resp = input("\nEnter or 'T': ")
            if resp == 'T':
                sys.exit('POWER-Up stopped at user request')

        _write_br_cfg_file(
            br_label,
            ip=bridge_ipaddr,
            prefix=netprefix,
            ifc=link,
            mode=mode)
        _setup_bridge(br_label, bridge_ipaddr, netprefix, link)
        _update_firewall(br_label)


def _is_firewall_running():
    res, err, rc = sub_proc_exec('systemctl status firewalld')
    if not rc:
        if 'Active: active' in res or 'active (running)' in res:
            return True


def _update_firewall(br_label):
    """Update iptables FORWARD table to forward all traffic coming into
    the specified bridge.
    """
    if _is_firewall_running():
        fwd_tbl, err, rc = sub_proc_exec('iptables -vL FORWARD')
        if br_label not in fwd_tbl:
            LOG.debug(f'Updating firewall. Forward {br_label} packets.')
            cmd = (f'iptables -I FORWARD -p all -i {br_label} '
                   f'-s 0.0.0.0/0 -d 0.0.0.0/0 -j ACCEPT')
            res, err, rc = sub_proc_exec(cmd)
            if rc:
                LOG.warning('An error occured while updating the firewall. '
                            f'Error {err}. RC: {rc}')


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


def _get_ip_addr_num(file_path):
    """Get the next IPADDR index num to use for adding an ip addr to an
    ifcfg file.
    """
    num = ''
    with open(file_path, 'r') as f:
        data = f.read()
    data = data.splitlines()
    for line in data:
        found = re.search(r'IPADDR(\d?)=', line)
        if found:
            if found.group(1) == '':
                num = 0
            else:
                num = str(int(found.group(1)) + 1)
    return num


def _write_ifc_cfg_file(ifc, ip=None, mask=None, broadcast=None, ifc_cfgd=False,
                        bridge=None):
    """ Writes an interface specific configuration file
    Args:
        ifc (str) interface name
        ip (str) interface ipv4 address
        mask (str) interface netmask
        broadcast (str) interface broadcast address
        ifc_cfgd (bin): Used for Ubuntu to indicate whether the physical
            interface is already defined. If not add 'auto' statement.
        bridge (str): If present, add a 'BRIDGE' statement to Red Hat interface
    """
    if OPSYS == 'Ubuntu':
        file_path = GEN_PATH + ifc + '-powerup-generated'
        LOG.debug('Writing {} config file'.format(file_path))
        f = open(file_path, 'w')
        f.write('# POWERUp generated\n')
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
            .format(file_path, ifc + '-powerup-generated'))
        os.system('rm ' + file_path)
    elif OPSYS == 'redhat':
        file_path = IFCFG_PATH + f'ifcfg-{ifc}'
        if not os.path.isfile(file_path):
            LOG.error(f'No interface config file exists for {ifc}.'
                      f'Creating {IFCFG_PATH}ifcfg-{ifc}')
            with open(file_path, 'w') as f:
                f.write(f'DEVICE="{ifc}"')
                f.write('ONBOOT=yes')
                f.write('BOOTPROTO=none')
                f.write('TYPE=Ethernet')
                f.write('NM_CONTROLLED=no')
        LOG.info('Writing {} config file'.format(file_path))
        line_in_file(file_path, r'^ *ONBOOT=.+', 'ONBOOT=yes', backup='-powerup-bkup.orig')
        line_in_file(file_path, r'^ *BOOTPROTO=.+', 'BOOTPROTO=none')
        line_in_file(file_path, r'^ *NM_CONTROLLED=.+', 'NM_CONTROLLED=no')
        if ip:
            ifc_cfgd, addr_cfgd = _is_ifc_configured(file_path, ifc, ip)
            if not addr_cfgd:
                ipaddr_num = _get_ip_addr_num(file_path)
                with open(file_path, 'a') as f:
                    f.write(f'IPADDR{ipaddr_num}={ip}\n')
                    f.write(f'NETMASK{ipaddr_num}={mask}')
        if bridge:
            with open(file_path, 'a') as f:
                f.write(f'BRIDGE={bridge}')


def _write_br_cfg_file(bridge, ip=None, prefix=None, ifc=None, mode='w'):
    """ Writes the config file for the specified bridge.  If the specified
    interface is not configured, a config file is created for it also.  If
    mode is set to 'a' (append) and the bridge config file exists, the
    specified interface is added to the bridge config file.  If mode is
    unspecified or set to 'w' (write), the config file is created or
    overwritten. The interface specified by 'ifc' is attached to the bridge.
    Args:
        bridge (str) bridge name
        ip (str) ipv4 address to be added to the bridge
        prefix (int or str) network prefix length.  ie the length of the
            network portion of the ip address
        ifc (str) name of the interface to be added to the bridge.
    """
    LOG.debug('OS: ' + OPSYS)
    if OPSYS not in ('debian', 'Ubuntu', 'redhat'):
        LOG.error('Unsupported Operating System')
        raise UserCriticalException('Unsupported Operating System')
    network = IPNetwork(ip + '/' + str(prefix))
    network_addr = str(network.network)
    broadcast = str(network.broadcast)
    netmask = str(network.netmask)
    if OPSYS in ('debian', 'Ubuntu'):
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
        return
    elif OPSYS == 'redhat':
        # Create the ifc config file
        # non vlan ifc
        if '.' not in ifc:
            _write_ifc_cfg_file(ifc, bridge=bridge)
        # vlan ifc
        else:
            file_path = IFCFG_PATH + f'ifcfg-{ifc}'
            with open(file_path, 'w') as f:
                LOG.debug(f'Writing vlan config file:\n{file_path}')
                f.write(f'DEVICE={ifc}\n')
                f.write('ONBOOT=yes\n')
                f.write('BOOTPROTO=none\n')
                f.write('NM_CONTROLLED=no\n')
                f.write('VLAN=yes\n')
                f.write(f'BRIDGE={bridge}')

        # Create the bridge config file
        file_path = f'{IFCFG_PATH}ifcfg-{bridge}'
        if mode == 'a' and os.path.isfile(file_path):
            LOG.debug(f'Appending to bridge config file {bridge} IP addr {ip}')
            ifc_cfgd, addr_cfgd = _is_ifc_configured(file_path, ifc, ip)
            if not addr_cfgd:
                ipaddr_num = _get_ip_addr_num(file_path)
                with open(file_path, 'a') as f:
                    f.write(f'IPADDR{ipaddr_num}={ip}\n')
                    f.write(f'PREFIX{ipaddr_num}={prefix}')
        else:
            with open(file_path, 'w') as f:
                f.write(f'DEVICE={bridge}\n')
                f.write('ONBOOT=yes\n')
                f.write('TYPE=Bridge\n')
                f.write(f'IPADDR={ip}\n')
                f.write(f'PREFIX={prefix}\n')
                f.write('BOOTPROTO=none\n')
                f.write('NM_CONTROLLED=no\n')
                f.write('DELAY=0')


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
    if OPSYS in ('debian', 'Ubuntu'):
        path = '/etc/network/'
        pathd = '/etc/network/interfaces.d/'
        file_list = []
        file_list.append(path + 'interfaces')
        for filename in os.listdir(pathd):
            file_list.append(pathd + filename)
    elif OPSYS == 'redhat':
        path = '/etc/sysconfig/network-scripts/'
        file_list = []
        for filename in os.listdir(path):
            _file = re.search(r'(?!.*\.orig$)ifcfg-.+', filename)
            if _file:
                file_list.append(path + _file.group(0))
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


def _is_ifc_attached(ifc, bridge):
    """ Checks to see if ifc is in use on a bridge other than that specified
    Args:
        ifc (str) interface name
        bridge (str) name of bridge the interface is intended for
    Returns:
        True if the interface is already being used (is unavailable)
    """

    br_list = subprocess.check_output(['bash', '-c', 'brctl show']
                                      ).decode("utf-8").splitlines()
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
