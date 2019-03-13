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

import os
import stat
import subprocess
import re
import netaddr
from orderedattrdict import AttrDict
from enum import Enum
from filelock import Timeout, FileLock
from socket import gethostbyname
from time import sleep
from random import random

import lib.logger as logger
from lib.ssh import SSH
from lib.switch_exception import SwitchException
from lib.genesis import get_switch_lock_path

FILE_PATH = os.path.dirname(os.path.abspath(__file__))
SWITCH_LOCK_PATH = get_switch_lock_path()


class SwitchCommon(object):
    ENABLE_REMOTE_CONFIG = 'configure terminal ; {} '
    IFC_ETH_CFG = 'interface ethernet {} '
    IFC_PORT_CH_CFG = 'interface port-channel {} '
    NO_IFC_PORT_CH_CFG = 'no interface port-channel {} '
    PORT_PREFIX = 'Eth'
    SEP = ';'
    SHOW_VLANS = 'show vlan'
    CREATE_VLAN = 'vlan {}'
    DELETE_VLAN = 'no vlan {}'
    SHOW_PORT = 'show interface brief'
    CLEAR_MAC_ADDRESS_TABLE = 'clear mac address-table dynamic'
    SHOW_MAC_ADDRESS_TABLE = 'show mac address-table ;'
    ENABLE_LACP = 'feature lacp'
    NO_CHANNEL_GROUP = 'no channel-group'
    CHANNEL_GROUP_MODE = 'channel-group {} mode {} '
    SHOW_PORT_CHANNEL = 'show port-channel summary'
    SWITCHPORT_MODE = 'switchport mode {} '
    SWITCHPORT_ACCESS_VLAN = 'switchport access vlan {} '
    SWITCHPORT_TRUNK_NATIVE_VLAN = 'switchport trunk native vlan {} '
    SWITCHPORT_TRUNK_ALLOWED_VLAN = 'switchport trunk allowed vlan {} {}'
    SET_MTU = 'mtu {}'
    NO_MTU = 'no mtu'
    SHUTDOWN = 'shutdown'
    NO_SHUTDOWN = 'no shutdown'
    FORCE = 'force'
    MGMT_INTERFACE_CONFIG = 'interface ip {}'
    SET_INTERFACE_IPADDR = ' ;ip address {}'
    SET_INTERFACE_MASK = ' ;ip netmask {}'
    SET_VLAN = ' ;vlan {}'
    SHOW_IP_INTERFACE_BRIEF = 'show ip interface brief'
    SHOW_INTERFACE = 'show interface vlan{}'
    SET_INTERFACE = ('feature interface-vlan ;'
                     'interface vlan {} ;'
                     'ip address {} {} ;'
                     'management ;'
                     'no shutdown')

    def __init__(self, host=None, userid=None,
                 password=None, mode=None, outfile=None):
        self.log = logger.getlogger()
        pass

    class AllowOp(Enum):
        ADD = 'add'
        ALL = 'all'
        EXCEPT = 'except'
        NONE = 'none'
        REMOVE = 'remove'

    class PortMode(Enum):
        ACCESS = 'access'
        FEX_FABRIC = 'fex-fabric'
        TRUNK = 'trunk'
        HYBRID = ''
        TRUNK_NATIVE = ''

    def send_cmd(self, cmd):
        if self.mode == 'passive':
            f = open(self.outfile, 'a+')
            f.write(cmd + '\n')
            f.close()
            return

        host_ip = gethostbyname(self.host)
        lockfile = os.path.join(SWITCH_LOCK_PATH, host_ip + '.lock')
        if not os.path.isfile(lockfile):
            os.mknod(lockfile)
            os.chmod(lockfile, stat.S_IRWXO | stat.S_IRWXG | stat.S_IRWXU)
        lock = FileLock(lockfile)
        cnt = 0
        while cnt < 5 and not lock.is_locked:
            if cnt > 0:
                self.log.info('Waiting to acquire lock for switch {}'.
                              format(self.host))
            cnt += 1
            try:
                lock.acquire(timeout=5, poll_intervall=0.05)  # 5 sec, 50 ms
                sleep(0.01)  # give switch a chance to close out comms
            except Timeout:
                pass
        if lock.is_locked:
            if self.ENABLE_REMOTE_CONFIG:
                cmd = self.ENABLE_REMOTE_CONFIG.format(cmd)
                self.log.debug(cmd)
            ssh = SSH()
            __, data, _ = ssh.exec_cmd(
                self.host,
                self.userid,
                self.password,
                cmd,
                ssh_log=True,
                look_for_keys=False)
            lock.release()
            # sleep 60 ms to give other processes a chance.
            sleep(0.06 + random() / 100)  # lock acquire polls at 50 ms
            if lock.is_locked:
                self.log.error('Lock is locked. Should be unlocked')
            return data.decode("utf-8")
        else:
            self.log.error('Unable to acquire lock for switch {}'.format(self.host))
            raise SwitchException('Unable to acquire lock for switch {}'.
                                  format(self.host))

    def get_enums(self):
        return self.PortMode, self.AllowOp

    def show_ports(self, format='raw'):
        if self.mode == 'passive':
            return None
        ports = {}
        port_info = self.send_cmd(self.SHOW_PORT)
        if format == 'raw':
            return port_info
        elif format == 'std':
            port_info = port_info.splitlines()
            for line in port_info:
                match = re.search(
                    r'Eth([0-9/]+)\s+(\d+)\s+\w+\s+(access|trunk)', line)
                if match:
                    # mode, avlans = self._get_port_detail(match)
                    ports[match.group(1)] = {
                        'mode': match.group(3),
                        'nvlan': match.group(2),
                        'avlans': ''}
            port_info = self.send_cmd('show interface trunk').split('Port')
            for item in port_info:
                if 'Vlans Allowed on Trunk' in item:
                    item = item.splitlines()
                    for line in item:
                        match = re.search(
                            r'Eth((?:\d+/)+\d+)\s+((?:\d+[,-])*\d+)', line)
                        if match:
                            ports[match.group(1)]['avlans'] = match.group(2)
            return ports

    def show_vlans(self):
        if self.mode == 'passive':
            return None
        self.log.debug(self.SHOW_VLANS)
        vlan_info = self.send_cmd(self.SHOW_VLANS)
        return vlan_info

    def show_native_vlan(self, port):
        if self.mode == 'passive':
            return None
        port = str(port)
        ports = self.show_ports(format='std')
        return ports[port]['nvlan']

    def set_switchport_mode(self, port, mode, vlan=None):
        port = str(port)
        cmd = self.IFC_ETH_CFG.format(port) + self.SEP
        cmd += self.SWITCHPORT_MODE.format(mode.value)
        if vlan:
            if mode.value == 'trunk':
                cmd += self.SEP + self.SWITCHPORT_TRUNK_NATIVE_VLAN.format(vlan)
            if mode.value == 'access':
                cmd += self.SEP + self.SWITCHPORT_ACCESS_VLAN.format(vlan)
        self.send_cmd(cmd)
        ports = self.show_ports(format='std')
        if port not in ports:
            msg = 'Unable to verify setting of switchport mode'
            msg += 'for port {}. May already be in a channel group.'
            msg.format(port)
            self.log.debug(msg)
            return
        if self.mode == 'passive' or ports[port]['mode'] == mode.value:
            self.log.debug(
                'Port {} is in {} mode'.format(port, mode.value))
        else:
            raise SwitchException(
                'Failed setting port {} to {} mode'.format(port, mode.value))

        if vlan:
            if self.mode == 'passive' or str(vlan) == ports[port]['nvlan']:
                msg = 'PVID/Native vlan {} set on port {}'.format(vlan, port)
                self.log.debug(msg)
            else:
                msg = 'Failed setting PVID/Native vlan {} on port {}'.format(
                    vlan, port)
                self.log.error(msg)
                raise SwitchException(msg)

    def is_port_in_trunk_mode(self, port):
        """Allows determination if a port is in 'trunk' mode.
        """
        if self.mode == 'passive':
            return None
        port = str(port)
        ports = self.show_ports(format='std')
        return self.PortMode.TRUNK.value in ports[port]['mode']

    def is_port_in_access_mode(self, port):
        if self.mode == 'passive':
            return None
        port = str(port)
        ports = self.show_ports('std')
        return self.PortMode.ACCESS.value in ports[port]['mode']

    def allowed_vlans_port(self, port, operation, vlans=''):
        """ configure vlans on a port channel
        ARGS:
            operation (enum of AllowOp): add | all | except | none | remove
            vlan (str or tuple or list). if type string, can be of the
            following formats: '4' or '4,5,8' or '5-10'
        """
        if isinstance(vlans, (tuple, list)):
            vlans = vlans[:]
            vlans = [str(vlans[i]) for i in range(len(vlans))]
            vlans = ','.join(vlans)
        else:
            vlans = str(vlans)
        cmd = self.IFC_ETH_CFG.format(port) + self.SEP + \
            self.SWITCHPORT_TRUNK_ALLOWED_VLAN.format(operation.value, vlans)
        self.send_cmd(cmd)

        res = self.is_vlan_allowed_for_port(vlans, port)
        if operation.value == 'add':
            if res is None:
                return
            elif not res:
                msg = 'Not all vlans in {} were added to port {}'. \
                    format(vlans, port)
                self.log.error(msg)
            else:
                self.log.debug('vlans {} were added to port {}'.
                               format(vlans, port))
        if operation.value == 'remove':
            if res is None:
                return
            elif res:
                msg = 'Not all vlans in {} were removed from port {}'. \
                    format(vlans, port)
                self.log.error(msg)
            else:
                self.log.debug('vlans {} were removed from port {}'.
                               format(vlans, port))

    def is_vlan_allowed_for_port(self, vlans, port):
        """ Test that all vlans in vlans are allowed for the given port
        Args:
            vlans: (int or str) string can be of form 'n', 'n,m,p', 'n-p'
            port: (int or str)
        Returns True if all vlans in vlans argument are allowed for port
        """
        if self.mode == 'passive':
            return None
        vlans = str(vlans)
        vlans = vlans.split(',')
        result = True
        port = str(port)
        ports = self.show_ports('std')
        if port not in ports:
            msg = 'Unable to verify setting of vlans '
            msg += 'for port {}. May already be in a channel group.'
            msg = msg.format(port)
            self.log.debug(msg)
            return
        avlans = ports[port]['avlans']
        avlans = avlans.split(',')
        for vlan in vlans:
            res = False
            for i, _vlans in enumerate(avlans):
                _vlans = _vlans.strip(' ')
                if not vlan:
                    res = True
                    break
                if not _vlans:
                    break
                elif '-' in vlan and vlan == _vlans:
                    res = True
                    break
                elif int(vlan) >= int(_vlans.split('-')[0]) and \
                        int(vlan) <= int(_vlans.split('-')[-1]):
                    res = True
                    break
                else:
                    pass
            result = result and res
        return result

    def create_vlan(self, vlan):
        self.send_cmd(self.CREATE_VLAN.format(vlan))
        if self.mode == 'passive' or self.is_vlan_created(vlan):
            self.log.debug('Created VLAN {}'.format(vlan))
        else:
            raise SwitchException('Failed creating VLAN {}'.format(vlan))

    def delete_vlan(self, vlan):
        self.send_cmd(self.DELETE_VLAN.format(vlan))
        if self.mode == 'active' and self.is_vlan_created(vlan):
            self.log.warning(
                'Failed deleting VLAN {}'.format(vlan))
            raise SwitchException(
                'Failed deleting VLAN {}'.format(vlan))
        self.log.info('vlan {} deleted.'.format(vlan))
        return

    def is_vlan_created(self, vlan):
        if self.mode == 'passive':
            return None
        if re.search(
                r'^' + str(vlan),
                self.send_cmd(self.SHOW_VLANS),
                re.MULTILINE):
            return True
        return False

    def set_mtu_for_port(self, port, mtu):
        # Bring port down
        self.send_cmd(
            self.IFC_ETH_CFG.format(port) + self.SEP + self.SHUTDOWN)

        # Set MTU
        if mtu == 0:
            self.send_cmd(
                self.IFC_ETH_CFG.format(port) + self.SEP + self.NO_MTU)
        else:
            self.send_cmd(
                self.IFC_ETH_CFG.format(port) + self.SEP + self.SET_MTU.format(mtu))

        # Bring port up
        self.send_cmd(
            self.IFC_ETH_CFG.format(port) + self.SEP + self.NO_SHUTDOWN)

    def show_mac_address_table(self, format=False):
        """Get switch mac address table.

        The returned text string can be raw or optionally fomatted.

        Args:
            format (boolean) : set to 'dict' or 'std' to return a dictionary
        Returns:
            raw string if format=False
            dictionary of ports and mac address values in native switch form
            if format = 'dict'.
            ordered dictionary of ports and mac address values in a standard
            format if fmt = 'std'.
        """
        if self.mode == 'passive':
            mac_info = {}
            try:
                with open(self.host, 'r') as f:
                    mac_info = f.read()

            except IOError as error:
                self.log.error(
                    'Passive switch MAC address table file not found (%s)' % error)
                raise
            mac_info = self.get_port_to_mac(mac_info)
            return mac_info

        mac_info = self.send_cmd(self.SHOW_MAC_ADDRESS_TABLE)
        if not format or format == 'raw':
            return mac_info
        return self.get_port_to_mac(mac_info, format, self.PORT_PREFIX)

    def clear_mac_address_table(self):
        """Clear switch mac address table by writing the CLEAR_MAC_ADDRESS_TABLE
        string to the switch.
        Args: None.  The CLEAR_MAC_ADDRESS_TABLE string can be over-ridden in
              the specific switch class module.
        Returns: Nothing
        """
        self.send_cmd(self.CLEAR_MAC_ADDRESS_TABLE)

    def is_pingable(self):
        try:
            if self.mode == 'passive':
                return None
            output = subprocess.check_output(
                ['bash', '-c', 'ping -c2 -i.5 ' + self.host]).decode("utf-8")
            if '0% packet loss' in output:
                return True
            else:
                return False
        except subprocess.CalledProcessError as exc:
            self.log.error('Unable to ping switch.  {}'.format(exc))
            return False

    def get_port_to_mac(self, mac_address_table, fmt='std', port_prefix=' '):
        """Convert MAC address table to dictionary.

        Args:
            mac_address_table (string): MAC address table. Lines delimited
            with line feed.  Assumes a header row with "Port" as a column
            header followed by a delimiter row composed of dashes ('-')
            which delimit columns.  Handles MAC addresses formatted
            as 'cc:cc:cc:cc:cc:cc' or 'cccc.cccc.cccc'

        Returns:
            dictionary: Keys are string port numbers and values are a list
            of MAC addresses both in native switch format.
        """
        import lib.logger as logger
        log = logger.getlogger()
        pos = None
        mac_dict = AttrDict()

        _mac_iee802 = r'([\dA-F]{2}[\.:-]){5}([\dA-F]{2})'
        _mac_cisco = r'([\dA-F]{4}\.){2}[\dA-F]{4}'
        _mac_all = "%s|%s" % (_mac_iee802, _mac_cisco)
        _mac_regex = re.compile(_mac_all, re.I)

        mac_address_table = mac_address_table.splitlines()
        p2 = re.compile('Port', re.IGNORECASE)
        for line in mac_address_table:
            # find row with 'Port' label
            match = p2.search(line)
            if match:
                pos = match.start()
            # find header seperator row
            if re.search(r'--+', line):
                log.debug('Found header seperator row: {}'.format(line))
                iter = re.finditer(r'--+', line)
                for i, match in enumerate(iter):
                    # find column aligned with 'Port'
                    if (pos is not None and pos >= match.span()[0] and
                            pos < match.span()[1]):
                        port_span = (match.span()[0], match.span()[1])
            # find rows with MACs
            match = _mac_regex.search(line)

            if match:
                line = self.sanitize_line(line)
                mac = match.group()
                log.debug('Found mac address: {}'.format(mac))
                _mac = mac
                if fmt == 'std':
                    _mac = mac[0:2]
                    mac = re.sub(r'\.|\:', '', mac)
                    for i in (2, 4, 6, 8, 10):
                        _mac = _mac + ':' + mac[i:i + 2]
                # Extract port section of row
                port = line[port_span[0] - 1:port_span[1]].strip(' ')
                if fmt == 'std':
                    port = port.replace(port_prefix, '')
                if port not in mac_dict.keys():
                    mac_dict[port] = [_mac]
                else:
                    mac_dict[port].append(_mac)
        return mac_dict

    @staticmethod
    def sanitize_line(line):
        return line

    def enable_lacp(self):
        self.send_cmd(self.ENABLE_LACP)

    def show_port_channel_interfaces(self):
        return self.send_cmd(self.SHOW_PORT_CHANNEL)

    def remove_ports_from_port_channel_ifc(self, ports):
        # Remove interface from channel-group
        for port in ports:
            self.send_cmd(
                self.IFC_ETH_CFG.format(port) + self.SEP + self.NO_CHANNEL_GROUP)
        port_chan_summ = self.show_port_channel_interfaces()
        for port in ports:
            if re.findall(self.PORT_PREFIX + str(port) + r'[\s+|\(]',
                          port_chan_summ):
                self.log.error('Port {} not removed from port channel'.format(
                    port))

    def remove_port_channel_ifc(self, lag_ifc):
        # Remove LAG interface
        cmd = self.NO_IFC_PORT_CH_CFG.format(lag_ifc)

        self.send_cmd(cmd)

    def create_port_channel_ifc(self, lag_ifc):
        # Create a LAG
        cmd = self.IFC_PORT_CH_CFG.format(lag_ifc)

        self.send_cmd(cmd)

    def set_port_channel_mode(self, port_ch, mode, nvlan=None):
        cmd = self.IFC_PORT_CH_CFG.format(port_ch) + self.SEP +\
            self.SWITCHPORT_MODE.format(mode.value)
        if nvlan:
            cmd += self.SEP + self.SWITCHPORT_TRUNK_NATIVE_VLAN.format(nvlan)

        self.send_cmd(cmd)

    def add_ports_to_port_channel_ifc(self, ports, lag_ifc, mode='active'):
        # Map a physical port to the LAG in specified mode (active for LACP)
        for port in ports:
            cmd = self.IFC_ETH_CFG.format(port) + self.SEP + \
                self.CHANNEL_GROUP_MODE.format(lag_ifc, mode)

            self.send_cmd(cmd)
        port_chan_summ = self.show_port_channel_interfaces()
        for port in ports:
            if not re.findall(self.PORT_PREFIX + str(port) + r'[\s+|\(]',
                              port_chan_summ):
                self.log.error('Port {} not added to port channel {}'.format(
                    port, lag_ifc))
                raise SwitchException('Port {} not added to port channel {}'.
                                      format(port, lag_ifc))

    def add_vlans_to_port_channel(self, port, vlans):
        """    DEPRECATED   """
        ports = self.show_ports('std')
        port = str(port)
        if port not in ports:
            raise SwitchException(
                'Port inaccessible (may already be in port channel).'
                '\nFailed adding vlans {} to port {}'.format(vlans, port))
        # Enable trunk mode for port
        self.send_cmd(self.SET_LAG_PORT_CHANNEL_MODE_TRUNK.format(port))

        # Add VLANs to port
        for vlan in vlans:
            self.send_cmd(
                self.LAG_PORT_CHANNEL.format(port) +
                'switchport trunk allowed vlan add {}'.format(vlan))

    def allowed_vlans_port_channel(self, port, operation, vlans=''):
        """ configure vlans on a port channel
        ARGS:
            operation (str): add | all | except | none | remove
            vlan (str or tuple or list). if type string, can be of the
            following formats: '4' or '4,5,8' or '5-10'
        """
        if isinstance(vlans, (tuple, list)):
            vlans = [str(vlans[i]) for i in range(len(vlans))]
            vlans = ','.join(vlans)
        else:
            vlans = str(vlans)

        cmd = self.IFC_PORT_CH_CFG.format(port) + self.SEP + \
            self.SWITCHPORT_TRUNK_ALLOWED_VLAN.format(operation.value, vlans)
        self.send_cmd(cmd)

    def set_mtu_for_port_channel(self, port, mtu):
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

    def remove_interface(self, vlan, host, netmask):
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
            self.send_cmd('interface vlan {} ;no ip address {} {}'.
                          format(vlan, host, netmask))
            self.send_cmd('no interface vlan {}'.format(vlan))
            interfaces = self.show_interfaces(vlan, host, netmask, format='std')
            if interfaces[-1][0]['configured']:
                self.log.debug('Failed to remove interface Vlan {}.'.format(vlan))
                raise SwitchException('Failed to remove interface Vlan {}.'.
                                      format(vlan))
        else:
            if interfaces[-1][0]['found vlan']:
                self.log.debug('Specified interface on vlan {} does not exist.'.
                               format(vlan))
                raise SwitchException('Failed to remove interface Vlan {}.'.
                                      format(vlan))

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
                format is returned. If format is set to 'std', a 'standard'
                format is returned.
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
        ifc_info = ''
        vlan = str(vlan)
        found, found_vlan = False, False
        ifc_info_brief = self.send_cmd(self.SHOW_IP_INTERFACE_BRIEF)
        vlan_ifcs = re.findall(r'Vlan(\d+)', ifc_info_brief, re.MULTILINE)
        for ifc in vlan_ifcs:
            ifc_info = ifc_info + self.send_cmd(self.SHOW_INTERFACE.format(ifc))
        if format is None:
            return ifc_info
        ifc_info = ifc_info.split('Vlan')
        for line in ifc_info:
            match = re.search(r'(\d+).*Internet Address is\s+'
                              r'((\w+.\w+.\w+.\w+)/\d+)', line, re.DOTALL)
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

    def configure_interface(self, host, netmask, vlan=1, intf=None):
        """Configures a management interface. This implementation checks
        if the host ip is already in use. If it is, a check is made to
        see if it is configured as specified. If not, an exception is raised.
        Lenovo numbers interfaces. The specified vlan will be created if it
        does not already exist.

        When implementing this method for a new switch, minimally this method
        should configure (overwrite if necessary) the specified interface.

        Args:
            host (string): hostname or ipv4 address in dot decimal notation
            netmask (string): netmask in dot decimal notation
            vlan (string): String representation of integer between
            1 and 4094. The management interface is created on the specified
            vlan intf (string): optional. String representation of integer
            between 1 and 128.
        raises:
            SwitchException if unable to program interface
        """
        vlan = str(vlan)
        interfaces = self.show_interfaces(vlan, host, netmask, format='std')
        if interfaces[-1][0]['configured']:
            self.log.debug(
                'Switch interface vlan {} already configured'.format(vlan))
            return
        if interfaces[-1][0]['found vlan']:
            self.log.debug(
                'Conflicting address. Interface vlan {} already configured'.
                format(vlan))
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
