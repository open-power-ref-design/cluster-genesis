#!/usr/bin/env python3
"""Write switch memory."""

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

from lib.inventory import Inventory
from lib.logger import Logger
from lib.ssh import SSH


class WriteSwitchMemory(object):
    """Write switch memory."""

    ENABLE_REMOTE_CONFIG_MGMT = 'enable\nconfigure terminal\n%s'
    ENABLE_REMOTE_CONFIG_DATA = 'cli enable "configure terminal" "%s"'
    WRITE_MEMORY = 'write memory'

    def __init__(self, log, inv_file):
        self.inv = Inventory(log, inv_file)
        self.log = log
        self.enable_remote = None
        self.userid = None
        self.password = None
        self.ipv4 = None

    def write_mgmt_switch_memory(self):
        self.enable_remote = self.ENABLE_REMOTE_CONFIG_MGMT
        for self.ipv4 in self.inv.yield_mgmt_switch_ip():
            pass
        self.userid = self.inv.get_userid_mgmt_switch()
        self.password = self.inv.get_password_mgmt_switch()
        self._send_cmd(self.WRITE_MEMORY, 'Write memory', False)

    def write_data_switch_memory(self):
        self.enable_remote = self.ENABLE_REMOTE_CONFIG_DATA
        for self.ipv4, value in self.inv.get_data_switches().items():
            self.userid = value['user']
            self.password = value['password']
            self._send_cmd(self.WRITE_MEMORY, 'Write memory')

    def _send_cmd(self, cmd, msg, status_check=True):
        ssh = SSH(self.log)
        self.log.debug('Switch cmd: ' + repr(cmd))
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
                if msg:
                    self.log.info(
                        msg + ' on ' + self.ipv4)
        else:
            if msg:
                self.log.info(msg + ' on ' + self.ipv4)
        return stdout_


if __name__ == '__main__':
    """Write switch memory.

    Args:
        INV_FILE (string): Inventory file.
        LOG_LEVEL (string): Log level.

    Raises:
        Exception: If parameter count is invalid.
    """

    LOG = Logger(__file__)

    ARGV_MAX = 3
    ARGV_COUNT = len(sys.argv)
    if ARGV_COUNT > ARGV_MAX:
        try:
            raise Exception()
        except Exception:
            LOG.error('Invalid argument count')
            sys.exit(1)

    INV_FILE = sys.argv[1]
    LOG.set_level(sys.argv[2])

    SWITCHES = WriteSwitchMemory(LOG, INV_FILE)
    SWITCHES.write_mgmt_switch_memory()
    SWITCHES.write_data_switch_memory()
