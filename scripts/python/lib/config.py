"""Config"""

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

import sys
from enum import Enum
import netaddr
from itertools import chain

import lib.logger as logger
from lib.db import DatabaseConfig
from lib.exception import UserException


class Config(object):
    """Config
    """

    class SwitchType(Enum):
        MGMT, DATA = range(2)

    class CfgKey(object):
        LABEL = 'label'
        HOSTNAME = 'hostname'
        USERID = 'userid'
        PASSWORD = 'password'
        SSH_KEY = 'ssh_key'
        ROOM = 'room'
        ROW = 'row'
        CELL = 'cell'
        IPADDR = 'ipaddr'
        PORT = 'port'
        PORTS = 'ports'
        TYPE = 'type'
        SWITCH = 'switch'
        RACK_ID = 'rack_id'
        RACK_EIA = 'rack_eia'
        HOSTNAME_PREFIX = 'hostname_prefix'
        DEVICE = 'device'
        INTERFACE = 'interface'
        INTERFACE_IPADDR = 'interface_ipaddr'
        CONTAINER_IPADDR = 'container_ipaddr'
        BRIDGE_IPADDR = 'bridge_ipaddr'
        VLAN = 'vlan'
        VIP = 'vip'
        NETMASK = 'netmask'
        PREFIX = 'prefix'
        TARGET = 'target'
        SWITCH = 'switch'
        CLASS = 'class'
        RENAME = 'rename'
        INTERFACE = 'interface'
        IFACE = 'iface'
        INTERFACE_DEVICE = 'DEVICE'
        INTERFACES = 'interfaces'
        NETWORKS = 'networks'
        ADDRESS_LIST = 'address_list'
        ADDRESS_START = 'address_start'
        IPADDR_LIST = 'IPADDR_list'
        IPADDR_START = 'IPADDR_start'
        SOFTWARE_BOOTSTRAP = 'software_bootstrap'

    def __init__(self, cfg=None):
        self.log = logger.getlogger()
        if cfg:
            self.cfg = cfg
        else:
            dbase = DatabaseConfig()
            self.cfg = dbase.load_config()

    @staticmethod
    def _netmask_to_prefix(netmask):
        """Convert Netmask to Prefix
        Args:
            netmask (str): Netmask

        Returns:
            int: Prefix
        """
        if netaddr.IPAddress(netmask).is_netmask():
            return (netaddr.IPAddress(netmask).bits()).count('1')
        else:
            return 32

    @staticmethod
    def _prefix_to_netmask(prefix):
        """Convert Prefix to Netmask
        Args:
            prefix (int): Prefix

        Returns:
            str: Netmask
        """

        return str(netaddr.IPNetwork('255.255.255.255/' + str(prefix)).netmask)

    def _netmask_prefix_not_found(self):
        """Check if Netmask or Prefix is specified
        Raises:
            Exception: If neither Netmask nor Prefix is specified
        """
        try:
            raise Exception()
        except Exception:
            self.log.error("Neither 'netmask' nor 'prefix' is specified")
            sys.exit(1)

    @staticmethod
    def _get_members(obj_list, key, index):
        """Get dictionary value under a list
        Args:
            obj_list (list): Object list
            key (dict key): Dictionary key
            index (int): Index

        Returns:
            list or obj: Members or member
        """

        if index is None:
            list_ = []
            for member in obj_list:
                if key in member:
                    list_.append(getattr(member, key))
                else:
                    list_.append(None)
            return list_
        if key in obj_list[index]:
            ret = getattr(obj_list[index], key)
            if isinstance(ret, list):
                return ret[:]
            else:
                return ret

    def get_version(self):
        """Get version
        Returns:
            str: Config file version
        """

        return self.cfg.version

    def get_globals_env_variables(self):
        """Get globals env_variables
        Returns:
            dict: env_variables
        """

        try:
            return self.cfg.globals.env_variables
        except AttributeError:
            return {}

    def get_globals_dhcp_lease_time(self):
        """Get globals dhcp_lease_time
        Returns:
            str: dhcp_lease_time
        """

        try:
            return str(self.cfg.globals.dhcp_lease_time)
        except AttributeError:
            return "1h"

    def is_passive_mgmt_switches(self):
        """Get management switch mode
        Returns:
            bool:
        """
        try:
            mode = self.cfg.globals.switch_mode_mgmt
        except AttributeError:
            return False
        if mode == 'passive':
            return True
        return False

    def is_passive_data_switches(self):
        """Get data switch mode
        Returns:
            bool:
        """
        try:
            mode = self.cfg.globals.switch_mode_data
        except AttributeError:
            return False
        if mode == 'passive':
            return True
        return False

    def get_loc_time_zone(self):
        """Get location time_zone
        Returns:
            str: Time zone
        """

        return self.cfg.location.time_zone

    def get_loc_data_center(self):
        """Get location data_center
        Returns:
            str: Data center
        """

        return self.cfg.location.data_center

    def get_loc_racks_cnt(self):
        """Get location racks count
        Returns:
            int: Racks count
        """

        return len(self.cfg.location.racks)

    def get_loc_racks_label(self, index=None):
        """Get location racks label
        Args:
            index (int, optional): List index

        Returns:
            str or list of str: Label member or list
        """

        return self._get_members(
            self.cfg.location.racks, self.CfgKey.LABEL, index)

    def get_loc_racks_room(self, index=None):
        """Get location racks room
        Args:
            index (int, optional): List index

        Returns:
            str or list of str: Room member or list
        """

        return self._get_members(
            self.cfg.location.racks, self.CfgKey.ROOM, index)

    def get_loc_racks_row(self, index=None):
        """Get location racks row
        Args:
            index (int, optional): List index

        Returns:
            str or list of str: Row member or list
        """

        return self._get_members(
            self.cfg.location.racks, self.CfgKey.ROW, index)

    def get_loc_racks_cell(self, index=None):
        """Get location racks cell
        Args:
            index (int, optional): List index

        Returns:
            str or list of str: Cell member or list
        """

        return self._get_members(
            self.cfg.location.racks, self.CfgKey.CELL, index)

    def get_depl_gateway(self):
        """Get deployer gateway setting
        Returns:
            bool: deployer gateway
        """

        try:
            return self.cfg.deployer.gateway
        except AttributeError:
            return False

    def get_depl_netw_mgmt_cnt(self):
        """Get deployer networks mgmt count
        Returns:
            int: Deployer management network count
        """

        return len(self.cfg.deployer.networks.mgmt)

    def get_depl_netw_mgmt_device(self, index=None):
        """Get deployer networks mgmt device
        Args:
            index (int, optional): List index

        Returns:
            str: Network device
        """

        return self._get_members(
            self.cfg.deployer.networks.mgmt,
            self.CfgKey.DEVICE,
            index)

    def yield_depl_netw_mgmt_device(self):
        """Yield deployer networks mgmt device
        Returns:
            iter of str: Network device
        """

        for member in self.get_depl_netw_mgmt_device():
            yield member

    def get_depl_netw_mgmt_intf_ip(self, index=None):
        """Get deployer networks mgmt interface_ipaddr
        Args:
            index (int, optional): List index

        Returns:
            str: Interface IP address
        """

        return self._get_members(
            self.cfg.deployer.networks.mgmt,
            self.CfgKey.INTERFACE_IPADDR,
            index)

    def yield_depl_netw_mgmt_intf_ip(self):
        """Yield deployer networks mgmt interface_ipaddr
        Returns:
            iter of str: Interface IP address
        """

        for member in self.get_depl_netw_mgmt_intf_ip():
            yield member

    def get_depl_netw_mgmt_cont_ip(self, index=None):
        """Get deployer networks mgmt container_ipaddr
        Args:
            index (int, optional): List index

        Returns:
            str: Container IP address
        """

        return self._get_members(
            self.cfg.deployer.networks.mgmt,
            self.CfgKey.CONTAINER_IPADDR,
            index)

    def yield_depl_netw_mgmt_cont_ip(self):
        """Yield deployer networks mgmt container_ipaddr
        Returns:
            iter of str: Container IP address
        """

        for member in self.get_depl_netw_mgmt_cont_ip():
            yield member

    def get_depl_netw_cont_ip(self):
        """Get single deployer networks container_ipaddr

        Returns:
            str: Container IP address
        """

        for ip in chain(self.yield_depl_netw_mgmt_cont_ip(),
                        self.yield_depl_netw_client_cont_ip()):
            if ip is not None:
                return ip

    def get_depl_netw_mgmt_brg_ip(self, index=None):
        """Get deployer networks mgmt bridge_ipaddr
        Args:
            index (int, optional): List index

        Returns:
            str: Bridge IP address
        """

        return self._get_members(
            self.cfg.deployer.networks.mgmt, self.CfgKey.BRIDGE_IPADDR, index)

    def yield_depl_netw_mgmt_brg_ip(self):
        """Yield deployer networks mgmt bridge_ipaddr
        Returns:
            iter of str: Bridge IP address
        """

        for member in self.get_depl_netw_mgmt_brg_ip():
            yield member

    def get_depl_netw_mgmt_vlan(self, index=None):
        """Get deployer networks mgmt vlan
        Args:
            index (int, optional): List index

        Returns:
            int: VLAN
        """

        return self._get_members(
            self.cfg.deployer.networks.mgmt, self.CfgKey.VLAN, index)

    def yield_depl_netw_mgmt_vlan(self):
        """Yield deployer networks mgmt vlan
        Returns:
            iter of str: VLAN
        """

        for member in self.get_depl_netw_mgmt_vlan():
            yield member

    def get_depl_netw_mgmt_netmask(self, index=None):
        """Get deployer networks mgmt netmask
        Returns:
            str or iter of str: Netmask
        """

        if index is None:
            list_ = []
            for member in self.cfg.deployer.networks.mgmt:
                if self.CfgKey.NETMASK in member:
                    list_.append(member[self.CfgKey.NETMASK])
                elif self.CfgKey.PREFIX in member:
                    list_.append(self._prefix_to_netmask(
                        member[self.CfgKey.PREFIX]))
                else:
                    self._netmask_prefix_not_found()
            return list_
        else:
            member = self.cfg.deployer.networks.mgmt[index]
            if self.CfgKey.NETMASK in member:
                return member[self.CfgKey.NETMASK]
            elif self.CfgKey.PREFIX in member:
                return self._prefix_to_netmask(member[self.CfgKey.PREFIX])
            else:
                self._netmask_prefix_not_found()

    def yield_depl_netw_mgmt_netmask(self):
        """Yield deployer networks mgmt netmask
        Returns:
            iter of str: Netmask
        """

        for member in self.get_depl_netw_mgmt_netmask():
            yield member

    def get_depl_netw_mgmt_prefix(self, index=None):
        """Get deployer networks mgmt prefix
        Returns:
            str or iter of str: Prefix
        """

        if index is None:
            list_ = []
            for member in self.cfg.deployer.networks.mgmt:
                if self.CfgKey.PREFIX in member:
                    list_.append(member[self.CfgKey.PREFIX])
                elif self.CfgKey.NETMASK in member:
                    list_.append(self._netmask_to_prefix(
                        member[self.CfgKey.NETMASK]))
                else:
                    self._netmask_prefix_not_found()
            return list_
        else:
            member = self.cfg.deployer.networks.mgmt[index]
            if self.CfgKey.PREFIX in member:
                return member[self.CfgKey.PREFIX]
            elif self.CfgKey.NETMASK in member:
                return self._netmask_to_prefix(member[self.CfgKey.NETMASK])
            else:
                self._netmask_prefix_not_found()

    def yield_depl_netw_mgmt_prefix(self):
        """Yield deployer networks mgmt prefix
        Returns:
            iter of str: Prefix
        """

        for member in self.get_depl_netw_mgmt_prefix():
            yield member

    def get_depl_netw_client_cnt(self):
        """Get deployer networks client count
        Returns:
            int: Deployer client network count
        """

        return len(self.cfg.deployer.networks.client)

    def get_depl_netw_client_type(self, index=None):
        """Get deployer networks client type
        Args:
            index (int, optional): List index

        Returns:
            str: Client type (ipmi or pxe)
        """

        return self._get_members(
            self.cfg.deployer.networks.client,
            self.CfgKey.TYPE,
            index)

    def yield_depl_netw_client_type(self):
        """Yield deployer networks client type
        Returns:
            iter of str: Network type
        """

        for member in self.get_depl_netw_client_type():
            yield member

    def get_depl_netw_client_device(self, index=None):
        """Get deployer networks client device
        Args:
            index (int, optional): List index

        Returns:
            str: Device name
        """

        return self._get_members(
            self.cfg.deployer.networks.client,
            self.CfgKey.DEVICE,
            index)

    def yield_depl_netw_client_device(self):
        """Yield deployer networks client device
        Returns:
            iter of str: Network device
        """

        for member in self.get_depl_netw_client_device():
            yield member

    def get_depl_netw_client_intf_ip(self, index=None):
        """Get deployer networks client interface_ipaddr
        Args:
            index (int, optional): List index

        Returns:
            str: Interface IP address
        """

        return self._get_members(
            self.cfg.deployer.networks.client,
            self.CfgKey.INTERFACE_IPADDR,
            index)

    def yield_depl_netw_client_intf_ip(self):
        """Yield deployer networks client interface_ipaddr
        Returns:
            iter of str: Interface IP address
        """

        for member in self.get_depl_netw_client_intf_ip():
            yield member

    def get_depl_netw_client_cont_ip(self, index=None):
        """Get deployer networks client container_ipaddr
        Args:
            index (int, optional): List index

        Returns:
            str: Container IP address
        """

        return self._get_members(
            self.cfg.deployer.networks.client,
            self.CfgKey.CONTAINER_IPADDR,
            index)

    def yield_depl_netw_client_cont_ip(self):
        """Yield deployer networks client container_ipaddr
        Returns:
            iter of str: Container IP address
        """

        for member in self.get_depl_netw_client_cont_ip():
            yield member

    def get_depl_netw_client_brg_ip(self, index=None):
        """Get deployer networks client bridge_ipaddr
        Args:
            index (int, optional): List index

        Returns:
            str: Bridge IP address
        """

        return self._get_members(
            self.cfg.deployer.networks.client,
            self.CfgKey.BRIDGE_IPADDR,
            index)

    def yield_depl_netw_client_brg_ip(self):
        """Yield deployer networks client bridge_ipaddr
        Returns:
            iter of str: Bridge IP address
        """

        for member in self.get_depl_netw_client_brg_ip():
            yield member

    def get_depl_netw_client_vlan(self, index=None, if_type=None):
        """Get deployer networks client vlan
        Args:
            index (int, optional): List index
            if_type (str, optional): Interface type ('ipmi', 'pxe', or 'data').
                                     If omitted all types are returned.

        Returns:
            int: VLAN
        """

        if if_type is None:
            network_list = self.cfg.deployer.networks.client

        else:
            network_list = []
            for network in self.cfg.deployer.networks.client:
                if if_type == network.type:
                    network_list.append(network)

        return self._get_members(network_list, self.CfgKey.VLAN, index)

    def yield_depl_netw_client_vlan(self, if_type=None):
        """Yield deployer networks client vlan
        Args:
            if_type (str, optional): Interface type ('ipmi', 'pxe', or 'data').
                                     If omitted all types are returned.

        Returns:
            iter of str: VLAN
        """

        for member in self.get_depl_netw_client_vlan(if_type=if_type):
            yield member

    def get_depl_netw_client_netmask(self, index=None):
        """Get deployer networks client netmask
        Returns:
            str or iter of str: Netmask
        """

        if index is None:
            list_ = []
            for member in self.cfg.deployer.networks.client:
                if self.CfgKey.NETMASK in member:
                    list_.append(member[self.CfgKey.NETMASK])
                elif self.CfgKey.PREFIX in member:
                    list_.append(self._prefix_to_netmask(
                        member[self.CfgKey.PREFIX]))
                else:
                    self._netmask_prefix_not_found()
            return list_
        else:
            member = self.cfg.deployer.networks.client[index]
            if self.CfgKey.NETMASK in member:
                return member[self.CfgKey.NETMASK]
            elif self.CfgKey.PREFIX in member:
                return self._prefix_to_netmask(member[self.CfgKey.PREFIX])
            else:
                self._netmask_prefix_not_found()

    def yield_depl_netw_client_netmask(self):
        """Yield deployer networks client netmask
        Returns:
            iter of str: Netmask
        """

        for member in self.get_depl_netw_client_netmask():
            yield member

    def get_depl_netw_client_prefix(self, index=None):
        """Get deployer networks client prefix
        Returns:
            str or iter of str: Prefix
        """

        if index is None:
            list_ = []
            for member in self.cfg.deployer.networks.client:
                if self.CfgKey.PREFIX in member:
                    list_.append(member[self.CfgKey.PREFIX])
                elif self.CfgKey.NETMASK in member:
                    list_.append(self._netmask_to_prefix(
                        member[self.CfgKey.NETMASK]))
                else:
                    self._netmask_prefix_not_found()
            return list_
        else:
            member = self.cfg.deployer.networks.client[index]
            if self.CfgKey.PREFIX in member:
                return member[self.CfgKey.PREFIX]
            elif self.CfgKey.NETMASK in member:
                return self._netmask_to_prefix(member[self.CfgKey.NETMASK])
            else:
                self._netmask_prefix_not_found()

    def yield_depl_netw_client_prefix(self):
        """Yield deployer networks client prefix
        Returns:
            iter of str: Prefix
        """

        for member in self.get_depl_netw_client_prefix():
            yield member

    def get_sw_mgmt_cnt(self):
        """Get switches mgmt count
        Returns:
            int: Management switch count
        """

        return len(self.cfg.switches.mgmt)

    def get_sw_mgmt_index_by_label(self, label):
        """Get switches mgmt index by label
        Returns:
            int: Label index
        """

        for index, mgmt in enumerate(self.cfg.switches.mgmt):
            if label == mgmt.label:
                return index

    def get_sw_mgmt_label(self, index=None):
        """Get switches mgmt label
        Args:
            index (int, optional): List index

        Returns:
            str or list of str: Label member or list
        """

        return self._get_members(
            self.cfg.switches.mgmt, self.CfgKey.LABEL, index)

    def yield_sw_mgmt_label(self):
        """Yield switches mgmt label
        Returns:
            iter of str: Label
        """

        for member in self.get_sw_mgmt_label():
            yield member

    def get_sw_mgmt_class(self, index=None):
        """Get switches mgmt class
        Args:
            index (int, optional): List index

        Returns:
            str or list of str: Class member or list
        """

        return self._get_members(
            self.cfg.switches.mgmt, self.CfgKey.CLASS, index)

    def yield_sw_mgmt_class(self):
        """Yield switches mgmt class
        Returns:
            iter of str: Class
        """

        for member in self.get_sw_mgmt_class():
            yield member

    def get_sw_mgmt_hostname(self, index=None):
        """Get switches mgmt hostname
        Args:
            index (int, optional): List index

        Returns:
            str or list of str: Hostname member or list
        """

        return self._get_members(
            self.cfg.switches.mgmt, self.CfgKey.HOSTNAME, index)

    def yield_sw_mgmt_hostname(self):
        """Yield switches mgmt hostname
        Returns:
            iter of str: Hostname
        """

        for member in self.get_sw_mgmt_hostname():
            yield member

    def get_sw_mgmt_userid(self, index=None):
        """Get switches mgmt userid
        Args:
            index (int, optional): List index

        Returns:
            str or list of str: Userid member or list
        """

        return self._get_members(
            self.cfg.switches.mgmt, self.CfgKey.USERID, index)

    def yield_sw_mgmt_userid(self):
        """Yield switches mgmt userid
        Returns:
            iter of str: Userid
        """

        for member in self.get_sw_mgmt_userid():
            yield member

    def get_sw_mgmt_password(self, index=None):
        """Get switches mgmt password
        Args:
            index (int, optional): List index

        Returns:
            str or list of str: Password member or list
        """

        return self._get_members(
            self.cfg.switches.mgmt, self.CfgKey.PASSWORD, index)

    def yield_sw_mgmt_password(self):
        """Yield switches mgmt password
        Returns:
            iter of str: Password
        """

        for member in self.get_sw_mgmt_password():
            yield member

    def get_sw_mgmt_ssh_key(self, index=None):
        """Get switches mgmt ssh_key
        Args:
            index (int, optional): List index

        Returns:
            str or list of str: SSH key member or list
        """

        return self._get_members(
            self.cfg.switches.mgmt, self.CfgKey.SSH_KEY, index)

    def yield_sw_mgmt_ssh_key(self):
        """Yield switches mgmt ssh_key
        Returns:
            iter of str: SSH key
        """

        for member in self.get_sw_mgmt_ssh_key():
            yield member

    def get_sw_mgmt_access_info(self, index=None, type_ifc='inband'):
        """Get Mgmt switches class, user_id, password and an ip address. An
        attempt is made to get the specified 'type' of address, but if that is
        not available, the other type will be returned.
        Args:
            index (int, optional): Switch index
            type_ifc (str, opt): 'inband' or 'outband'

        Returns:
            tuple or list of tuples of access info : label (str), class (str),
            userid (str), password (str), ip address.
        """
        if index > self.get_sw_mgmt_cnt() - 1:
            raise UserException('switch index out of range')
        if index is not None:
            switch_indices = [index]
        else:
            switch_indices = range(self.get_sw_mgmt_cnt())
        ai_list = []
        for sw_idx in switch_indices:
            ai_tuple = ()
            ai_tuple += (self.get_sw_mgmt_label(index=sw_idx),)
            ai_tuple += (self.get_sw_mgmt_class(index=sw_idx),)
            ipaddr = None
            for ifc in self.cfg.switches.mgmt[sw_idx].interfaces:
                if ifc.type == type_ifc:
                    ipaddr = ifc.ipaddr
                    break
                else:
                    if not ipaddr:
                        ipaddr = ifc.ipaddr
            ai_tuple += (ipaddr,)

            ai_tuple += (self.get_sw_mgmt_userid(index=sw_idx),)
            ai_tuple += (self.get_sw_mgmt_password(index=sw_idx),)

            ai_list.append(ai_tuple)
        # if index specified, make it a tuple
        if index:
            ai_list = ai_list[0]
        return ai_list

    def yield_sw_mgmt_access_info(self):
        """Yield dictionary of Mgmt switches class, user_id, password, and
        inband and outband ip address list(s).

        Returns:
            iter of list get_sw_mgmt_access_info()
        """
        for switch_ai in self.get_sw_mgmt_access_info():
            yield switch_ai

    def get_sw_mgmt_rack_id(self, index=None):
        """Get switches mgmt rack_id
        Args:
            index (int, optional): List index

        Returns:
            str or list of str: Rack ID member or list
        """

        return self._get_members(
            self.cfg.switches.mgmt, self.CfgKey.RACK_ID, index)

    def yield_sw_mgmt_rack_id(self):
        """Yield switches mgmt rack_id
        Returns:
            iter of str: Rack ID
        """

        for member in self.get_sw_mgmt_rack_id():
            yield member

    def get_sw_mgmt_rack_eia(self, index=None):
        """Get switches mgmt rack_eia
        Args:
            index (int, optional): List index

        Returns:
            str or list of str: Rack EIA member or list
        """

        return self._get_members(
            self.cfg.switches.mgmt, self.CfgKey.RACK_EIA, index)

    def yield_sw_mgmt_rack_eia(self):
        """Yield switches mgmt rack_eia
        Returns:
            iter of str: Rack EIA
        """

        for member in self.get_sw_mgmt_rack_eia():
            yield member

    def get_sw_mgmt_interfaces_cnt(self, switch_index):
        """Get switches mgmt interfaces ipaddr count
        Args:
            switch_index (int): Management switch index

        Returns:
            int: Management switch inband interface count
        """

        return len(self.cfg.switches.mgmt[switch_index].interfaces)

    def get_sw_mgmt_interfaces_ip(self, switch_index, index=None):
        """Get switches mgmt interfaces ipaddr
        Args:
            switch_index (int): Management switch index
            index (int, optional): List index

        Returns:
            str or list of str: IP address member or list
        """
        return self._get_members(
            self.cfg.switches.mgmt[switch_index].interfaces,
            self.CfgKey.IPADDR, index)

    def yield_sw_mgmt_interfaces_ip(self, switch_index):
        """Yield switches mgmt interfaces ipaddr
        Args:
            switch_index (int): Management switch index

        Returns:
            iter of str: IP address
        """

        try:
            for member in self.get_sw_mgmt_interfaces_ip(switch_index):
                yield member
        except AttributeError:
            return

    def get_sw_mgmt_interfaces_vlan(self, switch_index, index=None):
        """Get switches mgmt interfaces vlans
        Args:
            switch_index (int): Management switch index
            index (int, optional): List index

        Returns:
            int or list of int: Port member or list
        """
        return self._get_members(
            self.cfg.switches.mgmt[switch_index].interfaces,
            self.CfgKey.VLAN, index)

    def get_sw_mgmt_interfaces_netmask(self, switch_index, index=None):
        """Get switches mgmt interfaces netmask
        Args:
            switch_index (int): Management switch index
            index (int, optional): List index

        Returns:
            str or list of str: Port member or list
        """
        return self._get_members(
            self.cfg.switches.mgmt[switch_index].interfaces,
            self.CfgKey.NETMASK, index)

    def get_sw_mgmt_interfaces_port(self, switch_index, index=None):
        """Get switches mgmt interfaces port
        Args:
            switch_index (int): Management switch index
            index (int, optional): List index

        Returns:
            int or list of int: Port member or list
        """
        return self._get_members(
            self.cfg.switches.mgmt[switch_index].interfaces,
            self.CfgKey.PORT, index)

    def yield_sw_mgmt_interfaces_ports(self, switch_index):
        """Yield switches mgmt interfaces ports
        Args:
            switch_index (int): Management switch index

        Returns:
            iter of int: Port
        """

        for member in self.get_sw_mgmt_interfaces_ports(switch_index):
            yield member

    def get_sw_mgmt_links_ip(self, switch_index, index=None):
        """Get switches mgmt links ipaddr
        Args:
            switch_index (int): Management switch index
            index (int, optional): List index

        Returns:
            str or list of str: IP address member or list
        """
        return self._get_members(
            self.cfg.switches.mgmt[switch_index].links,
            self.CfgKey.IPADDR, index)

    def yield_sw_mgmt_links_ip(self, switch_index):
        """Yield switches mgmt links ipaddr
        Args:
            switch_index (int): Management switch index

        Returns:
            iter of str: IP address
        """

        try:
            for member in self.get_sw_mgmt_links_ip(switch_index):
                yield member
        except AttributeError:
            return

    def get_sw_mgmt_links_target(self, switch_index, index=None):
        """Get switches mgmt links target
        Args:
            switch_index (int): Management switch index
            index (int, optional): List index

        Returns:
            str or list of str: Link Target member or list
        """
        return self._get_members(
            self.cfg.switches.mgmt[switch_index].links,
            self.CfgKey.TARGET, index)

    def yield_sw_mgmt_links_target(self, switch_index):
        """Yield switches mgmt links targets
        Args:
            switch_index (int): Management switch index

        Returns:
            iter of str: targets
        """
        try:
            for member in self.get_sw_mgmt_links_target(switch_index):
                yield member
        except AttributeError:
            return

    def get_sw_mgmt_links_port(self, switch_index, index=None):
        """Get switches mgmt links port
        Args:
            switch_index (int): Management switch index
            index (int, optional): List index

        Returns:
            str or list of str: Port member or list
        """
        return self._get_members(
            self.cfg.switches.mgmt[switch_index].links,
            self.CfgKey.PORTS, index)

    def get_sw_mgmt_links_vlan(self, switch_index, index=None):
        """Get switches mgmt links vlan
        Args:
            switch_index (int): Management switch index
            index (int, optional): List index

        Returns:
            str or list of str: vlan member or list
        """
        return self._get_members(
            self.cfg.switches.mgmt[switch_index].links,
            self.CfgKey.VLAN, index)

    def get_sw_data_cnt(self):
        """Get switches data count
        Returns:
            int: Data switch count
        """

        return len(self.cfg.switches.data)

    def get_sw_data_index_by_label(self, label):
        """Get switches data index by label
        Returns:
            int: Label index
        """

        for index, data in enumerate(self.cfg.switches.data):
            if label == data.label:
                return index

    def get_sw_data_label(self, index=None):
        """Get switches data label
        Args:
            index (int, optional): List index

        Returns:
            str or list of str: Label member or list
        """

        return self._get_members(
            self.cfg.switches.data, self.CfgKey.LABEL, index)

    def yield_sw_data_label(self):
        """Yield switches data label
        Returns:
            iter of str: Label
        """

        for member in self.get_sw_data_label():
            yield member

    def get_sw_data_class(self, index=None):
        """Get switches data class
        Args:
            index (int, optional): List index

        Returns:
            str or list of str: Class member or list
        """

        return self._get_members(
            self.cfg.switches.data, self.CfgKey.CLASS, index)

    def yield_sw_data_class(self):
        """Yield switches data class
        Returns:
            iter of str: Class
        """

        for member in self.get_sw_data_class():
            yield member

    def get_sw_data_hostname(self, index=None):
        """Get switches data hostname
        Args:
            index (int, optional): List index

        Returns:
            str or list of str: Hostname member or list
        """

        return self._get_members(
            self.cfg.switches.data, self.CfgKey.HOSTNAME, index)

    def yield_sw_data_hostname(self):
        """Yield switches data hostname
        Returns:
            iter of str: Hostname
        """

        for member in self.get_sw_data_hostname():
            yield member

    def get_sw_data_userid(self, index=None):
        """Get switches data userid
        Args:
            index (int, optional): List index

        Returns:
            str or list of str: Userid member or list
        """

        return self._get_members(
            self.cfg.switches.data, self.CfgKey.USERID, index)

    def yield_sw_data_userid(self):
        """Yield switches data userid
        Returns:
            iter of str: Userid
        """

        for member in self.get_sw_data_userid():
            yield member

    def get_sw_data_password(self, index=None):
        """Get switches data password
        Args:
            index (int, optional): List index

        Returns:
            str or list of str: Password member or list
        """

        return self._get_members(
            self.cfg.switches.data, self.CfgKey.PASSWORD, index)

    def yield_sw_data_password(self):
        """Yield switches data password
        Returns:
            iter of str: Password
        """

        for member in self.get_sw_data_password():
            yield member

    def get_sw_data_ssh_key(self, index=None):
        """Get switches data ssh_key
        Args:
            index (int, optional): List index

        Returns:
            str or list of str: SSH key member or list
        """

        return self._get_members(
            self.cfg.switches.data, self.CfgKey.SSH_KEY, index)

    def yield_sw_data_ssh_key(self):
        """Yield switches data ssh_key
        Returns:
            iter of str: SSH key
        """

        for member in self.get_sw_data_ssh_key():
            yield member

    def get_sw_data_access_info(self, index=None, type_ifc='inband'):
        """Get Data switches class, user_id, password and an ip address. An
        attempt is made to get the specified 'type' of address, but if that is
        not available, the other type will be returned.
        Args:
            index (int, optional): Switch index
            type_ifc (str, opt): 'inband' or 'outband'

        Returns:
            tuple or list of tuples of access info : label (str), class (str),
            userid (str), password (str), ip address.
        """
        if index > self.get_sw_data_cnt() - 1:
            raise UserException('switch index out of range')
        if index is not None:
            switch_indeces = [index]
        else:
            switch_indeces = range(self.get_sw_data_cnt())
        ai_list = []
        for sw_idx in switch_indeces:
            ai_tuple = ()
            ai_tuple += (self.get_sw_data_label(index=sw_idx),)
            ai_tuple += (self.get_sw_data_class(index=sw_idx),)
            ipaddr = None
            for ifc in self.cfg.switches.data[sw_idx].interfaces:
                if ifc.type == type_ifc:
                    ipaddr = ifc.ipaddr
                    break
                else:
                    if not ipaddr:
                        ipaddr = ifc.ipaddr
            ai_tuple += (ipaddr,)

            ai_tuple += (self.get_sw_data_userid(index=sw_idx),)
            ai_tuple += (self.get_sw_data_password(index=sw_idx),)

            ai_list.append(ai_tuple)
        # if index specified, make it a tuple
        if index:
            ai_list = ai_list[0]
        return ai_list

    def yield_sw_data_access_info(self):
        """Yield dictionary of Data switches class, user_id, password, and
        inband and outband ip address list(s).

        Returns:
            iter of list get_sw_data_access_info()
        """
        for switch_ai in self.get_sw_data_access_info():
            yield switch_ai

    def get_sw_data_interfaces_ip(self, switch_index, index=None):
        """Get switches mgmt interfaces ipaddr
        Args:
            switch_index (int): Management switch index
            index (int, optional): List index

        Returns:
            str or list of str: IP address member or list
        """
        return self._get_members(
            self.cfg.switches.data[switch_index].interfaces,
            self.CfgKey.IPADDR, index)

    def yield_sw_data_interfaces_ip(self, switch_index):
        """Yield switches mgmt interfaces ipaddr
        Args:
            switch_index (int): Management switch index

        Returns:
            iter of str: IP address
        """

        try:
            for member in self.get_sw_data_interfaces_ip(switch_index):
                yield member
        except AttributeError:
            return

    def get_sw_data_mlag_peer(self, label):
        """ Returns the mlag peer switch if one exists, otherwise returns None.
        An mlag peer exists if the specified switch has a link to another
        'target' switch listed under the switches 'links' value, the target exists
        in the defined data switches and that link has a vlan defined in the
        switches 'links' value.
        Args:
            label (str):
        Returns:
            target_link (str): MLAG peer switch
        """
        switch_idx = self.get_sw_data_index_by_label(label)
        for link_idx, target_link in enumerate(
                self.yield_sw_data_links_target(switch_idx)):
            if link_idx is not None and self.get_sw_data_links_vlan(
                    switch_idx, link_idx) is not None:
                return target_link

    def get_sw_data_mstr_switch(self, switch_list):
        """ Return the switch label for the switch which will be used to assign port
        channels and mlag port channels for bonds. The switch with the highest address
        on an mlag link (ie a link with a vlan defined) will be used as the numeric
        source.  This insures port channel numbers are assigned without conflict.
        Args:
            switch_list (list of str): List of switches.
        Returns:
            switch (str) label of the switch which will be used as the source for
            channel numbering.  For each port channel, the smallest port number will
            used for the port channel number.
        """

        mstr_switch = None
        ip_max = 0
        for switch in self.yield_sw_data_label():
            if switch in switch_list:
                sw_idx = self.get_sw_data_index_by_label(switch)
                for link_idx, link_target in enumerate(
                        self.get_sw_data_links_target(sw_idx)):
                    if link_target in switch_list:
                        ipaddr = self.get_sw_data_links_ip(sw_idx, link_idx)
                        ip = netaddr.IPNetwork(ipaddr)
                        if ip.value > ip_max:
                            mstr_switch = switch
                            ip_max = ip.value
                    elif mstr_switch is None and switch is not None:
                        mstr_switch = switch

        return mstr_switch

    def get_sw_data_links_target(self, switch_index, index=None):
        """Get switches data links target
        Args:
            switch_index (int): Data switch index
            index (int, optional): List index

        Returns:
            str or list of str: Link Target member or list
        """

        return self._get_members(
            self.cfg.switches.data[switch_index].links,
            self.CfgKey.TARGET, index)

    def yield_sw_data_links_target(self, switch_index):
        """Yield switches data links targets
        Args:
            switch_index (int): Data switch index

        Returns:
            iter of str: targets
        """
        try:
            for member in self.get_sw_data_links_target(switch_index):
                yield member
        except (TypeError, AttributeError):
            return

    def get_sw_data_links_port(self, switch_index, index=None):
        """Get switches data links port
        Args:
            switch_index (int): Data switch index
            index (int, optional): List index

        Returns:
            str or list of str: Port member or list
        """
        return self._get_members(
            self.cfg.switches.data[switch_index].links,
            self.CfgKey.PORTS, index)

    def get_sw_data_links_ip(self, switch_index, index=None):
        """Get switches data links ip addr
        Args:
            switch_index (int): Data switch index
            index (int, optional): List index

        Returns:
            str : ipaddr member
        """
        return self._get_members(
            self.cfg.switches.data[switch_index].links,
            self.CfgKey.IPADDR, index)

    def get_sw_data_links_prefix(self, switch_index, index=None):
        """Get data switch links prefix
        Args:
            switch_index (int): Data switch index
            index (int, optional): List index

        Returns:
            str or iter of str: Netmask
        """

        if index is None:
            list_ = []
            for member in self.cfg.switches.data[switch_index].links:
                if self.CfgKey.PREFIX in member:
                    list_.append(member[self.CfgKey.PREFIX])
                elif self.CfgKey.NETMASK in member:
                    list_.append(self._netmask_to_prefix(
                        member[self.CfgKey.NETMASK]))
                else:
                    self._netmask_prefix_not_found()
            return list_
        else:
            member = self.cfg.switches.data[switch_index].links[index]
            if self.CfgKey.PREFIX in member:
                return member[self.CfgKey.PREFIX]
            elif self.CfgKey.NETMASK in member:
                return self._netmask_to_prefix(member[self.CfgKey.NETMASK])
            else:
                self._netmask_prefix_not_found()

    def yield_sw_data_links_prefix(self, switch_index):
        """Yield data switch prefixes
        Returns:
            iter of str: prefix
        """

        for member in self.get_sw_data_links_netmask(switch_index):
            yield member

    def get_sw_data_links_netmask(self, switch_index, index=None):
        """Get data switch links netmask
        Args:
            switch_index (int): Data switch index
            index (int, optional): List index

        Returns:
            str or iter of str: Netmask
        """

        if index is None:
            list_ = []
            for member in self.cfg.switches.data[switch_index].links:
                if self.CfgKey.NETMASK in member:
                    list_.append(member[self.CfgKey.NETMASK])
                elif self.CfgKey.PREFIX in member:
                    list_.append(self._prefix_to_netmask(
                        member[self.CfgKey.PREFIX]))
                else:
                    self._netmask_prefix_not_found()
            return list_
        else:
            member = self.cfg.switches.data[switch_index].links[index]
            if self.CfgKey.NETMASK in member:
                return member[self.CfgKey.NETMASK]
            elif self.CfgKey.PREFIX in member:
                return self._prefix_to_netmask(member[self.CfgKey.PREFIX])
            else:
                self._netmask_prefix_not_found()

    def yield_sw_data_links_netmask(self, switch_index):
        """Yield data switch netmasks
        Returns:
            iter of str: Netmask
        """

        for member in self.get_sw_data_links_netmask(switch_index):
            yield member

    def get_sw_data_links_vlan(self, switch_index, index=None):
        """Get switches data links vlan
        Args:
            switch_index (int): Data switch index
            index (int, optional): List index

        Returns:
            str or list of str: vlan member or list
        """
        return self._get_members(
            self.cfg.switches.data[switch_index].links,
            self.CfgKey.VLAN, index)

    def get_sw_data_links_vip(self, switch_index, index=None):
        """Get switches data links vip
        Args:
            switch_index (int): Data switch index
            index (int, optional): List index

        Returns:
            str or list of str: vip member or list
        """
        return self._get_members(
            self.cfg.switches.data[switch_index].links,
            self.CfgKey.VIP, index)

    def get_ntmpl_cnt(self):
        """Get node_templates count
        Returns:
            int: Node template count
        """

        return len(self.cfg.node_templates)

    def yield_ntmpl_ind(self):
        """Yield node_templates iindex
        Returns:
            int: Node template index
        """

        for index in range(0, self.get_ntmpl_cnt()):
            yield index

    def get_ntmpl_label(self, index=None):
        """Get node_templates label
        Args:
            index (int, optional): List index

        Returns:
            str or list of str: Type member or list
        """

        return self._get_members(
            self.cfg.node_templates, self.CfgKey.LABEL, index)

    def yield_ntmpl_label(self):
        """Yield node_templates label
        Returns:
            iter of str: Type
        """

        for member in self.get_ntmpl_label():
            yield member

    def get_ntmpl_ipmi_userid(self, index=None):
        """Get node_templates ipmi userid
        Args:
            index (int, optional): List index

        Returns:
            str or list of str: IPMI userid member or list
        """
        if index is None:
            list_ = []
            for member in self.cfg.node_templates:
                list_.append(member.ipmi.userid)
            return list_
        return self.cfg.node_templates[index].ipmi.userid

    def yield_ntmpl_ipmi_userid(self):
        """Yield node_templates ipmi userid
        Returns:
            iter of str: IPMI userid
        """

        for member in self.get_ntmpl_ipmi_userid():
            yield member

    def get_ntmpl_ipmi_password(self, index=None):
        """Get node_templates ipmi password
        Args:
            index (int, optional): List index

        Returns:
            str or list of str: IPMI password member or list
        """
        if index is None:
            list_ = []
            for member in self.cfg.node_templates:
                list_.append(member.ipmi.password)
            return list_
        return self.cfg.node_templates[index].ipmi.password

    def yield_ntmpl_ipmi_password(self):
        """Yield node_templates ipmi password
        Returns:
            iter of str: IPMI password
        """

        for member in self.get_ntmpl_ipmi_password():
            yield member

    def get_ntmpl_os_dict(self, index=None):
        """Get node_templates os dictionary
        Args:
            index (int, optional): List index

        Returns:
            AttrDict or list of AttrDict: Node template OS dictionary
        """
        if index is None:
            list_ = []
            for member in self.cfg.node_templates:
                list_.append(member.os)
            return list_
        else:
            return self.cfg.node_templates[index].os

    def yield_ntmpl_os_dict(self):
        """Yield node_templates os dictionary
        Returns:
            iter of AttrDict: Node template OS dictionary
        """

        for member in self.get_ntmpl_os_dict():
            yield member

    def get_ntmpl_os_hostname_prefix(self, index=None):
        """Get node_templates os hostname_prefix
        Args:
            index (int, optional): List index

        Returns:
            str or list of str: Hostname prefix member or list
        """
        if index is None:
            list_ = []
            for member in self.cfg.node_templates:
                if self.CfgKey.HOSTNAME_PREFIX in member.os.iterkeys():
                    list_.append(member.os.hostname_prefix)
                else:
                    list_.append(None)
            return list_
        if (self.CfgKey.HOSTNAME_PREFIX in
                self.cfg.node_templates[index].os.iterkeys()):
            return self.cfg.node_templates[index].os.hostname_prefix

    def yield_ntmpl_os_hostname_prefix(self):
        """Yield node_templates os hostname_prefix
        Returns:
            iter of str: Hostname prefix
        """

        for member in self.get_ntmpl_os_hostname_prefix():
            yield member

    def get_ntmpl_os_profile(self, index=None):
        """Get node_templates os profile
        Args:
            index (int, optional): List index

        Returns:
            str or list of str: OS profile member or list
        """
        if index is None:
            list_ = []
            for member in self.cfg.node_templates:
                list_.append(member.os.profile)
            return list_
        return self.cfg.node_templates[index].os.profile

    def yield_ntmpl_os_profile(self):
        """Yield node_templates os profile
        Returns:
            iter of str: OS profile
        """

        for member in self.get_ntmpl_os_profile():
            yield member

    def get_ntmpl_roles_cnt(self, node_template_index):
        """Get node_templates roles count
        Args:
            node_template_index (int): Node template index

        Returns:
            int: Role count
        """

        try:
            return len(self.cfg.node_templates[node_template_index].roles)
        except AttributeError:
            return 0

    def get_ntmpl_roles(self, node_template_index, index=None):
        """Get node_templates roles
        Args:
            node_template_index (int): Node template index
            index (int, optional): List index

        Returns:
            str or list of str: Role member or list
        """

        if index is None:
            try:
                return self.cfg.node_templates[node_template_index].roles
            except AttributeError:
                return None
        try:
            return self.cfg.node_templates[node_template_index].roles[index]
        except AttributeError:
            return ''

    def yield_ntmpl_roles(self, node_template_index):
        """Yield node_templates roles
        Args:
            node_template_index (int): Node template index

        Returns:
            iter of str: Role
        """

        for member in self.get_ntmpl_roles(node_template_index):
            yield member

    def get_ntmpl_interfaces(self, node_template_index):
        """Get node_templates interfaces
        Args:
            node_template_index (int): Node template index

        Returns:
            list of str: List of interface dictionaries

        Raises:
            UserException: If referenced interface is not defined
        """

        node_template = self.cfg.node_templates[node_template_index]
        interface_defs = self.get_interfaces()
        network_defs = self.get_networks()
        if_labels = []

        for interface in self.yield_ntmpl_phyintf_pxe_interface(
                node_template_index):
            if_labels.append(interface)

        for interface in self.yield_ntmpl_phyintf_data_interface(
                node_template_index):
            if_labels.append(interface)

        if (self.CfgKey.INTERFACES in node_template and
                node_template[self.CfgKey.INTERFACES] is not None):
            for interface in node_template[self.CfgKey.INTERFACES]:
                if interface not in if_labels:
                    if_labels.append(interface)

        if (self.CfgKey.NETWORKS in node_template and
                node_template[self.CfgKey.NETWORKS] is not None):
            for network in node_template[self.CfgKey.NETWORKS]:
                for network_def in network_defs:
                    if network == network_def[self.CfgKey.LABEL]:
                        for interface in network_def[self.CfgKey.INTERFACES]:
                            if interface not in if_labels:
                                if_labels.append(interface)

        interfaces = [None] * len(if_labels)
        for interface in interface_defs:
            if interface[self.CfgKey.LABEL] in if_labels:
                index = if_labels.index(interface[self.CfgKey.LABEL])
                _interface = interface.copy()
                replace_keys = [self.CfgKey.ADDRESS_LIST,
                                self.CfgKey.ADDRESS_START,
                                self.CfgKey.IPADDR_LIST,
                                self.CfgKey.IPADDR_START]
                for key in replace_keys:
                    if key in _interface.keys():
                        del _interface[key]
                        new_key = key.split('_')[0]
                        _interface[new_key] = None
                interfaces[index] = _interface

        for index, interface in enumerate(interfaces):
            if interface is None:
                raise UserException('No interface defined with label=%s' %
                                    if_labels[index])

        return interfaces

    def get_ntmpl_netw_cnt(self, node_template_index):
        """Get node_templates networks count
        Args:
            node_template_index (int): Node template index

        Returns:
            int: Network count
        """

        return len(self.cfg.node_templates[node_template_index].networks)

    def get_ntmpl_netw(self, node_template_index, index=None):
        """Get node_templates networks
        Args:
            node_template_index (int): Node template index
            index (int, optional): List index

        Returns:
            str or list of str: Network member or list
        """

        if 'networks' not in self.cfg.node_templates[node_template_index]:
            return None

        if index is None:
            netw = self.cfg.node_templates[node_template_index].networks
            netw = netw if netw is None else netw[:]
            return netw
        return self.cfg.node_templates[node_template_index].networks[index]

    def yield_ntmpl_netw(self, node_template_index):
        """Yield node_templates networks
        Args:
            node_template_index (int): Node template index

        Returns:
            iter of str: Network
        """

        for member in self.get_ntmpl_netw(node_template_index):
            yield member

    def get_ntmpl_ifcs_all(self, node_template_index):
        """Get node_templates interfaces including those in networks
        Args:
            node_template_index (int): Node template index

        Returns:
            list of str: interfaces list
        """

        networks = self.get_networks()
        if networks is None:
            return []
        ntmpl_networks = self.get_ntmpl_netw(node_template_index)
        ntmpl_ifcs = self.get_ntmpl_intf(node_template_index)
        ntmpl_ifcs = [] if ntmpl_ifcs is None else ntmpl_ifcs
        for netw in networks:
            if ntmpl_networks is not None and netw['label'] in ntmpl_networks:
                ntmpl_ifcs += netw['interfaces']
        return ntmpl_ifcs

    def get_ntmpl_intf_cnt(self, node_template_index):
        """Get node_templates interfaces count
        Args:
            node_template_index (int): Node template index

        Returns:
            int: Interface count
        """

        return len(self.cfg.node_templates[node_template_index].interfaces)

    def get_ntmpl_intf(self, node_template_index, index=None):
        """Get node_templates interfaces
        Args:
            node_template_index (int): Node template index
            index (int, optional): List index

        Returns:
            str or list of str: Interface member or list
        """

        if 'interfaces' not in self.cfg.node_templates[node_template_index]:
            return None

        if index is None:
            intf = self.cfg.node_templates[node_template_index].interfaces
            intf = intf if intf is None else intf[:]
            return intf
        return self.cfg.node_templates[node_template_index].interfaces[index]

    def yield_ntmpl_intf(self, node_template_index):
        """Yield node_templates interfaces
        Args:
            node_template_index (int): Node template index

        Returns:
            iter of str: Interface
        """

        for member in self.get_ntmpl_intf(node_template_index):
            yield member

    def get_ntmpl_phyintf_ipmi_cnt(self, node_template_index):
        """Get node_templates physical_interfaces ipmi count
        Args:
            node_template_index (int): Node template index

        Returns:
            int: IPMI count
        """

        node_template = self.cfg.node_templates[node_template_index]
        return len(node_template.physical_interfaces.ipmi)

    def yield_ntmpl_phyintf_ipmi_ind(self, node_template_index):
        """Yield node_templates physical_interfaces ipmi index
        Args:
            node_template_index (int): Node template index

        Returns:
            int: IPMI index
        """

        for index in range(0, self.get_ntmpl_phyintf_ipmi_cnt(
                node_template_index)):
            yield index

    def get_ntmpl_phyintf_ipmi_switch(
            self, node_template_index, index=None):
        """Get node_templates physical_interfaces ipmi switch
        Args:
            node_template_index (int): Node template index
            index (int, optional): List index

        Returns:
            str or list of str: IPMI switch member or list
        """

        node_template = self.cfg.node_templates[node_template_index]
        return self._get_members(
            node_template.physical_interfaces.ipmi, self.CfgKey.SWITCH, index)

    def yield_ntmpl_phyintf_ipmi_switch(self, node_template_index):
        """Yield node_templates physical_interfaces ipmi switch
        Args:
            node_template_index (int): Node template index

        Returns:
            iter of str: IPMI switch
        """

        for member in self.get_ntmpl_phyintf_ipmi_switch(node_template_index):
            yield member

    def get_ntmpl_phyintf_ipmi_pt_cnt(self, node_template_index, ipmi_index):
        """Get node template physical interface IPMI ports count
        Args:
            node_template_index (int): Node template index
            ipmi_index (int): IPMI index

        Returns:
            int: IPMI ports count
        """

        node_template = self.cfg.node_templates[node_template_index]
        return len(node_template.physical_interfaces.ipmi[ipmi_index].ports)

    def yield_ntmpl_phyintf_ipmi_pt_ind(
            self, node_template_index, ipmi_index):
        """Yield node template physical interface IPMI ports index
        Returns:
            int: IPMI ports index
        """

        for index in range(0, self.get_ntmpl_phyintf_ipmi_pt_cnt(
                node_template_index, ipmi_index)):
            yield index

    def get_ntmpl_phyintf_ipmi_ports(
            self, node_template_index, ipmi_index, index=None):
        """Get node_templates physical_interfaces ipmi ports
        Args:
            node_template_index (int): Node template index
            ipmi_index (int): IPMI index
            index (int, optional): List index

        Returns:
            int or list of int: IPMI ports member or list
        """

        node_template = self.cfg.node_templates[node_template_index]
        if index is None:
            return node_template.physical_interfaces.ipmi[ipmi_index].ports
        return node_template.physical_interfaces.ipmi[ipmi_index].ports[index]

    def yield_ntmpl_phyintf_ipmi_ports(self, node_template_index, ipmi_index):
        """Yield node_templates physical_interfaces ipmi ports
        Args:
            node_template_index (int): Node template index
            ipmi_index (int): IPMI index

        Returns:
            iter of int: IPMI ports
        """

        for member in self.get_ntmpl_phyintf_ipmi_ports(
                node_template_index, ipmi_index):
            yield member

    def get_ntmpl_phyintf_pxe_cnt(self, node_template_index):
        """
        Args:
            node_template_index (int): Node template index

        Returns:
            int: PXE count
        """

        node_template = self.cfg.node_templates[node_template_index]
        return len(node_template.physical_interfaces.pxe)

    def yield_ntmpl_phyintf_pxe_ind(self, node_template_index):
        """Yield node_templates physical_interfaces pxe index
        Args:
            node_template_index (int): Node template index

        Returns:
            int: PXE index
        """

        for index in range(0, self.get_ntmpl_phyintf_pxe_cnt(
                node_template_index)):
            yield index

    def get_ntmpl_phyintf_pxe_switch(
            self, node_template_index, index=None):
        """Get node_templates physical_interfaces pxe switch
        Args:
            node_template_index (int): Node template index
            index (int, optional): List index

        Returns:
            str or list of str: PXE switch member or list
        """

        node_template = self.cfg.node_templates[node_template_index]
        return self._get_members(
            node_template.physical_interfaces.pxe, self.CfgKey.SWITCH, index)

    def yield_ntmpl_phyintf_pxe_switch(self, node_template_index):
        """Yield node_templates physical_interfaces pxe switch
        Args:
            node_template_index (int): Node template index

        Returns:
            iter of str: PXE switch
        """

        for member in self.get_ntmpl_phyintf_pxe_switch(node_template_index):
            yield member

    def get_ntmpl_phyintf_pxe_rename(
            self, node_template_index, index=0):
        """Get node_templates physical_interfaces pxe rename boolean
        Args:
            node_template_index (int): Node template index
            index (int, optional): List index (defaults to 0)

        Returns:
            bool: if True device will be renamed
        """

        node_template = self.cfg.node_templates[node_template_index]
        if self.CfgKey.RENAME in node_template.physical_interfaces.pxe[index]:
            return node_template.physical_interfaces.pxe[index].rename
        else:
            return True

    def get_ntmpl_phyintf_pxe_pt_cnt(self, node_template_index, pxe_index):
        """
        Args:
            node_template_index (int): Node template index
            pxe_index (int): PXE index

        Returns:
            int: PXE ports count
        """

        node_template = self.cfg.node_templates[node_template_index]
        return len(node_template.physical_interfaces.pxe[pxe_index].ports)

    def yield_ntmpl_phyintf_pxe_pt_ind(self, node_template_index, pxe_index):
        """Yield node template physical interface PXE ports count
        Returns:
            int: PXE ports index
        """

        for index in range(0, self.get_ntmpl_phyintf_pxe_pt_cnt(
                node_template_index, pxe_index)):
            yield index

    def get_ntmpl_phyintf_pxe_ports(
            self, node_template_index, pxe_index, index=None):
        """Get node_templates physical_interfaces pxe ports
        Args:
            node_template_index (int): Node template index
            pxe_index (int): PXE index
            index (int, optional): List index

        Returns:
            int or list of int: PXE ports member or list
        """

        node_template = self.cfg.node_templates[node_template_index]
        if index is None:
            return node_template.physical_interfaces.pxe[pxe_index].ports
        return node_template.physical_interfaces.pxe[pxe_index].ports[index]

    def yield_ntmpl_phyintf_pxe_ports(self, node_template_index, pxe_index):
        """Yield node_templates physical_interfaces pxe ports
        Args:
            node_template_index (int): Node template index
            pxe_index (int): PXE index

        Returns:
            iter of int: PXE ports
        """

        for member in self.get_ntmpl_phyintf_pxe_ports(
                node_template_index, pxe_index):
            yield member

    def get_ntmpl_phyintf_pxe_interface(
            self, node_template_index, index=None):
        """Get node_templates physical_interfaces PXE interface
        Args:
            node_template_index (int): Node template index
            index (int, optional): List index

        Returns:
            str or list of str: PXE interface member or list
        """

        node_template = self.cfg.node_templates[node_template_index]
        return self._get_members(
            node_template.physical_interfaces.pxe, self.CfgKey.INTERFACE, index)

    def yield_ntmpl_phyintf_pxe_interface(self, node_template_index):
        """Yield node_templates physical_interfaces PXE interface
        Args:
            node_template_index (int): Node template index

        Returns:
            iter of str: PXE interface
        """

        for member in self.get_ntmpl_phyintf_pxe_interface(node_template_index):
            yield member

    def get_ntmpl_phyintf_data_interface(
            self, node_template_index, index=None):
        """Get node_templates physical_interfaces data interface
        Args:
            node_template_index (int): Node template index
            index (int, optional): List index

        Returns:
            str or list of str: Data interface member or list
        """

        node_template = self.cfg.node_templates[node_template_index]
        try:
            return self._get_members(
                node_template.physical_interfaces.data, self.CfgKey.INTERFACE,
                index)
        except AttributeError:
            return []

    def yield_ntmpl_phyintf_data_interface(self, node_template_index):
        """Yield node_templates physical_interfaces data interface
        Args:
            node_template_index (int): Node template index

        Returns:
            iter of str: Data interface
        """

        for member in self.get_ntmpl_phyintf_data_interface(
                node_template_index):
            yield member

    def get_ntmpl_phyintf_data_cnt(self, node_template_index):
        """
        Args:
            node_template_index (int): Node template index

        Returns:
            int: count of data physical interfaces
        """

        node_template = self.cfg.node_templates[node_template_index]
        try:
            return len(node_template.physical_interfaces.data)
        except AttributeError:
            return 0

    def yield_ntmpl_phyintf_data_ind(self, node_template_index):
        """Yield node_templates physical_interfaces data index
        Args:
            node_template_index (int): Node template index

        Returns:
            int: data physical interfaces index
        """

        for index in range(0, self.get_ntmpl_phyintf_data_cnt(
                node_template_index)):
            yield index

    def get_ntmpl_phyintf_data_switch(
            self, node_template_index, index=None):
        """Get node_templates physical_interfaces data switch label(s)
        Args:
            node_template_index (int): Node template index
            index (int, optional): Interface index

        Returns:
            str or list of str: Data switch member or list
        """

        node_template = self.cfg.node_templates[node_template_index]
        return self._get_members(
            node_template.physical_interfaces.data, self.CfgKey.SWITCH, index)

    def yield_ntmpl_phyintf_data_switch(self, node_template_index):
        """Yield node_templates physical_interfaces data switch label
        Args:
            node_template_index (int): Node template index

        Returns:
            iter of str: Data switch labels
        """

        for member in self.get_ntmpl_phyintf_data_switch(node_template_index):
            yield member

    def get_ntmpl_phyintf_data_ifc(
            self, node_template_index, index=None):
        """Get node_templates physical_interfaces data interface label
        Args:
            node_template_index (int): Node template index
            index (int, optional): Data interface index

        Returns:
            str or list of str: data interface member or list
        """

        node_template = self.cfg.node_templates[node_template_index]
        return self._get_members(
            node_template.physical_interfaces.data, self.CfgKey.INTERFACE, index)

    def yield_ntmpl_phyintf_data_ifc(self, node_template_index):
        """Yield node_templates physical_interfaces pxe dev
        Args:
            node_template_index (int): Node template index

        Returns:
            iter of str: data interface
        """

        for member in self.get_ntmpl_phyintf_data_ifc(node_template_index):
            yield member

    def get_ntmpl_phyintf_data_dev(
            self, node_template_index, index):
        """Get node_templates physical_interfaces data dev
        Args:
            node_template_index (int): Node template index
            index (int): List index

        Returns:
            str: Data interface device (iface) value
        """

        node_template = self.cfg.node_templates[node_template_index]
        if_label = node_template.physical_interfaces.data[index].interface
        return self.lookup_interface_iface(if_label)

    def get_ntmpl_phyintf_pxe_dev(
            self, node_template_index, index=0):
        """Get node_templates physical_interfaces PXE dev
        Args:
            node_template_index (int): Node template index
            index (int, optional): List index (defaults to 0)

        Returns:
            str: PXE interface device (iface) value
        """

        node_template = self.cfg.node_templates[node_template_index]
        if_label = node_template.physical_interfaces.pxe[index].interface
        return self.lookup_interface_iface(if_label)

    def lookup_interface_iface(self, if_label):
        """Get interface template data device
        Args:
            if_lable (str): Interface label

        Returns:
            str: Interface iface value

        Raises:
            UserException: If referenced interface is not defined or
                           has no 'iface' key
        """

        for interface in self.cfg.interfaces:
            if interface.label == if_label:
                if self.CfgKey.IFACE in interface:
                    return interface[self.CfgKey.IFACE]
                elif self.CfgKey.INTERFACE_DEVICE in interface:
                    return interface[self.CfgKey.INTERFACE_DEVICE]
                else:
                    raise UserException(
                        'No \'iface\' or \'DEVICE\' key defined in interface '
                        'with label=%s' % interface.label)
        else:
            raise UserException('No interface defined with label=%s' % if_label)

    def yield_ntmpl_phyintf_data_dev(self, node_template_index):
        """Yield node_templates physical_interfaces data dev
        Args:
            node_template_index (int): Node template index

        Returns:
            iter of str: Data dev
        """

        for member in self.get_ntmpl_phyintf_data_dev(node_template_index):
            yield member

    def get_ntmpl(self, node_template_index):
        """Get node_template
        Args:
            node_template_index (int): Node template index
            index (int, optional): Interface index

        Returns:
            dict : Node template dict
        """

        node_template = self.cfg.node_templates[node_template_index]
        return node_template

    def get_ntmpl_phyintf_data(self, node_template_index):
        """Get node templates  'physical_interfaces' dictionary

        Returns:
            dict: Physical Interface definitions
        """

        return self.cfg.node_templates[node_template_index].physical_interfaces.data

    def get_ntmpl_phyintf_data_rename(
            self, node_template_index, index):
        """Get node_templates physical_interfaces data rename boolean
        Args:
            node_template_index (int): Node template index
            index (int): List index

        Returns:
            bool: if True device will be renamed
        """

        node_template = self.cfg.node_templates[node_template_index]
        if self.CfgKey.RENAME in node_template.physical_interfaces.data[index]:
            return node_template.physical_interfaces.data[index].rename
        else:
            return False

    def get_ntmpl_phyintf_data_pt_cnt(self, node_template_index, data_index):
        """
        Args:
            node_template_index (int): Node template index
            data_index (int): Data index

        Returns:
            int: Data ports count
        """

        node_template = self.cfg.node_templates[node_template_index]
        return len(node_template.physical_interfaces.data[data_index].ports)

    def yield_ntmpl_phyintf_data_pt_ind(self, node_template_index, data_index):
        """Yield node template physical interface Data ports count
        Returns:
            int: Data ports index
        """

        for index in range(0, self.get_ntmpl_phyintf_data_pt_cnt(
                node_template_index, data_index)):
            yield index

    def get_ntmpl_phyintf_data_ports(
            self, node_template_index, data_index, index=None):
        """Get node_templates physical_interfaces data ports
        Args:
            node_template_index (int): Node template index
            data_index (int): Data index
            index (int, optional): List index

        Returns:
            int or list of int: Data ports member or list
        """

        node_template = self.cfg.node_templates[node_template_index]
        if index is None:
            return node_template.physical_interfaces.data[data_index].ports[:]
        return node_template.physical_interfaces.data[data_index].ports[index]

    def yield_ntmpl_phyintf_data_ports(self, node_template_index, data_index):
        """Yield node_templates physical_interfaces data ports
        Args:
            node_template_index (int): Node template index
            data_index (int): Data index

        Returns:
            iter of int: Data ports
        """

        for member in self.get_ntmpl_phyintf_data_ports(
                node_template_index, data_index):
            yield member

    def get_client_switch_ports(self, switch_label, if_type=None):
        """Get physical interface ports associated with switch_label
        Args:
            switch_label (str): Switch Label
            if_type (str, optional): Interface type ('ipmi', 'pxe', or 'data').
                                     If omitted all types are returned.

        Returns:
            list of str: Ports
        """

        port_list = []

        for template in self.cfg.node_templates:
            for temp_if_type, items in template.physical_interfaces.items():
                if if_type is None or if_type == temp_if_type:
                    for item in items:
                        if item.switch == switch_label:
                            for port in item.ports:
                                port_list.append(port)
        return port_list

    def yield_client_switch_ports(self, switch_label, if_type=None):
        """Yield physical interface ports associated with switch_label
        Args:
            switch_label (str): Switch Label
            if_type (str, optional): Interface type ('ipmi', 'pxe', or 'data').
                                     If omitted all types are returned.

        Returns:
            iter of str: Ports
        """

        for member in self.get_client_switch_ports(switch_label, if_type):
            yield member

    def get_interfaces(self):
        """Get top level 'interfaces' dictionary

        Returns:
            dict: Interface definitions
        """

        return self.cfg.interfaces

    def get_interface(self, label):
        """Get 'interfaces' dictionary by label

        Returns:
            dict: Interface definition or empty dict
        """

        for ifc in self.get_interfaces():
            if ifc['label'] == label:
                return ifc
        return {}

    def get_networks(self):
        """Get top level 'networks' dictionary

        Returns:
            dict: Network definitions
        """

        if self.CfgKey.NETWORKS in self.cfg:
            return self.cfg.networks
        else:
            return []

    def get_software_bootstrap(self):
        """Get top level 'software_bootstrap' dictionary

        Returns:
            list: Software bootstrap list
        """

        if self.CfgKey.SOFTWARE_BOOTSTRAP in self.cfg:
            return self.cfg[self.CfgKey.SOFTWARE_BOOTSTRAP]
        else:
            return []
