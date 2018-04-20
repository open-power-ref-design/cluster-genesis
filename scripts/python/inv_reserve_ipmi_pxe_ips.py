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

import xmlrpclib
from netaddr import IPNetwork
from pyghmi.ipmi import command as ipmi_command
from pyghmi import exceptions as pyghmi_exception
from time import time

from lib.config import Config
from lib.inventory import Inventory
import lib.genesis as gen
import lib.utilities as util
from ipmi_power_off import ipmi_power_off
from lib.exception import UserException
import lib.logger as logger

DNSMASQ_TEMPLATE = '/etc/cobbler/dnsmasq.template'
COBBLER_USER = gen.get_cobbler_user()
COBBLER_PASS = gen.get_cobbler_pass()
WAIT_TIME = 1200
POWER_TIME_OUT = gen.get_power_time_out()
POWER_WAIT = gen.get_power_wait()
SLEEP_TIME = gen.get_power_sleep_time()


class IPManager(object):
    """Manage IP address assignments from a given network

    Args:
        network (IPNetwork): netaddr IPNetwork object
        start_offset (int): Starting IP address offset
    """

    def __init__(self, network, start_offset):
        self.log = logger.getlogger()
        self.network = network
        self.next_offset = start_offset
        self.next_ip = network.network + self.next_offset

    def get_next_ip(self, reserve=True):
        """Get next available sequential IP address

        Args:
            reserve (bool): If true the IP will be considered reserved

        Returns:
            ip_address (str): Next IP address

        Raises:
            UserException: No more IP addresses available
        """
        if self.next_ip == self.network.network + self.network.size:
            raise UserException('Not enough IP addresses in network \'%s\'' %
                                str(self.network.cidr))
        ip_address = str(self.next_ip)
        if reserve:
            self.next_ip += 1
        return ip_address


def inv_set_ipmi_pxe_ip():
    """Configure DHCP IP reservations for IPMI and PXE interfaces

    IP addresses are assigned sequentially within the appropriate
    client networks starting with the DHCP pool start offset defined
    in 'lib.genesis'.

    Raises:
        UserException: - No IPMI or PXE client networks defined within
                         the 'config.yml'
                       - Unable to connect to BMC at new IPMI IP address
    """
    log = logger.getlogger()
    cfg = Config()
    inv = Inventory()

    ipmiNetwork = None
    pxeNetwork = None
    nodes_list = []

    # All nodes should be powered off before starting
    ipmi_power_off(POWER_TIME_OUT, POWER_WAIT)

    # Create IPManager object for IPMI and/or PXE networks
    start_offset = gen.get_dhcp_pool_start()
    for index, netw_type in enumerate(cfg.yield_depl_netw_client_type()):
        ip = cfg.get_depl_netw_client_cont_ip(index)
        netmask = cfg.get_depl_netw_client_netmask(index)
        if netw_type == 'ipmi':
            ipmiNetwork = IPManager(IPNetwork(ip + '/' + netmask), start_offset)
        elif netw_type == 'pxe':
            pxeNetwork = IPManager(IPNetwork(ip + '/' + netmask), start_offset)

    # If only one network is defined use the same IPManager for both
    if ipmiNetwork is None and pxeNetwork is not None:
        ipmiNetwork = pxeNetwork
    elif ipmiNetwork is not None and pxeNetwork is None:
        pxeNetwork = ipmiNetwork
    elif ipmiNetwork is None and pxeNetwork is None:
        raise UserException('No IPMI or PXE client network found')

    # Modify IP addresses for each node
    dhcp_lease_time = cfg.get_globals_dhcp_lease_time()
    for index, hostname in enumerate(inv.yield_nodes_hostname()):
        # IPMI reservations are written directly to the dnsmasq template
        ipmi_ipaddr = inv.get_nodes_ipmi_ipaddr(0, index)
        ipmi_mac = inv.get_nodes_ipmi_mac(0, index)
        ipmi_new_ipaddr = ipmiNetwork.get_next_ip()
        util.remove_line(DNSMASQ_TEMPLATE, "^dhcp-host=" + ipmi_mac + ".*")
        util.append_line(DNSMASQ_TEMPLATE, 'dhcp-host=%s,%s-bmc,%s,%s\n' %
                         (ipmi_mac, hostname, ipmi_new_ipaddr,
                          dhcp_lease_time))
        _adjust_dhcp_pool(ipmiNetwork.network,
                          ipmiNetwork.get_next_ip(reserve=False),
                          dhcp_lease_time)

        # PXE reservations are handled by Cobbler
        pxe_ipaddr = inv.get_nodes_pxe_ipaddr(0, index)
        pxe_mac = inv.get_nodes_pxe_mac(0, index)
        pxe_new_ipaddr = pxeNetwork.get_next_ip()
        log.info('Modifying Inventory PXE IP - Node: %s MAC: %s '
                 'Original IP: %s New IP: %s' %
                 (hostname, pxe_mac, pxe_ipaddr, pxe_new_ipaddr))
        inv.set_nodes_pxe_ipaddr(0, index, pxe_new_ipaddr)
        _adjust_dhcp_pool(pxeNetwork.network,
                          pxeNetwork.get_next_ip(reserve=False),
                          dhcp_lease_time)

        # Run Cobbler sync to process DNSMASQ template
        cobbler_server = xmlrpclib.Server("http://127.0.0.1/cobbler_api")
        token = cobbler_server.login(COBBLER_USER, COBBLER_PASS)
        cobbler_server.sync(token)
        log.debug("Running Cobbler sync")

        # Save info to verify connection come back up
        ipmi_userid = inv.get_nodes_ipmi_userid(index)
        ipmi_password = inv.get_nodes_ipmi_password(index)
        # No need to reset and check if the IP does not change
        if ipmi_new_ipaddr != ipmi_ipaddr:
            nodes_list.append({'hostname': hostname,
                               'index': index,
                               'ipmi_userid': ipmi_userid,
                               'ipmi_password': ipmi_password,
                               'ipmi_new_ipaddr': ipmi_new_ipaddr,
                               'ipmi_ipaddr': ipmi_ipaddr,
                               'ipmi_mac': ipmi_mac})

    # Issue MC cold reset to force refresh of IPMI interfaces
    for node in nodes_list:
        ipmi_userid = node['ipmi_userid']
        ipmi_password = node['ipmi_password']
        ipmi_ipaddr = node['ipmi_ipaddr']
        ipmi_cmd = ipmi_command.Command(bmc=ipmi_ipaddr,
                                        userid=ipmi_userid,
                                        password=ipmi_password)
        ipmi_cmd.reset_bmc()
        del ipmi_cmd
        log.debug('BMC Cold Reset Issued - Node: %s - IP: %s' %
                  (hostname, ipmi_ipaddr))

    # Check connections for set amount of time
    end_time = time() + WAIT_TIME
    while time() < end_time and len(nodes_list) > 0:
        success_list = []
        for list_index, node in enumerate(nodes_list):
            hostname = node['hostname']
            index = node['index']
            ipmi_userid = node['ipmi_userid']
            ipmi_password = node['ipmi_password']
            ipmi_new_ipaddr = node['ipmi_new_ipaddr']
            ipmi_ipaddr = node['ipmi_ipaddr']
            ipmi_mac = node['ipmi_mac']

            # Attempt to connect to new IPMI IP address
            try:
                ipmi_cmd = ipmi_command.Command(
                    bmc=ipmi_new_ipaddr,
                    userid=ipmi_userid,
                    password=ipmi_password)
                status = ipmi_cmd.get_power()
            except pyghmi_exception.IpmiException as error:
                log.debug('BMC connection failed - Node: %s IP: %s, %s '
                          '(Retrying for %s seconds)' %
                          (hostname, ipmi_new_ipaddr, str(error), WAIT_TIME))
                continue

            # If connection sucessful modify inventory
            if status.get('powerstate') in ['on', 'off']:
                log.debug('BMC connection success - Node: %s IP: %s' %
                          (hostname, ipmi_new_ipaddr))
                log.info('Modifying Inventory IPMI IP - Node: %s MAC: %s '
                         'Original IP: %s New IP: %s' %
                         (hostname, ipmi_mac, ipmi_ipaddr, ipmi_new_ipaddr))
                inv.set_nodes_ipmi_ipaddr(0, index, ipmi_new_ipaddr)
                success_list.append(list_index)

        # Remove nodes that connected successfully
        for remove_index in sorted(success_list, reverse=True):
            del nodes_list[remove_index]

    for node in nodes_list:
        log.error('Unable to connect to BMC at new IPMI IP address- Node: %s '
                  'MAC: %s Original IP: %s New IP: %s' %
                  (hostname, ipmi_mac, ipmi_ipaddr, ipmi_new_ipaddr))
    if len(nodes_list) > 0:
        raise UserException('%d BMC(s) not responding after IP modification' %
                            len(nodes_list))


def _adjust_dhcp_pool(network, dhcp_pool_start, dhcp_lease_time):
    dhcp_range = 'dhcp-range=%s,%s,%s  # %s'
    new_entry = dhcp_range % (dhcp_pool_start,
                              str(network.network + network.size - 1),
                              str(dhcp_lease_time),
                              str(network.cidr))

    entry = "^dhcp-range=.* # " + str(network.cidr)
    util.replace_regex(DNSMASQ_TEMPLATE, entry, new_entry)


if __name__ == '__main__':

    logger.create()
    inv_set_ipmi_pxe_ip()
