#!/usr/bin/env python3
"""Get switch model information and assign class."""

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

import sys
import re
from orderedattrdict import AttrDict

from lib.inventory import Inventory
from lib.logger import Logger
from lib.ssh import SSH


class GetSwitchInfoAssignClass(object):
    """Get switch model information and assign class.

    This class is responsible for collection switch model information
    and assign the corresponding switch class.
    """

    supported_mgmt_switches = (
        ('G8052', 'Lenovo'),)

    supported_data_switches = (
        ('MLNX-OS', 'Mellanox'),)

    MGMT_SWITCH_TYPE = 'mgmt'
    DATA_SWITCH_TYPE = 'data'

    ENABLE_REMOTE_CONFIG_MGMT = 'enable;configure terminal; %s'
    SHOW_VERSION_MTM = 'show version | include ^MTM'
    MODEL = 'Model'
    MTM_VALUE = 'MTM Value'

    ENABLE_REMOTE_CONFIG_DATA = 'cli enable "configure terminal" "%s"'
    SHOW_VERSION_PRODUCT = 'show version | include ^Product'
    PRODUCT_NAME = 'Product name'
    SHOW_INVENTORY_CHASSIS = 'show inventory | include ^CHASSIS'
    CHASSIS = 'CHASSIS'

    def __init__(self, log, inv_file):
        self.info_list = []
        self.class_list = []
        self.info_dict = AttrDict()
        self.class_dict = AttrDict()
        self.ipv4 = None
        self.userid = None
        self.password = None
        self.enable_remote = None

        self.inv = Inventory(log, inv_file)
        self.log = log

    def update_mgmt_switch_info(self):
        """Update management switch model information and assign class."""

        self.enable_remote = self.ENABLE_REMOTE_CONFIG_MGMT
        self.info_list = []
        self.class_list = []
        for switch in self.inv.yield_switches(self.inv.SwitchType.MGMT):
            self.info_dict = AttrDict()
            self.class_dict = AttrDict()
            self.ipv4 = switch.ip_addr
            self.userid = switch.userid
            self.password = switch.password
            switch_valid = False

            output = self._send_cmd(self.SHOW_VERSION_MTM, 'Query MTM', False)

            switch_valid |= self._set_switch_info_class(
                r'\s+(\S+)\(config\)#',
                self.MODEL,
                output,
                self.supported_mgmt_switches)

            switch_valid |= self._set_switch_info_class(
                r'%s:\s+(\S+)\s+' % self.MTM_VALUE,
                self.MTM_VALUE,
                output,
                self.supported_mgmt_switches)

            if not switch_valid:
                if self.info_list:
                    self.log.error(
                        'Unsupported management switch: %s' %
                        self.info_dict)
                else:
                    self.log.error('Management switch could not be identified')
                sys.exit(1)

        if self.info_list:
            self.inv.update_switch_model_info(
                self.inv.SwitchType.MGMT, self.info_list)
            self.inv.update_switch_class(
                self.inv.SwitchType.MGMT, self.class_list)

    def update_data_switch_info(self):
        """Update data switch model information and assign class."""

        self.enable_remote = self.ENABLE_REMOTE_CONFIG_DATA
        self.info_list = []
        self.class_list = []
        for switch in self.inv.yield_switches(self.inv.SwitchType.DATA):
            self.info_dict = AttrDict()
            self.class_dict = AttrDict()
            self.ipv4 = switch.ip_addr
            self.userid = switch.userid
            self.password = switch.password
            switch_valid = False

            output = self._send_cmd(
                self.SHOW_VERSION_PRODUCT, 'Query Product Name', False)

            switch_valid |= self._set_switch_info_class(
                r'%s:\s+(\S+)\s+' % self.PRODUCT_NAME,
                self.PRODUCT_NAME,
                output,
                self.supported_data_switches)

            output = self._send_cmd(
                self.SHOW_INVENTORY_CHASSIS, 'Query CHASSIS', False)

            switch_valid |= self._set_switch_info_class(
                r'%s\s+(\S+)\s+' % self.CHASSIS,
                self.CHASSIS,
                output,
                self.supported_data_switches)

            if not switch_valid:
                if self.info_list:
                    self.log.error(
                        'Unsupported data switch: %s' %
                        self.info_dict)
                else:
                    self.log.error('Data switch could not be identified')
                sys.exit(1)

        if self.info_list:
            self.inv.update_switch_model_info(
                self.inv.SwitchType.DATA, self.info_list)
            self.inv.update_switch_class(
                self.inv.SwitchType.DATA, self.class_list)

    def _set_switch_info_class(
            self, pattern, attr, output, supported_switches):
        """Add model and class information to switch structure.

        Check whether switch is supported.

        Args:
            pattern (string): Command response pattern.
            attr (string): Attribute key.
            output (string): Command output.
            supported_switches (tuple of tuples): Supported switches.

        Returns:
            (boolean): Whether switch is supported based on given attribute.
        """

        pat = re.compile(
            pattern, re.MULTILINE)
        match = pat.search(output)
        if match:
            switch_attr = match.group(1)
            self.info_dict[attr] = switch_attr
            self.info_list.append(self.info_dict)
            attr_list = [sublist[0] for sublist in supported_switches]
            class_list = [sublist[1] for sublist in supported_switches]
            self.log.info(attr + ': ' + switch_attr + ' on ' + self.ipv4)
            if switch_attr in attr_list:
                index = attr_list.index(switch_attr)
                self.class_dict = class_list[index]
                self.class_list.append(self.class_dict)
                return True
        return False

    def _send_cmd(self, cmd, msg, status_check=True):
        """Send command to switch.

        Args:
            cmd (string): Switch command.
            msg (string): Description for log file.
            status_check (boolean): Whether to check for SSH error.

        Returns:
            (string): Command output from switch.
        """

        ssh = SSH(self.log)
        self.log.debug(cmd + ' on ' + self.ipv4)
        status, stdout_, _ = ssh.exec_cmd(
            self.ipv4,
            self.userid,
            self.password,
            self.enable_remote % cmd)
        if status:
            if status_check:
                self.log.error(
                    'Failed: ' + msg + ' on ' + self.ipv4 +
                    ' - Error: ' +
                    stdout_.replace('\n', ' ').replace('\r', ''))
                sys.exit(1)
            else:
                self.log.info(
                    msg + ' on ' + self.ipv4 +
                    ' - Error: ' +
                    stdout_.replace('\n', ' ').replace('\r', ''))
        else:
            self.log.info(msg + ' on ' + self.ipv4)
        return stdout_


if __name__ == '__main__':
    """Get switch model information and assign class.

    Args:
        INV_FILE (string): Inventory file.
        LOG_LEVEL (string): Log level.

    Raises:
       Exception: If parameter count is invalid.
    """

    LOG = Logger(__file__)

    if len(sys.argv) != 4:
        try:
            raise Exception()
        except:
            LOG.error('Invalid argument count')
            sys.exit(1)

    INV_FILE = sys.argv[1]
    SWITCH_TYPE = sys.argv[2]
    LOG.set_level(sys.argv[3])

    SWITCH = GetSwitchInfoAssignClass(LOG, INV_FILE)
    if SWITCH_TYPE == SWITCH.MGMT_SWITCH_TYPE:
        SWITCH.update_mgmt_switch_info()
    elif SWITCH_TYPE == SWITCH.DATA_SWITCH_TYPE:
        SWITCH.update_data_switch_info()
    else:
        try:
            raise Exception()
        except:
            LOG.error(
                "Invalid switch type '%s', expecting '%s' or '%s'" % (
                    SWITCH_TYPE,
                    SWITCH.MGMT_SWITCH_TYPE,
                    SWITCH.DATA_SWITCH_TYPE))
            sys.exit(1)
