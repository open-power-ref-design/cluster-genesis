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
import pyghmi.exceptions as ipmi_exc

from lib.inventory import Inventory
from lib.logger import Logger
from lib.utilities import bmc_ipmi_login


class IpmiData(object):
    IPMI_SYSTEM_FIRMWARE = b'System Firmware'
    IPMI_SYSTEM = b'System'
    IPMI_NODE1 = b'NODE 1'
    IPMI_HARDWARE_VERSION = b'Hardware Version'
    IPMI_PRODUCT_NAME = b'Product name'
    IPMI_CHASSIS_PART_NUMBER = b'Chassis part number'
    IPMI_CHASSIS_SERIAL_NUMBER = b'Chassis serial number'
    IPMI_MODEL = b'Model'
    IPMI_SERIAL_NUMBER = b'Serial Number'
    IPMI_OPENPOWER_FW = b'OpenPOWER Firmware'
    PPC64 = b'ppc64'
    ARCHITECTURE = b'architecture'
    NONE = b'None'

    def __init__(self, log, inv_file):
        self.inv = Inventory(log, inv_file)
        self.log = log

        for _, _, self.group, self.index, self.node in \
                self.inv.yield_nodes():
            ipmi_cmd = bmc_ipmi_login(
                self.node[self.inv.INV_IPV4_IPMI],
                self.node[self.inv.INV_USERID_IPMI],
                self.node[self.inv.INV_PASSWORD_IPMI])

            components = []
            try:
                for desc in ipmi_cmd.get_inventory_descriptions():
                    components.append(desc)
            except ipmi_exc.IpmiException as exc:
                self._log_ipmi_exception(exc)
                continue

            self.comp_name = self.IPMI_SYSTEM_FIRMWARE
            if self.comp_name in components:
                try:
                    self.comp_value = ipmi_cmd.get_inventory_of_component(
                        self.comp_name)
                    self._get_ipmi_architecture()
                    self._get_ipmi_field(self.IPMI_HARDWARE_VERSION)
                except ipmi_exc.IpmiException as exc:
                    self._log_ipmi_exception(exc)

            self.comp_name = self.IPMI_SYSTEM
            if self.comp_name in components:
                try:
                    self.comp_value = ipmi_cmd.get_inventory_of_component(
                        self.comp_name)
                    self._get_ipmi_field(self.IPMI_PRODUCT_NAME)
                    self._get_ipmi_field(self.IPMI_CHASSIS_PART_NUMBER)
                    self._get_ipmi_field(self.IPMI_CHASSIS_SERIAL_NUMBER)
                    self._get_ipmi_field(self.IPMI_MODEL)
                    self._get_ipmi_field(self.IPMI_SERIAL_NUMBER)
                except ipmi_exc.IpmiException as exc:
                    self._log_ipmi_exception(exc)

            self.comp_name = self.IPMI_NODE1
            if self.comp_name in components:
                try:
                    self.comp_value = ipmi_cmd.get_inventory_of_component(
                        self.comp_name)
                    self._get_ipmi_field(self.IPMI_CHASSIS_PART_NUMBER)
                    self._get_ipmi_field(self.IPMI_CHASSIS_SERIAL_NUMBER)
                except ipmi_exc.IpmiException as exc:
                    self._log_ipmi_exception(exc)

    def _log_ipmi_exception(self, exc):
        self.log.warning(
            self.node[self.inv.INV_IPV4_IPMI] +
            ": Could not collect IPMI data for '" +
            self.comp_name +
            "' component" +
            ' - Error: ' + str(exc))

    def _get_ipmi_architecture(self):
        if self.comp_value:
            if (self.comp_value[self.IPMI_PRODUCT_NAME] ==
                    self.IPMI_OPENPOWER_FW):
                value = self.get_ipmi(
                    self.comp_name,
                    self.IPMI_PRODUCT_NAME,
                    self.comp_value,
                    self.PPC64)
                if value is not None and value != self.NONE:
                    self.inv.add_to_node(
                        self.group,
                        self.index,
                        self.ARCHITECTURE,
                        value)

    def _get_ipmi_field(self, ipmi_field):
        if self.comp_value:
            value = self.get_ipmi(
                self.comp_name,
                ipmi_field,
                self.comp_value)
            if value is not None and value != self.NONE:
                self.inv.add_to_node(
                    self.group,
                    self.index,
                    str(ipmi_field.lower().replace(' ', '_').replace(
                        '-', '_')),
                    value)

    def get_ipmi(
            self,
            ipmi_key,
            ipmi_field,
            ipmi_value,
            inv_value=None):
        if ipmi_field in ipmi_value:
            self.log.info(
                self.node[self.inv.INV_IPV4_IPMI] +
                ": '" +
                ipmi_key + '[' + ipmi_field + ']' +
                "' = " +
                str(ipmi_value[ipmi_field]))
            if inv_value:
                return inv_value
            return str(ipmi_value[ipmi_field])

        self.log.info(
            self.node[self.inv.INV_IPV4_IPMI] +
            ": '" +
            ipmi_key + '[' + ipmi_field + ']' +
            "' not found")
        return None


if __name__ == '__main__':
    """
    Arg1: inventory file
    Arg2: log level
    """
    LOG = Logger(__file__)

    if len(sys.argv) != 3:
        try:
            raise Exception()
        except:
            LOG.error('Invalid argument count')
            sys.exit(1)

    INV_FILE = sys.argv[1]
    LOG.set_level(sys.argv[2])

    IpmiData(LOG, INV_FILE)
