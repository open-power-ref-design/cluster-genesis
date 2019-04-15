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
import time
import sys
import os
import re
from subprocess import PIPE
from pyroute2 import IPRoute, NetlinkError
from netaddr import IPNetwork
from orderedattrdict import AttrDict
from tabulate import tabulate

import lib.logger as logger
from lib.config import Config
from lib.inventory import Inventory
from lib.ssh import SSH_Exception
from lib.switch_exception import SwitchException
from lib.switch import SwitchFactory
from lib.exception import UserException, UserCriticalException
from get_dhcp_lease_info import GetDhcpLeases
from lib.genesis import get_dhcp_pool_start, GEN_PATH
from lib.utilities import sub_proc_exec, sub_proc_launch
import lib.bmc as _bmc
from set_power_clients import set_power_clients
from set_bootdev_clients import set_bootdev_clients

# offset relative to bridge address
NAME_SPACE_OFFSET_ADDR = 1


def main(config_path):
    """Validate config"""
    log = logger.getlogger()

    val = ValidateClusterHardware(config_path)
    if not val.validate_mgmt_switches():
        log.error('Failed validating cluster management switches')

    if not val.validate_data_switches():
        log.error('Failed validating cluster data switches')

    if not val.validate_ipmi():
        log.error('Failed cluster nodes IPMI validation')

    if not val.validate_pxe():
        log.error('Failed cluster nodes PXE validation')


class NetNameSpace(object):
    """Instantiate a network namespace connected to a bridge

    Args:
        log (object): Log
    """
    def __init__(self, name, bridge, addr):
        """
        Args:
            name (str): namespace name
            bridge (str): name of bridge to attach to
            addr (str): cidr of namespace address
        """
        self.log = logger.getlogger()
        self.addr = addr
        self.bridge = bridge
        self.vlan = bridge.split('-')[-1]
        self.name = name + self.vlan
        self.ip = IPRoute()
        self._disconnect_container()
        self.log.debug('Creating network namespace {}'.format(self.name))

        stdout, stderr, rc = sub_proc_exec('ip netns add {}'.format(self.name))
        if rc:
            self.log.debug('An error occurred while creating namespace '
                           f' {self.name}.\nreturn code: {rc}\nWarning: {stderr}')
        if stderr:
            if 'File exists' in stderr:
                self.log.debug(stderr)
            else:
                self.log.error('Unable to create namespace')
                sys.exit(1)

        self.br_ifc = 'veth-br-' + self.name.split('-')[0] + '-' + self.vlan
        self.peer_ifc = 'veth-' + self.name

        try:
            self.ip.link(
                "add", ifname=self.br_ifc, peer=self.peer_ifc, kind='veth')
        except NetlinkError as exc:
            if 'File exists' not in str(exc):
                self.log.error('Failed creating veth pair. {}'.format(exc))
                sys.exit(1)

        try:
            # peer interface side disappears from host space once attached to
            # the namespace
            idx_ns_ifc = self.ip.link_lookup(ifname=self.peer_ifc)[0]
            self.ip.link('set', index=idx_ns_ifc, net_ns_fd=self.name)
        except IndexError:
            self.log.debug('Peer ifc already attached.')
        except NetlinkError:
            self.log.debug('Peer ifc already attached.')
        idx_br = self.ip.link_lookup(ifname=bridge)[0]
        self.idx_br_ifc = self.ip.link_lookup(ifname=self.br_ifc)[0]
        self.ip.link('set', index=self.idx_br_ifc, master=idx_br)

        # bring up the interfaces
        cmd = 'ip netns exec {} ip link set dev {} up'.format(
            self.name, self.peer_ifc)
        stdout, stderr, rc = sub_proc_exec(cmd)

        cmd = 'ip netns exec {} ip link set dev lo up'.format(self.name)
        stdout, stderr, rc = sub_proc_exec(cmd)

        cmd = 'ip netns exec {} ip addr add {} dev {} brd +' \
            .format(self.name, addr, self.peer_ifc)
        stdout, stderr, rc = sub_proc_exec(cmd)

        # verify address setup
        # cmd = 'ip netns exec {} ip addr show'.format(self.name)
        # proc = Popen(cmd.split(), stdout=PIPE, stderr=PIPE)
        # stdout, stderr = proc.communicate()

        self.ip.link('set', index=self.idx_br_ifc, state='up')

    def _get_name_sp_ifc_name(self):
        return self.peer_ifc

    def _get_name_sp_name(self):
        return self.name

    def _get_name_sp_addr(self):
        return self.addr

    def _launch_cmd(self, cmd, stdout=PIPE, stderr=PIPE):
        """Execute a command in the namespace

        Args:
            log (object): Log
            cmd (string)
        """
        cmd = 'ip netns exec {} {}'.format(self.name, cmd)
        data = sub_proc_launch(cmd, stdout, stderr)
        return data

    def _exec_cmd(self, cmd, stdout=PIPE, stderr=PIPE):
        """Execute a command in the namespace

        Args:
            log (object): Log
            cmd (string)
        """
        cmd = 'ip netns exec {} {}'.format(self.name, cmd)
        std_out, std_err, rc = sub_proc_exec(cmd, stdout, stderr)
        return std_out, std_err, rc

    def _destroy_name_sp(self):
        self.ip.link('set', index=self.idx_br_ifc, state='down')
        self.ip.link('del', index=self.idx_br_ifc)
        self.ip.close()
        stdout, stderr, rc = sub_proc_exec('ip netns del {}'.format(self.name))

    def _disconnect_container(self):
        """ Disconnects any attached containers by bringing down all veth pairs
        attached to the bridge.
        """
        br_idx = self.ip.link_lookup(ifname=self.bridge)
        for link in self.ip.get_links():
            if br_idx[0] == link.get_attr('IFLA_MASTER'):
                link_name = link.get_attr('IFLA_IFNAME')
                if 'veth' in link_name:
                    self.log.debug('Bringing down veth pair {} on bridge: {}'
                                   .format(link_name, self.bridge))
                    self.ip.link('set', index=link['index'], state='down')

    def _reconnect_container(self):
        """ Disconnects any attached containers by bringing down all veth pairs
        attached to the bridge.
        """
        br_idx = self.ip.link_lookup(ifname=self.bridge)
        for link in self.ip.get_links():
            if br_idx[0] == link.get_attr('IFLA_MASTER'):
                link_name = link.get_attr('IFLA_IFNAME')
                if 'veth' in link.get_attr('IFLA_IFNAME'):
                    self.log.debug('Bringing up veth pair {} on bridge: {}'
                                   .format(link_name, self.bridge))
                    self.log.debug('link:' + link.get_attr('IFLA_IFNAME'))
                    self.ip.link('set', index=link['index'], state='up')


class ValidateClusterHardware(object):
    """Discover and validate cluster hardware

    Args:
        log (object): Log
    """

    def __init__(self, config_file=None):
        self.log = logger.getlogger()
        try:
            self.cfg = Config(config_file)
            self.inv = Inventory(None, config_file)
        except UserException as exc:
            self.log.critical(exc)
            raise UserException(exc)
        # initialize ipmi list of access info
        self.ran_ipmi = False
        self.bmc_ai = {}
        vlan_ipmi = self.cfg.get_depl_netw_client_vlan(if_type='ipmi')[0]
        vlan_pxe = self.cfg.get_depl_netw_client_vlan(if_type='pxe')[0]
        self.dhcp_pxe_leases_file = GEN_PATH + \
            'logs/dnsmasq{}.leases'.format(vlan_pxe)
        self.dhcp_ipmi_leases_file = GEN_PATH + \
            'logs/dnsmasq{}.leases'.format(vlan_ipmi)
        self.tcp_dump_file = GEN_PATH + \
            'logs/tcpdump{}.out'.format(vlan_pxe)
        self.node_table_ipmi = AttrDict()
        self.node_table_pxe = AttrDict()
        self.node_list = []

    def _add_offset_to_address(self, addr, offset):
        """calculates an address with an offset added.
        Args:
            addr (str): ipv4 or cidr representation of address
            offset (int): integer offset
        Returns:
            addr_.ip (str) address in ipv4 representation
        """
        addr_ = IPNetwork(addr)
        addr_.value += offset
        return str(addr_.ip)

    def _get_port_cnts(self):
        labels = self.cfg.get_sw_mgmt_label()
        ipmi_cnt = 0
        pxe_cnt = 0

        for label in labels:
            ipmi_cnt += len(self.cfg.get_client_switch_ports(label, 'ipmi'))
            pxe_cnt += len(self.cfg.get_client_switch_ports(label, 'pxe'))
        return ipmi_cnt, pxe_cnt

    def _get_credentials(self, node_addr_list, cred_list):
        """ Attempts to discover bmc credentials and generate a list of all
        discovered nodes.  For each node try all available credentials.  If no
        credentials allow access, the node is not marked as succesful.

        Args:
            node_addr_list (list): list of ipv4 addresses for the discovered
            nodes. (ie those that previously fetched an address from the DHCP
             server.
            cred_list (list of lists): Each list item is a list containing the
            the userid, password, bmc_type and number of nodes for a node template.
        return: bmc access info (dict) : Values hold tuple of userid, password,
                bmc_type
        """
        tot = [cred_list[x][3] for x in range(len(cred_list))]
        tot = sum(tot)
        left = tot
        max_attempts = 20
        delay = 5
        attempt = 0
        timeout = 4
        print()
        self.log.info("Discover BMC credentials and verify communications")
        print()
        nodes = {}
        bmc_ai = {}
        for node in node_addr_list:
            nodes[node] = False
        while not all([x for x in nodes.values()]) and attempt <= max_attempts:
            print(f'\rAttempt count: {max_attempts - attempt}  ', end='')
            sys.stdout.flush()
            attempt += 1
            timeout += 1
            node_list = [x for x in nodes if not nodes[x]]
            for node in node_list:
                # each time through re-sort cred_list based on nodes left with
                # those credentials to maximize the probability
                # of using the correct credentials with minimum attempts
                cred_list.sort(key=lambda x: x[3], reverse=True)
                for j, creds in enumerate(cred_list):
                    self.log.debug(f'BMC {node} - Trying userid: {creds[0]} | '
                                   f'password: {creds[1]} | bmc type: {creds[2]}')
                    bmc = _bmc.Bmc(node, *creds[:-1], timeout=timeout)
                    if bmc.is_connected():
                        r = bmc.chassis_power('status')
                        self.log.debug(f'Chassis power status: {r}')
                        if r:
                            nodes[node] = True
                            time.sleep(1)
                            self.log.debug(f'Node {node} is powered {r}')
                            bmc_ai[node] = tuple(cred_list[j][:-1])
                            cred_list[j][3] -= 1
                            left -= left
                            print(f'\r{tot - left} of {tot} nodes communicating via IPMI',
                                  end='')
                            sys.stdout.flush()
                            bmc.logout()
                        else:
                            self.log.debug(f'No power status response from node {node}')
            time.sleep(delay)
        if left != 0:
            self.log.error(f'IPMI communication successful with only {tot - left} '
                           f'of {tot} nodes')
        print('\n')
        return bmc_ai

    def _get_ipmi_ports(self, switch_lbl):
        """ Get all of the ipmi ports for a given switch
        Args:
            switch_lbl (str): switch label
        Returns:
            ports (list of str): port name or number
        """
        ports = []
        for node_tmpl_idx in self.cfg.yield_ntmpl_ind():
            for sw_idx in self.cfg.yield_ntmpl_phyintf_ipmi_ind(node_tmpl_idx):
                if switch_lbl == self.cfg.get_ntmpl_phyintf_ipmi_switch(
                        node_tmpl_idx, sw_idx):
                    ports += self.cfg.get_ntmpl_phyintf_ipmi_ports(
                        node_tmpl_idx, sw_idx)
        ports = [str(port) for port in ports]
        return ports

    def _get_pxe_ports(self, switch_lbl):
        """ Get all of the pxe ports for a given switch
        Args:
            switch_lbl (str): switch label
        Returns:
            ports (list of str): port name or number
        """
        ports = []
        for node_tmpl_idx in self.cfg.yield_ntmpl_ind():
            for sw_idx in self.cfg.yield_ntmpl_phyintf_pxe_ind(node_tmpl_idx):
                if switch_lbl == self.cfg.get_ntmpl_phyintf_pxe_switch(
                        node_tmpl_idx, sw_idx):
                    ports += self.cfg.get_ntmpl_phyintf_pxe_ports(
                        node_tmpl_idx, sw_idx)
        ports = [str(port) for port in ports]
        return ports

    def _get_port_table_ipmi(self, node_list):
        """ Build table of discovered nodes.  The responding IP addresses are
        correlated to MAC addresses in the dnsmasq.leases file.  The MAC
        address is then used to correlate the IP address to a switch port.
        Args:
            node_list (list of str): IPV4 addresses
        Returns:
            table (AttrDict): switch, switch port, IPV4 address, MAC address
        """
        dhcp_leases = GetDhcpLeases(self.dhcp_ipmi_leases_file)
        dhcp_mac_ip = dhcp_leases.get_mac_ip()

        dhcp_mac_table = AttrDict()
        for ip in node_list:
            for item in dhcp_mac_ip.items():
                if ip in item:
                    dhcp_mac_table[item[0]] = item[1]
        self.log.debug('ipmi mac-ip table')
        self.log.debug(dhcp_mac_table)

        for sw_ai in self.cfg.yield_sw_mgmt_access_info():
            sw = SwitchFactory.factory(*sw_ai[1:])
            label = sw_ai[0]
            ipmi_ports = self._get_ipmi_ports(label)
            mgmt_sw_cfg_mac_lists = \
                sw.show_mac_address_table(format='std')
            # Get switch ipmi port mac address table
            # Logic below maintains same port order as config.yml
            sw_ipmi_mac_table = AttrDict()
            for port in ipmi_ports:
                if port in mgmt_sw_cfg_mac_lists:
                    sw_ipmi_mac_table[port] = mgmt_sw_cfg_mac_lists[port]
            self.log.debug('Switch ipmi port mac table')
            self.log.debug(sw_ipmi_mac_table)

            if label not in self.node_table_ipmi.keys():
                self.node_table_ipmi[label] = []

            for port in sw_ipmi_mac_table:
                for mac in dhcp_mac_table:
                    if mac in sw_ipmi_mac_table[port]:
                        if not self._is_port_in_table(
                                self.node_table_ipmi[label], port):
                            self.node_table_ipmi[label].append(
                                [port, mac, dhcp_mac_table[mac]])

    def _build_port_table_pxe(self, mac_list):
        """ Build table of discovered nodes.  The responding mac addresses
        discovered by tcpdump are correlated to switch ports from cluster
        switches. If nodes have taken an ip address (via dnsmasq) the ip
        address is included in the table.
        Args:
            node_list (list of str): IPV4 addresses
        Returns:
            table (AttrDict): switch, switch port, IPV4 address, MAC address
        """
        dhcp_leases = GetDhcpLeases(self.dhcp_pxe_leases_file)
        dhcp_mac_ip = dhcp_leases.get_mac_ip()

        dhcp_mac_table = AttrDict()
        for mac in mac_list:
            for item in dhcp_mac_ip.items():
                if mac in item:
                    dhcp_mac_table[item[0]] = item[1]
        self.log.debug('pxe dhcp mac table')
        self.log.debug(dhcp_mac_table)

        for sw_ai in self.cfg.yield_sw_mgmt_access_info():
            sw = SwitchFactory.factory(*sw_ai[1:])
            sw_label = sw_ai[0]
            pxe_ports = self._get_pxe_ports(sw_label)
            mgmt_sw_mac_lists = \
                sw.show_mac_address_table(format='std')

            # Get switch pxe port mac address table
            # Logic below maintains same port order as config.yml
            sw_pxe_mac_table = AttrDict()
            for port in pxe_ports:
                if port in mgmt_sw_mac_lists:
                    sw_pxe_mac_table[port] = mgmt_sw_mac_lists[port]
            self.log.debug('Switch pxe port mac table')
            self.log.debug(sw_pxe_mac_table)

            # self.node_table_pxe is structured around switches
            if sw_label not in self.node_table_pxe.keys():
                self.node_table_pxe[sw_label] = []

            for mac in mac_list:
                _port = '-'
                for port in sw_pxe_mac_table:
                    if mac in sw_pxe_mac_table[port]:
                        _port = port
                        break
                if mac in dhcp_mac_table:
                    ip = dhcp_mac_table[mac]
                else:
                    ip = '-'
                if not self._is_val_in_table(
                        self.node_table_pxe[sw_label], mac):
                    self.node_table_pxe[sw_label].append(
                        [_port, mac, ip])

    def _reset_existing_bmcs(self, node_addr_list, cred_list):
        """ Attempts to reset any BMCs which have existing IP addresses since
        we don't have control over their address lease time.
        Args:
            node_addr_list (list): list of ipv4 addresses for the discovered
            nodes. (ie those that previously fetched an address from the DHCP
             server.
            cred_list (list of lists): Each list item is a list containing the
            the userid, password and number of nodes for a node template.
        """
        for node in node_addr_list:
            for j, creds in enumerate(cred_list):
                bmc = _bmc.Bmc(node, creds[0], creds[1], creds[2])
                if bmc.is_connected():
                    self.log.info(f'Resetting BMC with existing ip address: {node}')
                    if not bmc.bmc_reset('cold'):
                        self.log.error(f'Failed attempting BMC reset on {node}')
                    bmc.logout()
                    break

    def validate_ipmi(self):
        self.log.info("Discover and validate cluster nodes")
        # if self.inv.check_all_nodes_ipmi_macs() and self.inv.check_all_nodes_pxe_macs():
        #     self.log.info("Inventory exists with IPMI and PXE MACs populated.")
        #     print("\nPress Enter to continue cluster deployment without "
        #           "running IPMI hardware validation.")
        #     print("Type 'C' to validate cluster nodes defined in current "
        #           "'config.yml'")
        #     resp = input("Type 'T' to terminate Power-Up ")
        #     if resp == 'T':
        #         resp = input("Type 'y' to confirm ")
        #         if resp == 'y':
        #             self.log.info("'{}' entered. Terminating Power-Up at user "
        #                           "request".format(resp))
        #             sys.exit(1)
        #     elif resp == 'C':
        #         self.log.info("'{}' entered. Continuing with hardware "
        #                       "validation".format(resp))
        #     else:
        #         print()
        #         return
        ipmi_cnt, pxe_cnt = self._get_port_cnts()
        ipmi_addr, bridge_addr, ipmi_prefix, ipmi_vlan = self._get_network('ipmi')
        ipmi_network = ipmi_addr + '/' + str(ipmi_prefix)
        addr = IPNetwork(bridge_addr + '/' + str(ipmi_prefix))
        netmask = str(addr.netmask)
        ipmi_size = addr.size
        addr.value += NAME_SPACE_OFFSET_ADDR
        addr = str(addr)
        cred_list = self._get_cred_list()
        rc = False
        dhcp_st = get_dhcp_pool_start()
        self.ipmi_ns = NetNameSpace('ipmi-ns-', 'br-ipmi-' + str(ipmi_vlan), addr)

        # setup DHCP, unless already running in namesapce
        # save start and end addr raw numeric values
        self.log.debug('Installing DHCP server in network namespace')
        addr_st = self._add_offset_to_address(ipmi_network, dhcp_st)
        addr_end = self._add_offset_to_address(ipmi_network, ipmi_size - 2)
        dhcp_end = self._add_offset_to_address(ipmi_network, dhcp_st + ipmi_cnt + 2)

        # scan ipmi network for nodes with pre-existing ip addresses
        cmd = 'fping -r0 -a -g {} {}'.format(addr_st, addr_end)
        node_list, stderr, rc = sub_proc_exec(cmd)
        if rc not in (0, 1):
            self.log.warning(f'Error scanning IPMI network. rc: {rc}')
        self.log.debug('Pre-existing node list: \n{}'.format(node_list))
        node_list = node_list.splitlines()

        self._reset_existing_bmcs(node_list, cred_list)

        if len(node_list) > 0:
            print('Pause 60s for BMCs to begin reset')
            time.sleep(60)

        dns_list, stderr, rc = sub_proc_exec('pgrep dnsmasq')
        if rc not in [0, 1]:
            self.log.warning(f'Error looking for dnsmasq. rc: {rc}')
        dns_list = dns_list.splitlines()

        for pid in dns_list:
            ns_name, stderr, rc = sub_proc_exec('ip netns identify {}'.format(pid))
            if self.ipmi_ns._get_name_sp_name() in ns_name:
                self.log.debug('DHCP already running in {}'.format(ns_name))
                break
        else:
            cmd = (f'dnsmasq --dhcp-leasefile={self.dhcp_ipmi_leases_file} '
                   f'--interface={self.ipmi_ns._get_name_sp_ifc_name()} '
                   f'--dhcp-range={addr_st},{dhcp_end},{netmask},600')
            stdout, stderr, rc = self.ipmi_ns._exec_cmd(cmd)
            if rc != 0:
                self.log.warning(f'Error setting up dnsmasq. rc: {rc}')
            print(stderr)

        # Scan up to 25 times. Delay 5 seconds between scans
        # Allow infinite number of retries
        self.log.info('Scanning BMC network on 5 s intervals')
        cnt = 0
        cnt_down = 25
        while cnt < ipmi_cnt:
            print()
            for i in range(cnt_down):
                print('\r{} of {} nodes requesting DHCP address. Scan count: {} '
                      .format(cnt, ipmi_cnt, cnt_down - i), end="")
                sys.stdout.flush()
                time.sleep(5)
                cmd = 'fping -r0 -a -g {} {}'.format(addr_st, dhcp_end)
                stdout, stderr, rc = sub_proc_exec(cmd)
                node_list = stdout.splitlines()
                cnt = len(node_list)
                if cnt >= ipmi_cnt:
                    rc = True
                    print('\r{} of {} nodes requesting DHCP address. Scan count: {} '
                          .format(cnt, ipmi_cnt, cnt_down - i), end="")
                    break

            self._get_port_table_ipmi(node_list)
            self.log.debug('Table of found IPMI ports: {}'.format(self.node_table_ipmi))
            for switch in self.node_table_ipmi:
                print('\n\nSwitch: {}                '.format(switch))
                print(tabulate(self.node_table_ipmi[switch], headers=(
                    'port', 'MAC address', 'IP address')))
                print()

            if cnt >= ipmi_cnt:
                break
            print('\n\nPress Enter to continue scanning for cluster nodes.\nOr')
            print("Or enter 'C' to continue cluster deployment with a subset of nodes")
            resp = input("Or Enter 'T' to terminate Power-Up ")
            if resp == 'T':
                resp = input("Enter 'y' to confirm ")
                if resp == 'y':
                    self.log.info("'{}' entered. Terminating Power-Up at user request"
                                  .format(resp))
                    self._teardown_ns(self.ipmi_ns)
                    sys.exit(1)
            elif resp == 'C':
                print('\nNot all nodes have been discovered')
                resp = input("Enter 'y' to confirm continuation of"
                             " deployment without all nodes ")
                if resp == 'y':
                    self.log.info("'{}' entered. Continuing PowerUp".format(resp))
                    break
        self.node_list = node_list
        if cnt < ipmi_cnt:
            self.log.warning('Failed to validate expected number of nodes')

        if len(node_list) > 0 and len(cred_list) > 0:
            # Verify and power off nodes
            self.bmc_ai = self._get_credentials(node_list, cred_list)
            if not self.bmc_ai:
                self.log.error('Critical error. Unable to establish BMC communication '
                               'with any cluster nodes.\n.')
                sys.exit('Exiting.')

        # set_power_cients('off') has built in 60 s delay
        self.log.info('\nPowering off cluster nodes')
        set_power_clients('off', clients=self.bmc_ai)

        set_power_clients('on', clients=self.bmc_ai)

        self.log.debug('\nSetting "network" boot device on all nodes')
        set_bootdev_clients('network', clients=self.bmc_ai)

        self.log.debug('Cluster nodes IPMI validation complete')
        self.ran_ipmi = True
        if not rc:
            raise UserException('Not all node IPMI ports validated')

    def _get_cred_list(self):
        """Returns list of list.  Each list has the credentials
        for a node template(userid, password, bmc_type).
        Note that there is no association to any ip address.
        """
        cred_list = []
        for idx in self.cfg.yield_ntmpl_ind():
            for idx_ipmi in self.cfg.yield_ntmpl_phyintf_ipmi_ind(idx):
                port_cnt = self.cfg.get_ntmpl_phyintf_ipmi_pt_cnt(idx, idx_ipmi)
            cred_list.append([self.cfg.get_ntmpl_ipmi_userid(index=idx),
                             self.cfg.get_ntmpl_ipmi_password(index=idx),
                             self.cfg.get_ntmpl_bmc_type(index=idx),
                             port_cnt])
        return cred_list

    def _teardown_ns(self, ns):
        # kill dnsmasq
        dns_list, stderr, rc = sub_proc_exec('pgrep dnsmasq')
        dns_list = dns_list.splitlines()

        for pid in dns_list:
            ns_name, stderr, rc = sub_proc_exec('ip netns identify ' + pid)
            if ns._get_name_sp_name() in ns_name:
                self.log.debug('Killing dnsmasq {}'.format(pid))
                stdout, stderr, rc = sub_proc_exec('kill -15 ' + pid)

        # kill tcpdump
        tcpdump_list, stderr, rc = sub_proc_exec('pgrep tcpdump')
        tcpdump_list = tcpdump_list.splitlines()

        for pid in tcpdump_list:
            ns_name, stderr, rc = sub_proc_exec('ip netns identify ' + pid)
            if ns._get_name_sp_name() in ns_name:
                self.log.debug('Killing tcpdump {}'.format(pid))
                stdout, stderr, rc = sub_proc_exec('kill -15 ' + pid)

        # reconnect the veth pair to the container
        ns._reconnect_container()

        # Destroy the namespace
        self.log.debug('Destroying namespace')
        ns._destroy_name_sp()

    def _get_macs(self, mac_list, dump):
        """ Parse the data returned by tcpdump looking for pxe boot
        requests.
        Args:
            mac_list(list): list of already found mac addresses
            dump(str): tcpdump output from the tcpdump file
        """
        _mac_iee802 = r'([\dA-F]{2}[\.:-]){5}([\dA-F]{2})'
        _mac_regex = re.compile(_mac_iee802, re.I)

        dump = dump.split('BOOTP/DHCP, Request')

        for item in dump:
            # look first for 'magic cookie'
            pos = item.find('6382 5363')
            if pos >= 0:
                bootp = item[pos:]
                bootp = bootp[:2 + re.search(' ff|ff ', bootp, re.DOTALL).start()]
                # look for pxe request info.  0x37 = 55 (parameter list request)
                # 0x43 = 67 (boot filename request)
                # 0xd1 = 209 (pxeconfig file request)
                if ('37 ' in bootp or ' 37' in bootp):
                    if (' d1' in bootp or 'd1 ' in bootp) or \
                            ('43 ' in bootp or ' 43' in bootp):
                        self.log.debug('bootp param request field: {}'.format(bootp))
                        mac = _mac_regex.search(item).group()
                        if mac not in mac_list:
                            mac_list.append(mac)
        return mac_list

    def validate_pxe(self, bootdev='default', persist=True):
        # if self.inv.check_all_nodes_pxe_macs():
        #     self.log.info("Inventory exists with PXE MACs populated.")
        #     if not self.ran_ipmi:
        #         return
        #     print("\nPress Enter to continue cluster deployment without "
        #           "running PXE hardware validation.")
        #     print("Type 'C' to validate cluster nodes defined in current "
        #           "'config.yml'")
        #     resp = input("Type 'T' to terminate Power-Up ")
        #     if resp == 'T':
        #         resp = input("Type 'y' to confirm ")
        #         if resp == 'y':
        #             self.log.info("'{}' entered. Terminating Power-Up at user "
        #                           "request".format(resp))
        #             sys.exit(1)
        #     elif resp == 'C':
        #         self.log.info("'{}' entered. Continuing with hardware "
        #                       "validation".format(resp))
        #     else:
        #         print()
        #         return
        # if not self.ran_ipmi:
        #     return
        if not self.node_table_ipmi:
            raise UserCriticalException('No BMCs discovered')
        self.log.debug("Checking PXE networks and client PXE"
                       " ports ________\n")
        self.log.debug('Boot device: {}'.format(bootdev))
        ipmi_cnt, pxe_cnt = self._get_port_cnts()
        pxe_addr, bridge_addr, pxe_prefix, pxe_vlan = self._get_network('pxe')
        pxe_network = pxe_addr + '/' + str(pxe_prefix)
        addr = IPNetwork(bridge_addr + '/' + str(pxe_prefix))
        netmask = str(addr.netmask)
        addr.value += NAME_SPACE_OFFSET_ADDR
        addr = str(addr)
        foundall = False
        dhcp_st = get_dhcp_pool_start()
        pxe_ns = NetNameSpace('pxe-ns-', 'br-pxe-' + str(pxe_vlan), addr)

        # setup DHCP. save start and end addr raw numeric values
        self.log.debug('Installing DHCP server in network namespace')
        addr_st = self._add_offset_to_address(pxe_network, dhcp_st)
        addr_end = self._add_offset_to_address(pxe_network, dhcp_st + pxe_cnt + 2)

        dns_list, stderr, rc = sub_proc_exec('pgrep dnsmasq')
        dns_list = dns_list.splitlines()

        if os.path.exists(self.dhcp_pxe_leases_file):
            os.remove(self.dhcp_pxe_leases_file)

        # delete any remnant dnsmasq processes
        for pid in dns_list:
            ns_name, stderr, rc = sub_proc_exec('ip netns identify {}'.format(pid))
            if pxe_ns._get_name_sp_name() in ns_name:
                self.log.debug('Killing dnsmasq. pid {}'.format(pid))
                stdout, stderr, rc = sub_proc_exec('kill -15 ' + pid)

        cmd = (f'dnsmasq --dhcp-leasefile={self.dhcp_pxe_leases_file} '
               f'--interface={pxe_ns._get_name_sp_ifc_name()} '
               f'--dhcp-range={addr_st},{addr_end},{netmask},3600')
        stdout, stderr, rc = pxe_ns._exec_cmd(cmd)
        if rc != 0:
            self.log.warning(f'Error configuring dnsmasq. rc: {rc}')

        if os.path.exists(self.tcp_dump_file):
            os.remove(self.tcp_dump_file)

        tcpdump_list, stderr, rc = sub_proc_exec('pgrep tcpdump')
        tcpdump_list = tcpdump_list.splitlines()

        # delete any remnant tcpdump processes
        for pid in tcpdump_list:
            ns_name, stderr, rc = sub_proc_exec('ip netns identify ' + pid)
            if pxe_ns._get_name_sp_name() in ns_name:
                self.log.debug('Killing tcpdump. pid {}'.format(pid))
                stdout, stderr, rc = sub_proc_exec('kill -15 ' + pid)

        cmd = (f'sudo tcpdump -X -U -i {pxe_ns._get_name_sp_ifc_name()} '
               f'-w {self.tcp_dump_file} --immediate-mode  port 67')
        proc = pxe_ns._launch_cmd(cmd)
        if not isinstance(proc, object):
            self.log.error(f'Failure to launch process of tcpdump monitor {proc}')

        # Scan up to 25 times. Delay 10 seconds between scans
        # Allow infinite number of retries
        self.log.info('Scanning pxe network on 10 s intervals.')
        cnt = 0
        cnt_prev = 0
        cnt_down = 25
        mac_list = []
        dump = ''
        while cnt < pxe_cnt:
            print()
            cmd = 'sudo tcpdump -r {} -xx'.format(self.tcp_dump_file)
            for i in range(cnt_down):
                print('\r{} of {} nodes requesting PXE boot. Scan cnt: {} '
                      .format(cnt, pxe_cnt, cnt_down - i), end="")
                sys.stdout.flush()
                time.sleep(10)
                # read the tcpdump file if size is not 0
                if os.path.exists(self.tcp_dump_file) and os.path.getsize(self.tcp_dump_file):
                    dump, stderr, rc = sub_proc_exec(cmd)
                    if rc != 0:
                        self.log.warning(f'Error reading tcpdump file. rc: {rc}')
                    if 'reading' not in stderr:
                        self.log.warning(f'Failure reading tcpdump file - {stderr}')
                mac_list = self._get_macs(mac_list, dump)
                cnt = len(mac_list)
                if cnt > cnt_prev:
                    cnt_prev = cnt
                    # Pause briefly for in flight DHCP to complete and lease file to update
                    time.sleep(5)
                    self._build_port_table_pxe(mac_list)
                if cnt >= pxe_cnt:
                    foundall = True
                    print('\r{} of {} nodes requesting PXE boot. Scan count: {} '
                          .format(cnt, pxe_cnt, cnt_down - i), end="")
                    break
            self.log.debug('Table of found PXE ports: {}'.format(self.node_table_pxe))
            for switch in self.node_table_pxe:
                print('\n\nSwitch: {}'.format(switch))
                print(tabulate(self.node_table_pxe[switch], headers=(
                    'port', 'MAC address', 'IP address')))
                print()

            if cnt >= pxe_cnt:
                break
            print('\n\nPress Enter to continue scanning for cluster nodes.')
            print("Or enter 'C' to continue cluster deployment with a subset of nodes")
            print("Or enter 'R' to cycle power to missing nodes")
            resp = input("Or enter 'T' to terminate Power-Up ")
            if resp == 'T':
                resp = input("Enter 'y' to confirm ")
                if resp == 'y':
                    self.log.info("'{}' entered. Terminating Power-Up at user"
                                  " request".format(resp))
                    self._teardown_ns(self.ipmi_ns)
                    self._teardown_ns(pxe_ns)
                    sys.exit(1)
            elif resp == 'R':
                self._reset_unfound_nodes()
            elif resp == 'C':
                print('\nNot all nodes have been discovered')
                resp = input("Enter 'y' to confirm continuation of"
                             " deployment without all nodes ")
                if resp == 'y':
                    self.log.info("'{}' entered. Continuing Power-Up".format(resp))
                    break
        if cnt < pxe_cnt:
            self.log.warning('Failed to validate expected number of nodes')

        self._teardown_ns(pxe_ns)

        # Cycle power on all discovered nodes if bootdev set to 'network'
        if bootdev == 'network':
            self.log.debug('\nCycling power to discovered nodes.\n')
            set_power_clients('off', clients=self.bmc_ai)

            set_power_clients('on', clients=self.bmc_ai)

            set_bootdev_clients('network', clients=self.bmc_ai)

        self._teardown_ns(self.ipmi_ns)

        # Reset BMCs to insure they acquire a new address from container
        # during inv_add_ports. Avoids conflicting addresses during redeploy
        self._reset_existing_bmcs(self.node_list, self._get_cred_list())

        self.log.info('Cluster nodes validation complete')
        if not foundall:
            raise UserException('Not all node PXE ports validated')

    def _reset_unfound_nodes(self):
        """ Power cycle the nodes who's PXE ports are not requesting pxe boot.
        """
        ipmi_missing_list_ai = {}
        for label in self.cfg.yield_sw_mgmt_label():
            pxe_ports = self._get_pxe_ports(label)
            ipmi_ports = self._get_ipmi_ports(label)
            for node in self.node_table_ipmi[label]:
                if node[0] in ipmi_ports:
                    idx = ipmi_ports.index(node[0])
                    if label not in self.node_table_pxe or not self._is_port_in_table(
                            self.node_table_pxe[label], pxe_ports[idx]):
                        ipmi_missing_list_ai[node[2]] = self.bmc_ai[node[2]]
        self.log.debug(f'Cycling power to missing nodes list: {ipmi_missing_list_ai}')

        print('Cycling power to non responding nodes:')
        for node in ipmi_missing_list_ai:
            print(node)
        t1 = time.time()
        self._power_all(ipmi_missing_list_ai, 'off')

        while time.time() < t1 + 10:
            time.sleep(0.5)

        self._power_all(ipmi_missing_list_ai, 'on', bootdev='network')

    def _is_port_in_table(self, table, port):
        for node in table:
            if port == node[0]:
                self.log.debug('Table port: {} port: {}'.format(node[0], port))
                return True
        return False

    def _is_val_in_table(self, table, val):
        for item in table:
            if val == item[0] or val == item[1]:
                self.log.debug('Found in table: {} item: {}'.format(val, item))
                return True
        return False

    def _get_network(self, type_):
        """Returns details of a Power-Up network.
        Args:
            type_ (str): Either 'pxe' or 'ipmi'
        Returns:
            network_addr: (str) ipv4 addr
            bridge_ipaddr: (str) ipv4 addr
            netprefix: (str)
            vlan: (str)
        """
        types = self.cfg.get_depl_netw_client_type()
        bridge_ipaddr = self.cfg.get_depl_netw_client_brg_ip()
        vlan = self.cfg.get_depl_netw_client_vlan()
        netprefix = self.cfg.get_depl_netw_client_prefix()
        idx = types.index(type_)

        network = IPNetwork(bridge_ipaddr[idx] + '/' + str(netprefix[idx]))
        network_addr = str(network.network)
        return network_addr, bridge_ipaddr[idx], netprefix[idx], vlan[idx]

    def validate_data_switches(self):
        self.log.info('Verifying data switches')

        sw_cnt = self.cfg.get_sw_data_cnt()
        self.log.debug('Number of data switches defined in config file: {}'.
                       format(sw_cnt))

        for index, switch_label in enumerate(self.cfg.yield_sw_data_label()):
            print('.', end="")
            sys.stdout.flush()
            label = self.cfg.get_sw_data_label(index)
            self.log.debug('switch_label: {}'.format(switch_label))

            switch_class = self.cfg.get_sw_data_class(index)
            if not switch_class:
                self.log.error('No switch class found')
                return False
            userid = None
            password = None
            rc = True

            try:
                userid = self.cfg.get_sw_data_userid(index)
            except AttributeError:
                self.log.info('Passive switch mode specified')
                return True

            try:
                password = self.cfg.get_sw_data_password(index)
            except AttributeError:
                try:
                    self.cfg.get_sw_data_ssh_key(index)
                except AttributeError:
                    return True
                else:
                    self.log.error(
                        'Switch authentication via ssh keys not yet supported')
                    return False
            # Verify communication on each defined interface
            for ip in self.cfg.yield_sw_data_interfaces_ip(index):
                self.log.debug('Verifying switch communication on ip'
                               ' address: {}'.format(ip))
                sw = SwitchFactory.factory(
                    switch_class,
                    ip,
                    userid,
                    password,
                    'active')
                if sw.is_pingable():
                    self.log.debug(
                        'Successfully pinged data switch \"%s\" at %s' %
                        (label, ip))
                else:
                    self.log.warning(
                        'Failed to ping data switch \"%s\" at %s' % (label, ip))
                    rc = False
                try:
                    vlans = sw.show_vlans()
                    if vlans and len(vlans) > 1:
                        self.log.debug(
                            'Successfully communicated with data switch \"%s\"'
                            ' at %s' % (label, ip))
                    else:
                        self.log.warning(
                            'Failed to communicate with data switch \"%s\"'
                            'at %s' % (label, ip))
                        rc = False
                except (SwitchException, SSH_Exception):
                    self.log.error('Failed communicating with data switch'
                                   ' at address {}'.format(ip))
                    rc = False
        print()
        if rc:
            self.log.debug(' OK - All data switches verified')
        else:
            raise UserException('Failed verification of data switches')

    def validate_mgmt_switches(self):
        self.log.info('Verifying management switches')

        sw_cnt = self.cfg.get_sw_mgmt_cnt()
        self.log.debug('Number of management switches defined in config file: {}'.
                       format(sw_cnt))

        for index, switch_label in enumerate(self.cfg.yield_sw_mgmt_label()):
            print('.', end="")
            sys.stdout.flush()
            label = self.cfg.get_sw_mgmt_label(index)
            self.log.debug('switch_label: {}'.format(switch_label))

            switch_class = self.cfg.get_sw_mgmt_class(index)
            if not switch_class:
                self.log.error('No switch class found')
                return False
            userid = None
            password = None
            rc = True

            try:
                userid = self.cfg.get_sw_mgmt_userid(index)
            except AttributeError:
                self.log.debug('Passive switch mode specified')
                return rc

            try:
                password = self.cfg.get_sw_mgmt_password(index)
            except AttributeError:
                try:
                    self.cfg.get_sw_mgmt_ssh_key(index)
                except AttributeError:
                    return rc
                else:
                    self.log.error(
                        'Switch authentication via ssh keys not yet supported')
                    rc = False
            # Verify communication on each defined interface
            for ip in self.cfg.yield_sw_mgmt_interfaces_ip(index):
                self.log.debug('Verifying switch communication on ip address:'
                               ' {}'.format(ip))
                sw = SwitchFactory.factory(
                    switch_class,
                    ip,
                    userid,
                    password,
                    'active')
                if sw.is_pingable():
                    self.log.debug(
                        'Successfully pinged management switch \"%s\" at %s' %
                        (label, ip))
                else:
                    self.log.warning(
                        'Failed to ping management switch \"%s\" at %s' %
                        (label, ip))
                    rc = False
                try:
                    vlans = sw.show_vlans()
                except (SwitchException, SSH_Exception):
                    self.log.error('Failed communicating with management switch'
                                   ' at address {}'.format(ip))
                    rc = False

                if vlans and len(vlans) > 1:
                    self.log.debug(
                        'Successfully communicated with management switch \"%s\"'
                        ' at %s' % (label, ip))
                else:
                    self.log.warning(
                        'Failed to communicate with data switch \"%s\"'
                        'at %s' % (label, ip))
                    rc = False
        print()
        if rc:
            self.log.debug(' OK - All management switches verified')
        else:
            raise UserCriticalException('Failed verification of management switches')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('config_path', default='config.yml',
                        help='Config file path.  Absolute path or relative '
                        'to power-up/')

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
    main(args.config_path)
