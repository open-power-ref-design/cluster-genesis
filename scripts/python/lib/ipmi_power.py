#!/usr/bin/env python3
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

import sys
from pyghmi import exceptions as pyghmi_exception

import lib.logger as logger
from lib.utilities import bmc_ipmi_login


class IpmiPower(object):
    WAIT = False
    POWER_ON = 'on'
    POWER_OFF = 'off'
    POWERSTATE = 'powerstate'
    ERROR = 'error'

    def __init__(self):
        self.log = logger.getlogger()
        self.ipmi_cmd = None

    def _command(self, bmc):
        try:
            self.ipmi_cmd = bmc_ipmi_login(bmc['ipv4'],
                                           bmc['userid'],
                                           bmc['password'])
        except pyghmi_exception.IpmiException as exc:
            self.log.error(
                'IPMI \'Command\' failed - Rack: %s - IP: %s, %s' %
                (bmc['rack_id'], bmc['ipv4'], str(exc)))
            sys.exit(1)

    def _get_power(self, bmc):
        try:
            _rc = self.ipmi_cmd.get_power()
        except pyghmi_exception.IpmiException as exc:
            self.log.error(
                'IPMI \'get_power\' failed - Rack: %s - IP: %s, %s' %
                (bmc['rack_id'], bmc['ipv4'], str(exc)))
            sys.exit(1)
        return _rc

    def is_power_on(self, bmc):
        self._command(bmc)
        _rc = self._get_power(bmc)
        if _rc.get(self.POWERSTATE) == self.POWER_ON:
            return True, _rc.get(self.POWERSTATE)
        return False, _rc.get(self.POWERSTATE)

    def is_power_off(self, bmc):
        self._command(bmc)
        _rc = self._get_power(bmc)
        if _rc.get(self.POWERSTATE) == self.POWER_OFF:
            return True, _rc.get(self.POWERSTATE)
        return False, _rc.get(self.POWERSTATE)

    def set_power_on(self, bmc):
        self._command(bmc)
        try:
            _rc = self.ipmi_cmd.set_power(self.POWER_ON, self.WAIT)
        except pyghmi_exception.IpmiException as exc:
            self.log.error(
                'IPMI \'set_power\' on failed - Rack: %s - IP: %s, %s' %
                (bmc['rack_id'], bmc['ipv4'], str(exc)))
            sys.exit(1)

        if self.ERROR in _rc:
            self.log.error(
                'IPMI power on failed - Rack: %s - IP: %s, %s' %
                (bmc['rack_id'], bmc['ipv4'], _rc[self.ERROR]))
            sys.exit(1)

    def set_power_off(self, bmc):
        self._command(bmc)
        try:
            _rc = self.ipmi_cmd.set_power(self.POWER_OFF, self.WAIT)
        except pyghmi_exception.IpmiException as exc:
            self.log.error(
                'IPMI power \'set_power\' off failed - Rack: %s - IP: %s, %s' %
                (bmc['rack_id'], bmc['ipv4'], str(exc)))
            sys.exit(1)

        if self.ERROR in _rc:
            self.log.error(
                'IPMI power off failed - Rack: %s - IP: %s, %s' %
                (bmc['rack_id'], bmc['ipv4'], _rc[self.ERROR]))
            sys.exit(1)
