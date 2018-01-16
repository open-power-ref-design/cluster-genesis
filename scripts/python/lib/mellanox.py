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

import re
import os.path
import netaddr
import datetime

import lib.logger as logger
from lib.switch_common import SwitchCommon
from lib.genesis import GEN_PASSIVE_PATH, GEN_PATH
from lib.switch_exception import SwitchException


class Mellanox(SwitchCommon):
    """Class for configuring and retrieving information for a Mellanox
    switch. Similar Mellanox switches may work or may need some methods
    overridden. This class can be instantiated in 'active' mode, in which
    case the switch will be configured or in 'passive' mode in which case the
    commands needed to configure the switch are written to a file.
    When in passive mode, information requests will return 'None'.
    In passive mode, a filename can be generated which
    will contain the active mode switch commands used for switch
    configuration. This outfile will be written to the
    'cluster-genesis/passive' directory if it exists or to the
    'cluster-genesies' directory if the passive directory does not
    exist. If no outfile name is provided a default name is used.
    In active mode, the 'host, userid and password named variables
    are required. If 'mode' is not provided, it is defaulted to 'passive'.

    Args:
        host (string): Management switch management interface IP address
        or hostname or if in passive mode, a fully qualified filename of the
        acquired mac address table for the switch.
        userid (string): Switch management interface login user ID.
        password (string): Switch management interface login password.
        mode (string): Set to 'passive' to run in passive switch mode.
            Defaults to 'active'
        outfile (string): Name of file to direct switch output to when
        in passive mode.
        access_list (list of str): optional list containing host, userid
        and password.
    """
    ENABLE_REMOTE_CONFIG = 'cli enable "configure terminal" "%s"'
    FORCE = 'force'
    SET_MTU = 'mtu {}'
    INTERFACE_CONFIG = 'interface ethernet 1/{} '
    SHOW_SWITCHPORT = 'show interfaces switchport | include Eth1/{}'
    SET_NATIVE_VLAN_ACCESS = 'interface ethernet 1/{} switchport access vlan {}'
    SET_NATIVE_VLAN_TRUNK = 'interface ethernet 1/{} switchport access vlan {}'
    SHOW_PORT = 'show interfaces switchport'
    SET_SWITCHPORT_MODE_TRUNK = ('interface ethernet 1/{} switchport mode hybrid')
    SET_SWITCHPORT_MODE_ACCESS = ('interface ethernet 1/{} switchport mode access')
    SWITCHPORT_HYBRID_ALLOWED_VLAN = \
        'switchport hybrid allowed-vlan add %d'
    ADD_VLANS_TO_PORT = \
        'switchport hybrid allowed-vlan add {}'
    REMOVE_VLANS_FROM_PORT = \
        'switchport hybrid allowed-vlan remove {}'
    SHUTDOWN = 'shutdown'
    NO_SHUTDOWN = 'no shutdown'
    IP_ROUTING = 'ip routing'
    ENABLE_LACP = 'lacp'
    QOS_ENABLE = 'dcb priority-flow-control enable force'
    MLAG = 'protocol mlag'
    LAG_PORT_CHANNEL = 'interface port-channel {} '
    LAG_ACTIVE = 'channel-group {} mode active'
    IPL = 'ipl 1'
    QOS_ON = 'dcb priority-flow-control mode on force'
    QOS_OFF = 'no dcb priority-flow-control mode force'
    INTERFACE_VLAN = 'interface vlan {}'
    IP_CIDR = 'ip address {}'
    PEER_ADDR = 'peer-address {}'
    MLAG_VIP = 'mlag-vip mlag-vip-domain ip %s force'
    NO_MLAG_VIP = 'no mlag-vip'
    ENABLE_MLAG = 'no mlag shutdown'
    DISABLE_MLAG = 'mlag shutdown'
    MLAG_PORT_CHANNEL = 'interface mlag-port-channel {} '
    SHOW_IFC_LAG_PORT_CHANNEL = 'show interface port-channel summary'
    SHOW_IFC_MLAG_PORT_CHANNEL = 'show interface mlag-port-channel summary'
    STP_PORT_TYPE_EDGE = 'spanning-tree port type edge'
    STP_BPDUFILTER_ENABLE = 'spanning-tree bpdufilter enable'
    MLAG_ACTIVE = 'mlag-channel-group {} mode active'
    NO_CHANNEL_GROUP = 'no channel-group'
    NO_MLAG_CHANNEL_GROUP = 'no mlag-channel-group'
    MAC_RE = re.compile('([\da-fA-F]{2}:){5}([\da-fA-F]{2})')
    CLEAR_MAC_ADDRESS_TABLE = 'clear mac-address-table dynamic'
    SHOW_INTERFACE = 'show interface vlan {}'
    SET_INTERFACE = 'interface vlan {} ip address {} {}'

    def __init__(self, host=None, userid=None, password=None, mode=None,
                 outfile=None):
        self.log = logger.getlogger()
        self.mode = mode
        self.host = host
        if self.mode == 'active':
            self.userid = userid
            self.password = password
        elif self.mode == 'passive':
            if os.path.isdir(GEN_PASSIVE_PATH):
                self.outfile = GEN_PASSIVE_PATH + '/' + outfile
            else:
                self.outfile = GEN_PATH + '/' + outfile
            f = open(self.outfile, 'a+')
            f.write(str(datetime.datetime.now()) + '\n')
            f.close()
        super(Mellanox, self).__init__(host, userid, password, mode, outfile)

    def set_switchport_mode(self, mode, port, nvlan=None):
        """Sets the switchport mode.  Note that Mellanox's 'hybrid'
        mode is functionally equivalent to most other vendor's 'trunk'
        mode. To handle this, if mode is specified as 'trunk', it is
        set to 'hybrid'. Mellanox's trunk mode can be set by setting
        mode to 'trunk-native'.
        """
        if mode == 'trunk':
            self.send_cmd(self.SET_SWITCHPORT_MODE_TRUNK.format(port))
            if nvlan is not None:
                self.send_cmd(self.SET_NATIVE_VLAN_TRUNK.format(port, nvlan))
        if mode == 'access':
            self.send_cmd(self.SET_SWITCHPORT_MODE_ACCESS.format(port))
            if nvlan is not None:
                self.send_cmd(self.SET_NATIVE_VLAN_ACCESS.format(port, nvlan))
        if mode == 'trunk-native':
            self.send_cmd('interface ethernet 1/{} switchport mode trunk'.format(port))
        if self.mode == 'passive':
            return
        ports = self.show_ports('std')
        port = str(port)
        if ports[port]['mode'] == 'hybrid' and mode == 'trunk':
            self.log.info(
                'Set port {} to {} mode'.format(port, mode))
        elif ports[port]['mode'] == 'access' and mode == 'access':
            self.log.info(
                'Set port {} to {} mode'.format(port, mode))
        elif mode == 'trunk':
            self.log.info(
                'Set port {} to {} mode'.format(port, mode))
        else:
            raise SwitchException(
                'Failed setting port {} to {} mode'.format(port, mode))

    def show_ports(self, format=None):
        if self.mode == 'passive':
            return None
        ports = {}
        port_info = self.send_cmd(self.SHOW_PORT)
        if format is None:
            return port_info
        elif format == 'std':
            port_info = port_info.splitlines()
            for line in port_info:
                match = re.search(r'Eth1/(\d+)\s+(access|hybrid|trunk)\s+(\d+)\s+(.+)', line)
                if match:
                    ports[match.group(1)] = {
                        'mode': match.group(2),
                        'nvlan': match.group(3),
                        'avlans': match.group(4)}
            return ports

    def show_interfaces(self, vlan='', host=None, netmask=None, format=None):
        """Gets from the switch a list of programmed in-band interfaces. The
        standard format consists of a list of lists. Each list entry contains
        the vlan number, the ip address, netmask and the number of the interface.
        which do not number the in-band interfaces, the last item in each list
        is set to '-'. When vlan, host and netmask are specified, the last list
        item contains 'True' or 'False' indicating whether an interface already
        exists with the specified vlan, host and netmask. For switches which do
        number the interfaces, (ie Lenovo) the last list item also contains the
        next available interface number and the number of the found interface.
        Args:
            vlan (string): String representation of integer between
                1 and 4094. If none specified, usually the default vlan is used.
            host (string): hostname or ipv4 address in dot decimal notation
            netmask (string): netmask in dot decimal notation
            format (string): 'std' If format is not specified, The native (raw)
                format is returned. If format is set to 'std', a 'standard' format
                is returned.
        Returns:
        If format is unspecified, returns a raw string of data as it
        comes from the switch. If format == 'std' a standard format is returned.
        Standard format consists of a list of lists. Each list entry contains
        the vlan number, the ip address, netmask and the number of the interface.
        For switches which do not number the in-band interfaces, the last item
        in each list is set to '-'. When vlan, host and netmask are specified,
        the last list item contains a dictionary. The dictionary has three entries;
            'configured' : set to True or False indicating whether an
                interface already exists with the specified vlan, host and netmask.
            'avail ifc' : For switches which do number the interfaces, (ie Lenovo)
                this dictioanary entry contains the next available interface number.
            'found ifc' : For switches which do number the interfaces, this entry
                contains the number of the found interface.
        """
        if self.mode == 'passive':
            return None
        ifcs = []
        vlan = str(vlan)
        found, found_vlan = False, False
        ifc_info = self.send_cmd(self.SHOW_INTERFACE.format(''))
        if format is None:
            return ifc_info
        ifc_info = ifc_info.rsplit('Vlan')
        for line in ifc_info:
            match = re.search(r'\s+(\d+).*Internet Address:\s+'
                              '((\w+.\w+.\w+.\w+)/\d+)', line, re.DOTALL)
            if match:
                mask = netaddr.IPNetwork(match.group(2))
                mask = str(mask.netmask)
                ifcs.append(
                    [match.group(1), match.group(3), mask, '-'])
                if (vlan, host, netmask, '-') == tuple(ifcs[-1]):
                    found = True
                if vlan in ifcs[-1]:
                    found_vlan = True
        ifcs.append([{'configured': found, 'found vlan': found_vlan}])
        return ifcs

    def remove_interface(self, vlan, host='', netmask=''):
        """Removes an in-band management interface.
        Args:
            host (string): hostname or ipv4 address in dot decimal notation
            netmask (string): netmask in dot decimal notation
            vlan (int or string): value between 1 and 4094.
        raises:
            SwitchException if unable to remove interface
        """
        vlan = str(vlan)
        interfaces = self.show_interfaces(vlan, host, netmask, format='std')
        if interfaces[-1][0]['configured']:
            self.send_cmd('no interface vlan {}'.format(vlan))
            interfaces = self.show_interfaces(vlan, host, netmask, format='std')
            if interfaces[-1][0]['configured']:
                self.log.info('Failed to remove interface Vlan {}.'.format(vlan))
                raise SwitchException('Failed to remove interface Vlan {}.'.format(vlan))
        else:
            if interfaces[-1][0]['found vlan']:
                self.log.info('Specified interface on vlan {} does not exist.'.format(vlan))
                raise SwitchException('Failed to remove interface Vlan {}.'.format(vlan))

    def configure_interface(self, host, netmask, vlan):
        """Configures a management interface. Minimally, this method will
        configure (overwrite if necessary) the specified interface.
        A better behaved implementation will check if host ip is already in
        use. If it is, it checks to see if it is configured as specified. If
        not, an exception is raised. If no interface number is specified,
        it will use the next available unconfigured interface. The specified
        vlan will be created if it does not already exist.

        Args:
            host (string): hostname or ipv4 address in dot decimal notation
            netmask (string): netmask in dot decimal notation
            vlan (int or string): Integer between 1 and 4094.
            If none specified, usually the default vlan is used.
        raises:
            SwitchException if unable to program interface
        """
        vlan = str(vlan)
        interfaces = self.show_interfaces(vlan, host, netmask, format='std')
        if interfaces[-1][0]['configured']:
            self.log.info(
                'Switch interface vlan {} already configured'.format(vlan))
            return
        if interfaces[-1][0]['found vlan']:
            self.log.info(
                'Conflicting address. Interface vlan {} already configured'.format(vlan))
            raise SwitchException(
                'Conflicting address exists on interface vlan {}'.format(vlan))
            return
        # create vlan if it does not already exist
        self.create_vlan(vlan)

        # create the interface
        self.send_cmd(self.SET_INTERFACE.format(vlan, host, netmask))
        interfaces = self.show_interfaces(vlan, host, netmask, format='std')
        if not interfaces[-1][0]['configured']:
            raise SwitchException(
                'Failed configuring management interface vlan {}'.format(vlan))

    def is_port_in_trunk_mode(self, port):
        """Allows determination if a port is in 'trunk' mode. Note that
        mellanox's hybrid mode is equivalent to most vendor's trunk mode.
        """
        if self.mode == 'passive':
            return None
        port = str(port)
        ports = self.show_ports('std')
        return 'hybrid' in ports[port]['mode']

    def remove_channel_group(self, port):
        # Remove channel-group from interface
        self.send_cmd(
            self.INTERFACE_CONFIG.format(port) +
            ' ' +
            self.NO_CHANNEL_GROUP)

    def remove_mlag_channel_group(self, port):
        # Remove channel-group from interface
        self.send_cmd(
            self.INTERFACE_CONFIG.format(port) +
            ' ' +
            self.NO_MLAG_CHANNEL_GROUP)

    def add_vlans_to_lag_port_channel(self, port, vlans):
        # Enable hybrid mode for port
        self.send_cmd(
            self.LAG_PORT_CHANNEL.format(port) +
            self.SWITCHPORT_MODE_HYBRID)

        # Add VLANs to port
        for vlan in vlans:
            self.send_cmd(
                self.LAG_PORT_CHANNEL.format(port) +
                self.SWITCHPORT_HYBRID_ALLOWED_VLAN % vlan)

    def add_vlans_to_mlag_port_channel(self, port, vlans):
        # Enable hybrid mode for port
        self.send_cmd(
            self.MLAG_PORT_CHANNEL.format(port) +
            self.SWITCHPORT_MODE_HYBRID)

        # Add VLANs to port
        for vlan in vlans:
            self.send_cmd(
                self.MLAG_PORT_CHANNEL.format(port) +
                ' ' +
                self.SWITCHPORT_HYBRID_ALLOWED_VLAN % vlan)

    def set_mtu_for_port(self, port, mtu):
        # Bring port down
        self.send_cmd(
            self.INTERFACE_CONFIG.format(port) + self.SHUTDOWN)

        # Set MTU
        if mtu == 0:
            self.send_cmd(
                self.INTERFACE_CONFIG.format(port) + 'no mtu')
        else:
            self.send_cmd(
                self.INTERFACE_CONFIG.format(port) + self.SET_MTU.format(mtu))

        # Bring port up
        self.send_cmd(
            self.INTERFACE_CONFIG.format(port) + self.NO_SHUTDOWN)

    def set_mtu_for_lag_port_channel(self, port, mtu):
        # Set port-channel MTU
        if mtu == 0:
            self.send_cmd(
                self.LAG_PORT_CHANNEL.format(port) +
                'no mtu ' +
                self.FORCE)
        else:
            self.send_cmd(
                self.LAG_PORT_CHANNEL.format(port) +
                self.SET_MTU.format(mtu) +
                ' ' +
                self.FORCE)

    def set_mtu_for_mlag_port_channel(self, port, mtu):
        # Set port-channel MTU
        if mtu == 0:
            self.send_cmd(
                self.MLAG_PORT_CHANNEL.format(port) +
                'no mtu ' +
                self.FORCE)
        else:
            self.send_cmd(
                self.MLAG_PORT_CHANNEL.format(port) +
                self.SET_MTU.format(mtu) +
                ' ' +
                self.FORCE)

    def create_lag_interface(self, lag_ifc):
        # Create a LAG
        self.send_cmd(
            self.LAG_PORT_CHANNEL.format(lag_ifc))

    def remove_lag_interface(self, lag_ifc):
        # Remove LAG interface
        self.send_cmd(
            'no ' + self.LAG_PORT_CHANNEL.format(lag_ifc))

    def bind_ports_to_lag_interface(self, ports, lag_ifc):
        # Map a physical port to the LAG in active mode (LACP)
        for port in ports:
            self.send_cmd(
                self.INTERFACE_CONFIG.format(port) +
                ' ' +
                self.LAG_ACTIVE.format(lag_ifc))

    def enable_lacp(self):
        self.send_cmd(self.ENABLE_LACP)

    def enable_mlag(self):
        self.send_cmd(self.ENABLE_MLAG)

    def disable_mlag(self):
        self.send_cmd(self.DISABLE_MLAG)

    def show_lag_interfaces(self):
        return self.send_cmd(self.SHOW_IFC_LAG_PORT_CHANNEL)

    def deconfigure_mlag(self):
        # Get MLAG info.  Note that Mellanox supports only 1 IPL port channel
        mlag_info = self.send_cmd('show mlag')
        match = re.search(r'\d+\s+Po(\d+)\s+(\d+)', mlag_info)
        if match:
            port_channel = match.group(1)
            vlan = match.group(2)
            self.log.info(
                'Found IPL port channel {} on vlan {}. Removing.'
                .format(port_channel, vlan))
        else:
            raise SwitchException(
                'MLAG port channel information not found')

        port_channel_info = self.send_cmd(self.SHOW_IFC_LAG_PORT_CHANNEL)
        match = re.search(
            r'\d+\s+Po' +
            port_channel +
            '\S+\s+\w+\s+Eth1/(\d+)\S+\s+Eth1/(\d+)', port_channel_info)
        if match:
            port1 = match.group(1)
            port2 = match.group(2)
            self.log.info('Found IPL ports {} {}'.format(port1, port2))
        else:
            raise SwitchException(
                'MLAG IPL port channel information not found')

        self.disable_mlag()
        self.send_cmd(self.NO_MLAG_VIP)

        # Remove IPL peer address
        self.send_cmd(
            self.INTERFACE_VLAN.format(vlan) +
            ' no ' +
            self.IPL +
            ' ' +
            self.PEER_ADDR.format(''))

        # Remove IPL address
        self.send_cmd(
            self.INTERFACE_VLAN.format(vlan) +
            ' no ' +
            self.IP_CIDR.format(''))

        # Remove the interface on vlan
        self.send_cmd('no ' + self.INTERFACE_VLAN.format(vlan))

        # Turn off QOS dcb priority flow control on port channel
        self.send_cmd(
            self.LAG_PORT_CHANNEL.format(port_channel) +
            self.QOS_OFF)

        # Unbind IPL 1 from port channel
        self.send_cmd(
            self.LAG_PORT_CHANNEL.format(port_channel) + 'no ' + self.IPL)

        # Remove physical ports from channel group
        self.send_cmd(self.INTERFACE_CONFIG.format(port1) + 'no channel group')
        self.send_cmd(self.INTERFACE_CONFIG.format(port2) + 'no channel group')

        # Remove the port channel
        self.send_cmd('no ' + self.LAG_PORT_CHANNEL.format(port_channel))

        # Remove the vlan
        self.send_cmd('no vlan {}'.format(vlan))

        # Disable mlag protocol
        self.send_cmd('no ' + self.MLAG)

        # Disable QOS
        self.send_cmd('no ' + self.QOS_ENABLE)

    def configure_mlag(self,
                       vlan,
                       port_channel,
                       cidr_mlag_ipl,
                       ipaddr_mlag_ipl_peer,
                       ipaddr_mlag_vip,
                       mlag_ipl_ports):

        # Enable IP routing
        self.send_cmd(self.IP_ROUTING)

        # Enable QoS
        self.send_cmd(self.QOS_ENABLE)

        # Enable MLAG protocol commands
        self.send_cmd(self.MLAG)

        # Create MLAG VLAN
        self.create_vlan(vlan)

        # Create a LAG
        self.send_cmd(
            self.LAG_PORT_CHANNEL.format(port_channel))

        # Map a physical port to the LAG in active mode (LACP)
        # for port in self.inv.yield_mlag_ports(switch_index):
        for port in mlag_ipl_ports:
            self.send_cmd(
                self.INTERFACE_CONFIG.format(port) +
                self.LAG_ACTIVE.format(port_channel))

        # Set this LAG as an IPL
        self.send_cmd(
            self.LAG_PORT_CHANNEL.format(port_channel) + self.IPL)

        # Enable QoS on this specific interface
        self.send_cmd(
            self.LAG_PORT_CHANNEL.format(port_channel) + self.QOS_ON)

        # Create VLAN interface
        self.send_cmd(
            self.INTERFACE_VLAN.format(vlan))

        # Set MLAG IPL IP address
        self.send_cmd(
            self.INTERFACE_VLAN.format(vlan) +
            ' ' +
            self.IP_CIDR.format(cidr_mlag_ipl))

        # Set MLAG Peer IP address
        self.send_cmd(
            self.INTERFACE_VLAN.format(vlan) +
            ' ' +
            self.IPL +
            ' ' +
            self.PEER_ADDR.format(ipaddr_mlag_ipl_peer))

        # Set MLAG VIP
        if ipaddr_mlag_vip:
            self.send_cmd(self.MLAG_VIP % ipaddr_mlag_vip)
        else:
            self.send_cmd(self.MLAG_VIP.split(' ip')[0])

    def create_mlag_interface(self, mlag_ifc):
        # Create MLAG interface
        self.send_cmd(
            self.MLAG_PORT_CHANNEL.format(mlag_ifc))

        self.send_cmd(
            self.MLAG_PORT_CHANNEL.format(mlag_ifc) + self.STP_PORT_TYPE_EDGE)

        self.send_cmd(
            self.MLAG_PORT_CHANNEL.format(mlag_ifc) + self.STP_BPDUFILTER_ENABLE)

    def remove_mlag_interface(self, mlag_ifc):
        # Remove MLAG interface
        self.send_cmd(
            'no ' + self.MLAG_PORT_CHANNEL.format(mlag_ifc))

    def show_mlag_interfaces(self):
        return self.send_cmd(self.SHOW_IFC_MLAG_PORT_CHANNEL)

    def bind_port_to_mlag_interface(self, port, mlag_ifc=None):
        """ Bind a port to an MLAG interface and enable it. If no mlag
        interface is specified, the port is bound to the mlag interface
        number matching the first port number.
        Args:
            port: (int or string) Physical port to add to the MLAG port
            channel
            mlag_ifc: (int or string) MLAG interface (MLAG port channel)
            This port channel must already exist. (create_mlag_interface(self,
            mlag_ifc))
        """
        if mlag_ifc is None:
            mlag_ifc = port
        self.send_cmd(
            self.INTERFACE_CONFIG.format(port) + self.MLAG_ACTIVE.format(port))

        self.send_cmd(
            self.MLAG_PORT_CHANNEL.format(mlag_ifc) + self.NO_SHUTDOWN)


class switch(object):
    @staticmethod
    def factory(host=None, userid=None, password=None, mode=None,
                outfile=None):
        return Mellanox(host, userid, password, mode, outfile)
