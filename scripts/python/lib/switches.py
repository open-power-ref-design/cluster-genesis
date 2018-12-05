#!/usr/bin/env python3
"""Library for Network Switch Classes."""

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

import paramiko
import re
from orderedattrdict import AttrDict


class Switch(object):
    """Generic switch class.

    Top level switch class defining general attributes and methods.

    Args:
        log (:obj:`Logger`): Log file object.
        ip (string): Switch management interface IP address.
        userid (string): Switch management interface login user ID.
        password (string): Switch management interface login password.
        port (int): Switch management interface SSH port. Defaults to 22.
    """

    _mac_iee802 = '([\dA-F]{2}[\.:-]){5}([\dA-F]{2})'
    _mac_cisco = '([\dA-F]{4}\.){2}[\dA-F]{4}'
    _mac_all = "%s|%s" % (_mac_iee802, _mac_cisco)
    _mac_regex = re.compile(_mac_all, re.I)

    _show_macs_cmd = '\"show mac-address-table\"'
    _clear_macs_cmd = '\"clear mac-address-table dynamic\"'

    def __init__(self, log, ip, userid, password, port=22):
        self.log = log
        self.ip = ip
        self.userid = userid
        self.password = password
        self.port = port

        self.DEBUG = b'DEBUG'
        self.INFO = b'INFO'
        self.SSH_LOG = 'switch-%s-log.txt' % ip

    def issue_cmd(self, cmd):
        """Issue command to switch via SSH and return its stdout.

        Args:
            cmd (string): Command to issue.

        Returns:
            string: Command stdout.
        """
        if self.log_level == self.DEBUG or self.log_level == self.INFO:
            paramiko.util.log_to_file(self.SSH_LOG)
        s = paramiko.SSHClient()
        s.load_system_host_keys()
        s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        s.connect(self.ip, self.port, self.userid, self.password)
        stdin, stdout, stderr = s.exec_command(
            self.ENABLE_REMOTE_CONFIG % (cmd))
        output = stdout.read()
        s.close()
        return output


class PassiveSwitch(Switch):
    def __init__(self, log, name):
        self.name = name
        super(PassiveSwitch, self).__init__(log, name, None, None, None)
        self.log.debug('creating passive switch object %s' % self.name)

    def get_port_to_mac(self, mac_table_file_path):
        """Get Attribute Dictionary mapping ports to lists of MAC address.

        The returned attribute dictionary provides port numbers mapped to lists
        of MAC addresses (from the switch MAC address table). Individual ports
        can easily be retrieved by using the port number as the dictionary key.

        Args:
            mac_table_file_path (string): Path to text file containing switch
                MAC address table.

        Returns:
            AttrDict: Port to MAC address mapping.
        """
        port_to_mac = AttrDict()
        mac_line_list = []
        port_index = None
        mac_index = None

        mac_header_re = re.compile('mac address', re.I)
        single_s = re.compile('(\S)\s(\S)')

        self.log.debug('opening %s' % mac_table_file_path)
        try:
            with open(mac_table_file_path, 'r') as f:
                for line in f:
                    if self._mac_regex.search(line):
                        self.log.debug('Found mac address: %s' % line.rstrip())
                        mac_line_list.append(line.split())
                    elif mac_header_re.search(line):
                        self.log.debug('Found possible header: %s' % line.rstrip())
                        header = single_s.sub('\g<1>\g<2>', line.lower()).split()
                        if set(["macaddress", "port"]) <= set(header):
                            self.log.debug('header: %s' % header)
                            mac_index = header.index("macaddress")
                            port_index = header.index("port")
        except IOError as error:
            self.log.error(
                'Passive switch MAC address table file not found (%s)' % error)
            raise

        if mac_index is None and mac_line_list:
            for index, value in enumerate(mac_line_list[0]):
                if self._mac_regex.search(value):
                    mac_index = index

        if port_index is None and mac_line_list:
            if mac_index == 1:
                port_index = 0
            else:
                port_index = 1

        for line in mac_line_list:
            mac = line[mac_index].lower()
            mac = mac.replace("-", ":")
            mac = mac.replace(".", ":")
            for i in [2, 5, 8, 11, 14]:
                if mac[i] != ":":
                    mac = mac[:i] + ":" + mac[i:]

            if "/" in line[port_index]:
                port = str(line[port_index].split("/", 1)[1])
            else:
                port = str(line[port_index])

            if port in port_to_mac:
                port_to_mac[port].append(mac)
            else:
                port_to_mac[port] = [mac]
            self.log.debug('port_to_mac[%s] = %s' % (port, port_to_mac[port]))

        return port_to_mac

    def issue_cmd(self, cmd):
        """Passive override of generic 'issue command' method.

        Passive switch method to skip switch commands. Instead a debug log is
            written.

        Todo:
            * Write commands to separate files for each switch.

        Args:
            cmd (string): Command to issue.

        Returns:
            string: Empty string.
        """
        self.log.debug('Passive switch (%s) command: %s' % (self.name, cmd))
        return ""

    def clear_mac_address_table(self):
        """Passive clear MAC address table method.

        Passive switch method to skip 'clear MAC address' calls. Instead a
            debug log is written.

        Note:
            There are no arguments or returns.
        """
        self.log.debug(
            'Passive switch (%s) clear MAC address table issued' % self.name)
