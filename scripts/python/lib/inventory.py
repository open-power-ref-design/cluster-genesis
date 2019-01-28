"""Inventory"""

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

from enum import Enum
from orderedattrdict import AttrDict, DefaultAttrDict

import lib.logger as logger
from lib.exception import UserException
from lib.db import DatabaseInventory


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(
                Singleton, cls).__call__(*args, **kwargs)
        else:
            cls._instances[cls].__init__(*args, **kwargs)
        return cls._instances[cls]


# Python 3
# class Inventory(metaclass=Singleton):
class Inventory(object):
    __metaclass__ = Singleton
    """Inventory

    Args:
        log (object): Log
        inv_file (string): Inventory file
    """

    class SwitchType(Enum):
        MGMT, DATA = range(2)

    class InvKey(object):
        NODES = 'nodes'
        LABEL = 'label'
        HOSTNAME = 'hostname'
        USERID = 'userid'
        PASSWORD = 'password'
        SSH_KEY = 'ssh_key'
        ROOM = 'room'
        ROW = 'row'
        CELL = 'cell'
        IPADDRS = 'ipaddrs'
        MACS = 'macs'
        IPMI = 'ipmi'
        PXE = 'pxe'
        DATA = 'data'
        SWITCHES = 'switches'
        SWITCHES_IPMI = 'switches_ipmi'
        SWITCHES_PXE = 'switches_pxe'
        PORTS = 'ports'
        PORTS_IPMI = 'ports_ipmi'
        PORTS_PXE = 'ports_pxe'
        RACK_ID = 'rack_id'
        USERID = 'userid'
        PASSWORD = 'password'
        DEVICES = 'devices'
        DEVICES_PXE = 'devices_pxe'
        OS = 'os'
        PROFILE = 'profile'
        INSTALL_DEVICE = 'install_device'
        DOMAIN = 'domain'
        USERS = 'users'
        KERNEL_OPTIONS = 'kernel_options'
        ROLES = 'roles'
        RENAME = 'rename'
        INTERFACES = 'interfaces'
        IFACE = 'iface'
        DEVICE = 'DEVICE'
        BMC_TYPE = 'bmc_type'

    def __init__(self, cfg_file=None, inv_file=None):
        self.log = logger.getlogger()
        self.dbase = DatabaseInventory(inv_file=inv_file, cfg_file=cfg_file)

        self.inv = AttrDict()
        inv = self.dbase.load_inventory()
        if inv is not None:
            self.inv = inv

        self.switch = None
        self.switch_type = None

        if self.InvKey.NODES not in self.inv:
            self.inv.nodes = []

        # Order is only kept in Python 3.6 and above
        # self.nodes = AttrDict({
        #     self.InvKey.LABEL: 'a',
        #     self.InvKey.HOSTNAME: 'b',
        #     self.InvKey.PORT: 'c'})

        self.nodes = AttrDict()
        self.nodes[self.InvKey.LABEL] = []
        self.nodes[self.InvKey.HOSTNAME] = []
        self.nodes[self.InvKey.RACK_ID] = []
        self.nodes[self.InvKey.BMC_TYPE] = []
        self.nodes[self.InvKey.IPMI] = AttrDict()
        self.nodes[self.InvKey.PXE] = AttrDict()
        self.nodes[self.InvKey.DATA] = AttrDict()
        self.nodes[self.InvKey.OS] = []
        self.nodes[self.InvKey.ROLES] = []
        self.nodes[self.InvKey.INTERFACES] = []

        self.nodes[self.InvKey.IPMI][self.InvKey.SWITCHES] = []
        self.nodes[self.InvKey.IPMI][self.InvKey.PORTS] = []
        self.nodes[self.InvKey.IPMI][self.InvKey.MACS] = []
        self.nodes[self.InvKey.IPMI][self.InvKey.IPADDRS] = []
        self.nodes[self.InvKey.IPMI][self.InvKey.USERID] = []
        self.nodes[self.InvKey.IPMI][self.InvKey.PASSWORD] = []
        self.nodes[self.InvKey.PXE][self.InvKey.PORTS] = []
        self.nodes[self.InvKey.PXE][self.InvKey.MACS] = []
        self.nodes[self.InvKey.PXE][self.InvKey.IPADDRS] = []
        self.nodes[self.InvKey.PXE][self.InvKey.DEVICES] = []
        self.nodes[self.InvKey.PXE][self.InvKey.SWITCHES] = []
        self.nodes[self.InvKey.PXE][self.InvKey.RENAME] = []
        self.nodes[self.InvKey.DATA][self.InvKey.SWITCHES] = []
        self.nodes[self.InvKey.DATA][self.InvKey.PORTS] = []
        self.nodes[self.InvKey.DATA][self.InvKey.MACS] = []
        self.nodes[self.InvKey.DATA][self.InvKey.IPADDRS] = []
        self.nodes[self.InvKey.DATA][self.InvKey.DEVICES] = []
        self.nodes[self.InvKey.DATA][self.InvKey.RENAME] = []

    def add_nodes_hostname(self, hostname):
        self.nodes.hostname.append(hostname)

    def add_nodes_label(self, label):
        self.nodes.label.append(label)

    def add_nodes_os_dict(self, os_dict):
        self.nodes.os.append(os_dict)

    def add_nodes_rack_id(self, rack_id):
        self.nodes.rack_id.append(rack_id)

####
    def add_nodes_bmc_type(self, bmc_type):
        self.nodes.bmc_type.append(bmc_type)

    def add_nodes_switches_ipmi(self, switches):
        self.nodes.ipmi.switches.append(switches)

    def add_nodes_switches_pxe(self, switches):
        self.nodes.pxe.switches.append(switches)

    def add_nodes_switches_data(self, switches):
        self.nodes.data.switches.append(switches)

    def add_nodes_ports_ipmi(self, ports):
        self.nodes.ipmi.ports.append(ports)

    def add_nodes_ports_pxe(self, ports):
        self.nodes.pxe.ports.append(ports)

    def add_nodes_ports_data(self, ports):
        self.nodes.data.ports.append(ports)

    def add_nodes_macs_ipmi(self, macs):
        self.nodes.ipmi.macs.append(macs)

    def add_nodes_macs_pxe(self, macs):
        self.nodes.pxe.macs.append(macs)

    def add_nodes_macs_data(self, macs):
        self.nodes.data.macs.append(macs)

    def add_nodes_ipaddrs_ipmi(self, ipaddrs):
        self.nodes.ipmi.ipaddrs.append(ipaddrs)

    def add_nodes_ipaddrs_pxe(self, ipaddrs):
        self.nodes.pxe.ipaddrs.append(ipaddrs)

    def add_nodes_userid_ipmi(self, userid):
        self.nodes.ipmi.userid.append(userid)

    def add_nodes_password_ipmi(self, password):
        self.nodes.ipmi.password.append(password)

    def add_nodes_devices_pxe(self, dev):
        self.nodes.pxe.devices.append(dev)

    def add_nodes_devices_data(self, dev):
        self.nodes.data.devices.append(dev)

    def add_nodes_roles(self, roles):
        self.nodes.roles.append(roles)

    def add_nodes_rename_data(self, renames):
        self.nodes.data.rename.append(renames)

    def add_nodes_rename_pxe(self, renames):
        self.nodes.pxe.rename.append(renames)

    def add_nodes_interfaces(self, interfaces):
        self.nodes.interfaces.append(interfaces)

    def _flatten(self, data):
        def items():
            for key, value in iter(data.items()):
                if isinstance(value, dict):
                    for subkey, subvalue in iter(self._flatten(value).items()):
                        yield key + '.' + subkey, subvalue
                else:
                    yield key, value
        return AttrDict(items())

    def update_nodes(self):
        nodes = []
        flat = self._flatten(self.nodes)

        for item_key, item_values in iter(flat.items()):
            for index, item_value in enumerate(item_values):
                if len(nodes) <= index:
                    nodes.append(DefaultAttrDict(dict))
                if '.' in item_key:
                    keys = item_key.split('.')
                    nodes[index][keys[0]][keys[1]] = item_value
                else:
                    nodes[index][item_key] = item_value

        self.inv.nodes = nodes
        self.dbase.dump_inventory(self.inv)

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

    def get_nodes_label(self, index=None):
        """Get nodes label
        Args:
            index (int, optional): List index

        Returns:
            str: nodes label
        """

        return self._get_members(self.inv.nodes, self.InvKey.LABEL, index)

    def get_nodes_hostname(self, index=None):
        """Get nodes hostname
        Args:
            index (int, optional): List index

        Returns:
            str: nodes hostname
        """

        return self._get_members(self.inv.nodes, self.InvKey.HOSTNAME, index)

    def get_nodes_bmc_type(self, index=None):
        """Get nodes bmc type
        Args:
            index (int, optional): List index

        Returns:
            str: nodes hostname
        """

        return self._get_members(self.inv.nodes, self.InvKey.BMC_TYPE, index)

    def yield_nodes_hostname(self):
        """Yield nodes hostnames
        Returns:
            iter of str: Nodes hostnames
        """

        for member in self.get_nodes_hostname():
            yield member

    def get_port_mac_ip(self, switch, port):
        """Get the mac address and ip address for the specified port on the
        specified switch.  Otherwise return None, None
        Args:
            switch (str): Switch label
            port (str or int): Port name
        Returns:
            str: port mac address
            str: port ipv4 address
        """
        mac, ipaddr = None, None
        for node in self.inv.nodes:
            if port in node.ipmi.ports:
                idx = node.ipmi.ports.index(port)
                if switch == node.ipmi.switches[idx]:
                    try:
                        mac = node.ipmi.macs[idx]
                    except (AttributeError, IndexError):
                        mac = None
                    try:
                        ipaddr = node.ipmi.ipaddrs[idx]
                    except (AttributeError, IndexError):
                        ipaddr = None
                    return mac, ipaddr
            if port in node.pxe.ports:
                idx = node.pxe.ports.index(port)
                if switch == node.pxe.switches[idx]:
                    try:
                        mac = node.pxe.macs[idx]
                    except (AttributeError, IndexError):
                        mac = None
                    try:
                        ipaddr = node.pxe.ipaddrs[idx]
                    except (AttributeError, IndexError):
                        ipaddr = None
                    return mac, ipaddr
        return mac, ipaddr

    def get_nodes_ipmi_userid(self, index=None):
        """Get nodes BMC userid
        Args:
            index (int, optional): List index

        Returns:
            str: nodes IPMI userid
        """

        return self._get_members(
            self.inv.nodes, self.InvKey.IPMI, index)[self.InvKey.USERID]

    def get_nodes_ipmi_password(self, index=None):
        """Get nodes BMC password
        Args:
            index (int, optional): List index

        Returns:
            str: nodes IPMI password
        """

        return self._get_members(
            self.inv.nodes, self.InvKey.IPMI, index)[self.InvKey.PASSWORD]

    def get_nodes_ipmi_ipaddr(self, if_index, index=None):
        """Get nodes IPMI interface ipaddr
        Args:
            if_index (int): Interface index
            index (int, optional): List index

        Returns:
            str: nodes IPMI ipaddr
        """

        ipmi_addr_list = self._get_members(
            self.inv.nodes, self.InvKey.IPMI, index)
        if index is not None:
            return ipmi_addr_list[self.InvKey.IPADDRS][if_index]
        else:
            return [ipmi_addr_list[x][self.InvKey.IPADDRS][0]
                    for x in range(len(ipmi_addr_list))]

    def set_nodes_ipmi_ipaddr(self, if_index, index, ipaddr):
        """Set nodes IPMI interface ipaddr
        Args:
            if_index (int): Interface index
            index (int): List index
        """

        self.inv.nodes[index].ipmi.ipaddrs[if_index] = ipaddr
        self.dbase.dump_inventory(self.inv)

    def get_nodes_ipmi_mac(self, if_index, index=None):
        """Get nodes IPMI interface MAC address
        Args:
            if_index (int): Interface index
            index (int, optional): List index

        Returns:
            str: nodes IPMI MAC
        """

        return self._get_members(
            self.inv.nodes, self.InvKey.IPMI,
            index)[self.InvKey.MACS][if_index]

    def get_nodes_pxe_ipaddr(self, if_index, index=None):
        """Get nodes PXE interface ipaddr
        Args:
            if_index (int): Interface index
            index (int, optional): List index

        Returns:
            str: nodes PXE ipaddr
        """
        pxe_addr_list = self._get_members(
            self.inv.nodes, self.InvKey.PXE, index)
        if index is not None:
            return pxe_addr_list[self.InvKey.IPADDRS][if_index]
        else:
            return [pxe_addr_list[x][self.InvKey.IPADDRS][0]
                    for x in range(len(pxe_addr_list))]

    def yield_nodes_pxe_ipaddr(self):
        """Yield nodes PXE ipaddrs
        Returns:
            iter of str: Nodes ipaddrs
        """

        for node in self.inv.nodes:
            for ipaddr in node.pxe.ipaddrs:
                yield ipaddr

    def set_nodes_pxe_ipaddr(self, if_index, index, ipaddr):
        """Set nodes PXE interface ipaddr
        Args:
            if_index (int): Interface index
            index (int): List index
        """

        self.inv.nodes[index].pxe.ipaddrs[if_index] = ipaddr
        self.dbase.dump_inventory(self.inv)

    def get_nodes_pxe_mac(self, if_index, index=None):
        """Get nodes PXE interface MAC address
        Args:
            if_index (int): Interface index
            index (int, optional): List index

        Returns:
            str: nodes PXE MAC
        """

        return self._get_members(
            self.inv.nodes, self.InvKey.PXE,
            index)[self.InvKey.MACS][if_index]

    def _check_all_nodes_mac_ipaddr(self, interface_type, key):
        """Check if PXE/IPMI key is populated across all nodes
        Args:
            interface_type (str): Interface type ("ipmi" or "pxe")
            key (str): Dictionary key ("macs", "ipaddrs", etc.)

        Returns:
            bool: True if all nodes have value populated for key
        """

        # If no nodes defined return False
        if (self.InvKey.NODES not in self.inv or
                len(self.inv[self.InvKey.NODES]) < 1):
            return False

        # If any value is None immediately return False
        for node in self.inv[self.InvKey.NODES]:
            for item in node[interface_type][key]:
                if item is None:
                    return False
        else:
            return True

    def check_all_nodes_ipmi_ipaddrs(self):
        """Check if all nodes have populated IPMI interface ipaddr

        Returns:
            bool: True if all nodes have all IPMI ipaddrs items populated
        """

        return self._check_all_nodes_mac_ipaddr(self.InvKey.IPMI,
                                                self.InvKey.IPADDRS)

    def check_all_nodes_ipmi_macs(self):
        """Check if all nodes have populated IPMI interface mac

        Returns:
            bool: True if all nodes have all IPMI macs items populated
        """

        return self._check_all_nodes_mac_ipaddr(self.InvKey.IPMI,
                                                self.InvKey.MACS)

    def check_all_nodes_pxe_ipaddrs(self):
        """Check if all nodes have populated PXE interface ipaddr

        Returns:
            bool: True if all nodes have all PXE ipaddrs items populated
        """

        return self._check_all_nodes_mac_ipaddr(self.InvKey.PXE,
                                                self.InvKey.IPADDRS)

    def check_all_nodes_pxe_macs(self):
        """Check if all nodes have populated PXE interface mac

        Returns:
            bool: True if all nodes have all PXE macs items populated
        """

        return self._check_all_nodes_mac_ipaddr(self.InvKey.PXE,
                                                self.InvKey.MACS)

    def get_nodes_os_profile(self, index=None):
        """Get nodes OS profile
        Args:
            index (int, optional): List index

        Returns:
            str: nodes OS profile
        """

        return self._get_members(
            self.inv.nodes, self.InvKey.OS, index)[self.InvKey.PROFILE]

    def get_nodes_os_install_device(self, index=None):
        """Get nodes OS install device
        Args:
            index (int, optional): List index

        Returns:
            str: nodes OS install device
        """

        try:
            return self._get_members(
                self.inv.nodes,
                self.InvKey.OS,
                index)[self.InvKey.INSTALL_DEVICE]
        except KeyError:
            pass

    def get_nodes_os_domain(self, index=None):
        """Get nodes OS domain
        Args:
            index (int, optional): List index

        Returns:
            str: nodes OS domain
        """

        try:
            return self._get_members(
                self.inv.nodes,
                self.InvKey.OS,
                index)[self.InvKey.DOMAIN]
        except KeyError:
            pass

    def get_nodes_os_users(self, index=None):
        """Get nodes OS users
        Args:
            index (int, optional): List index

        Returns:
            list: OS user definition dicts
        """

        try:
            return self._get_members(
                self.inv.nodes,
                self.InvKey.OS,
                index)[self.InvKey.USERS]
        except KeyError:
            pass

    def get_nodes_os_kernel_options(self, index=None):
        """Get nodes OS kernel options
        Args:
            index (int, optional): List index

        Returns:
            str: nodes OS kernel options
        """

        try:
            return self._get_members(
                self.inv.nodes,
                self.InvKey.OS,
                index)[self.InvKey.KERNEL_OPTIONS]
        except KeyError:
            pass

    def get_nodes_rack_id(self, index=None):
        """Get nodes rack_id
        Args:
            index (int, optional): List index

        Returns:
            str: nodes label
        """

        return self._get_members(self.inv.nodes, self.InvKey.RACK_ID, index)

    def _add_macs(self, macs, type_):
        for node in self.inv.nodes:
            for index, _port in enumerate(node[type_][self.InvKey.PORTS]):
                port = str(_port)
                switch = node[type_][self.InvKey.SWITCHES][index]

                # If switch is not found
                if switch not in macs:
                    msg = "Switch '{}' not found".format(switch)
                    self.log.error(msg)
                    raise UserException(msg)
                # If port is not found
                if port not in macs[switch]:
                    msg = "Switch '{}' port '{}' not found".format(
                        switch, port)
                    self.log.debug(msg)
                    continue
                # If port has no MAC
                if not macs[switch][port]:
                    msg = "Switch '{}' port '{}' no MAC".format(
                        switch, port)
                    self.log.debug(msg)
                    continue
                # If port has more than one MAC
                if len(macs[switch][port]) > 1:
                    msg = "Switch '{}' port '{}' too many MACs '{}'".format(
                        switch, port, macs[switch][port])
                    self.log.error(msg)
                    raise UserException(msg)

                if macs[switch][port][0] not in node[type_][self.InvKey.MACS]:
                    node[type_][self.InvKey.MACS][index] = \
                        macs[switch][port][0]

    def add_macs_ipmi(self, macs):
        """Add MAC addresses
        Args:
            macs (dict of dict of list of str): Switch{Port}{[MAC]}
        """

        self._add_macs(macs, self.InvKey.IPMI)
        self.dbase.dump_inventory(self.inv)

    def add_macs_pxe(self, macs):
        """Add MAC addresses
        Args:
            macs (dict of dict of list of str): Switch{Port}{[MAC]}
        """

        self._add_macs(macs, self.InvKey.PXE)
        self.dbase.dump_inventory(self.inv)

    def add_macs_data(self, macs):
        """Add MAC addresses
        Args:
            macs (dict of dict of list of str): Switch{Port}{[MAC]}
        """

        self._add_macs(macs, self.InvKey.DATA)
        self.dbase.dump_inventory(self.inv)

    def get_data_interfaces(self):
        """Get data interface information

        Returns:
            dict of list of 5-tuples: {node1: [(switch, port, device,
                                                mac), ...],
                                       node2: [(...)], ...}
        """
        mac_dict = {}
        for node in self.inv.nodes:
            device_list = []
            for index, device in enumerate(
                    node[self.InvKey.DATA][self.InvKey.DEVICES]):
                switch = node[self.InvKey.DATA][self.InvKey.SWITCHES][index]
                port = node[self.InvKey.DATA][self.InvKey.PORTS][index]
                mac = node[self.InvKey.DATA][self.InvKey.MACS][index]
                device_list.append((switch, port, device, mac))
            mac_dict[node[self.InvKey.HOSTNAME]] = device_list

        return mac_dict

    def check_data_interfaces_macs(self):
        """Check if MAC addresses are populated for all data interfaces

        Returns:
            bool: True if all MACs are populated
        """
        for node in self.inv.nodes:
            for mac in node[self.InvKey.DATA][self.InvKey.MACS]:
                if mac is None:
                    return False

        return True

    def _add_ipaddrs(self, ipaddrs, type_):
        for node in self.inv.nodes:
            for index, mac in enumerate(node[type_][self.InvKey.MACS]):
                # If MAC is not found
                if mac not in ipaddrs:
                    continue

                if ipaddrs[mac] not in node[type_][self.InvKey.IPADDRS]:
                    node[type_][self.InvKey.IPADDRS][index] = ipaddrs[mac]

    def add_ipaddrs_ipmi(self, ipaddrs):
        """Add IPMI IP addresses
        Args:
            ipaddrs (dict of str): MAC{IP}
        """
        self._add_ipaddrs(ipaddrs, self.InvKey.IPMI)
        self.dbase.dump_inventory(self.inv)

    def add_ipaddrs_pxe(self, ipaddrs):
        """Add PXE IP addresses
        Args:
            ipaddrs (dict of str): MAC{IP}
        """
        self._add_ipaddrs(ipaddrs, self.InvKey.PXE)
        self.dbase.dump_inventory(self.inv)

    def get_node_dict(self, index):
        """Get node dictionary
        Args:
            index (int): List index

        Returns:
            dict: Node dictionary
        """

        return self.inv.nodes[index]

    def get_nodes_roles(self, index=None):
        """Get nodes hostname
        Args:
            index (int, optional): List index

        Returns:
            list: Roles list
        """

        return self._get_members(self.inv.nodes, self.InvKey.ROLES, index)

    def set_interface_name(self, set_mac, set_name):
        """Set physical interface name

        Args:
            macs (str): Interface MAC address
            name (str): Device name
        """
        old_name = ''

        for index, node in enumerate(self.inv.nodes):
            for if_index, mac in enumerate(node.pxe.macs):
                if set_mac == mac:
                    old_name = node.pxe.devices[if_index]
                    self.log.debug("Renaming node \'%s\' PXE physical "
                                   "interface \'%s\' to \'%s\' (MAC:%s)" %
                                   (node.hostname, old_name, set_name, mac))
                    node.pxe.devices[if_index] = set_name
                    break
            else:
                for if_index, mac in enumerate(node.data.macs):
                    if set_mac == mac:
                        old_name = node.data.devices[if_index]
                        self.log.debug("Renaming node \'%s\' data physical "
                                       "interface \'%s\' to \'%s\' (MAC:%s)" %
                                       (node.hostname, old_name, set_name, mac))
                        node.data.devices[if_index] = set_name
                        break
            if old_name != '':
                node_index = index
                break
        else:
            raise UserException("No physical interface found in inventory with "
                                "MAC: %s" % set_mac)

        for interface in self.inv.nodes[node_index][self.InvKey.INTERFACES]:
            for key, value in iter(interface.items()):
                if isinstance(value, str):
                    value_split = []
                    for _value in value.split():
                        if old_name == _value or old_name in _value.split('.'):
                            _value = _value.replace(old_name, set_name)
                        value_split.append(_value)
                    new_value = " ".join(value_split)
                    self.log.debug("Renaming node \'%s\' interface key \'%s\' "
                                   "from \'%s\' to \'%s\'" %
                                   (self.inv.nodes[node_index].hostname, key,
                                    value, new_value))
                    interface[key] = new_value
        self.dbase.dump_inventory(self.inv)
