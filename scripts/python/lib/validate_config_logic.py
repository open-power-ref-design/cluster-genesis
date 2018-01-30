#!/usr/bin/env python
"""Config logic validation"""

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

import lib.logger as logger
from lib.exception import UserException


class ValidateConfigLogic(object):
    """Config logic validation

    Args:
        config (object): Config
    """

    CONFIG_VERSION = 'v2.0'

    def __init__(self, config):
        self.log = logger.getlogger()
        self.config = config
        from lib.config import Config
        self.cfg = Config(self.config)

    def _validate_version(self):
        """Validate version

        Exception:
            If config version is not supported
        """

        if self.config.version != self.CONFIG_VERSION:
            exc = "Config version '{}' is not supported".format(
                self.config.version)
            self.log.error(exc)
            raise UserException(exc)

    def _validate_netmask_prefix(self):
        """Validate netmask and prefix

        The netmask or prefix needs to be specified, but not both.

        Exception:
            If both or neither the netmask and prefix are specified.
        """

        msg_either = "Either 'netmask' or 'prefix' needs to be specified"
        msg_both = "Both 'netmask' and 'prefix' can not be specified"

        for element in (
                self.config.deployer.networks.mgmt,
                self.config.deployer.networks.client):
            for member in element:
                try:
                    netmask = member.netmask
                except AttributeError:
                    netmask = None
                try:
                    prefix = member.prefix
                except AttributeError:
                    prefix = None

                if netmask is None and prefix is None:
                    exc = self.log.error("%s - %s" % (element, msg_either))
                    self.log.error(exc)
                    raise UserException(exc)
                if netmask is not None and prefix is not None:
                    exc = self.log.error("%s - %s" % (element, msg_both))
                    self.log.error(exc)
                    raise UserException(exc)

    def _validate_physical_interfaces(self):
        """ Validate that;
        - no data switch ports are specified more than once
        - All physical interfaces reference valid interface definitions
        - All rename values are either 'true' or 'false'
        Exception:
            UserException if any of the above criteria fail
            in config.yml
        """

        log = logger.getlogger()
        global exc
        exc = ''

        def get_dupes(_list):
            found = []
            dupes = []
            for item in _list:
                if item in found:
                    dupes.append(item)
                else:
                    found.append(item)
            return dupes

        def validate_switch_defined(switch):
            global exc
            if switch not in sw_lbls:
                msg = ('\nSwitch "{}" in node template "{}" is not defined.'
                       '\nValid defined switches are: {}\n').format(
                    switch, ntmpl_lbl, sw_lbls)
                exc += msg

        def validate_interface_defined(phy_ifc_lbl):
            global exc
            if phy_ifc_lbl not in ifc_lbls:
                msg = ('\nPhysical interface "{}" in node template "{}" '
                       '\nreferences an undefined interface.')
                exc += msg.format(phy_ifc_lbl, ntmpl_lbl)
                exc += '\nValid labels are: {}\n'.format(ifc_lbls)

        def _add_ports_to_ports_list(switch, ports):
            if switch in ports_list:
                ports_list[switch] += ports
            else:
                ports_list[switch] = ports

        ifcs = self.cfg.get_interfaces()
        ifc_lbls = []
        for ifc in ifcs:
            ifc_lbls.append(ifc['label'])

        sw_lbls = self.cfg.get_sw_mgmt_label()
        sw_lbls += self.cfg.get_sw_data_label()

        ports_list = {}
        for ntmpl_ind in self.cfg.yield_ntmpl_ind():
            ntmpl_lbl = self.cfg.get_ntmpl_label(ntmpl_ind)
            for phyintf_idx in self.cfg.yield_ntmpl_phyintf_data_ind(ntmpl_ind):
                phy_ifc_lbl = self.cfg.get_ntmpl_phyintf_data_ifc(
                    ntmpl_ind, phyintf_idx)
                validate_interface_defined(phy_ifc_lbl)
                rename = self.cfg.get_ntmpl_phyintf_data_rename(ntmpl_ind, phyintf_idx)
                if rename is not True and rename is not False:
                    msg = ('\nInvalid value for "rename:" ({}) in node template '
                           '"{}", \nphysical interface "{}"').format(
                        rename, ntmpl_lbl, phy_ifc_lbl)
                    msg += '\nValid values are "true" or "false"\n'
                    exc += msg
                switch = self.cfg.get_ntmpl_phyintf_data_switch(
                    ntmpl_ind, phyintf_idx)
                validate_switch_defined(switch)
                ports = self.cfg.get_ntmpl_phyintf_data_ports(
                    ntmpl_ind, phyintf_idx)
                _add_ports_to_ports_list(switch, ports)

            for phyintf_idx in self.cfg.yield_ntmpl_phyintf_pxe_ind(ntmpl_ind):
                phy_ifc_lbl = self.cfg.get_ntmpl_phyintf_pxe_interface(
                    ntmpl_ind, phyintf_idx)
                validate_interface_defined(phy_ifc_lbl)
                rename = self.cfg.get_ntmpl_phyintf_data_rename(ntmpl_ind, phyintf_idx)
                if rename is not True and rename is not False:
                    msg = ('\nInvalid value for "rename:" ({}) in node template '
                           '"{}", \nphysical interface "{}"').format(
                        rename, ntmpl_lbl, phy_ifc_lbl)
                    msg += '\nValid values are "true" or "false"\n'
                    exc += msg
                switch = self.cfg.get_ntmpl_phyintf_pxe_switch(
                    ntmpl_ind, phyintf_idx)
                validate_switch_defined(switch)
                ports = self.cfg.get_ntmpl_phyintf_pxe_ports(
                    ntmpl_ind, phyintf_idx)
                _add_ports_to_ports_list(switch, ports)

            for phyintf_idx in self.cfg.yield_ntmpl_phyintf_ipmi_ind(ntmpl_ind):
                switch = self.cfg.get_ntmpl_phyintf_ipmi_switch(
                    ntmpl_ind, phyintf_idx)
                validate_switch_defined(switch)
                ports = self.cfg.get_ntmpl_phyintf_ipmi_ports(
                    ntmpl_ind, phyintf_idx)
                _add_ports_to_ports_list(switch, ports)

        for switch in ports_list:
            dupes = get_dupes(ports_list[switch])
            if dupes:
                msg = ('\nDuplicate port(s) defined on switch "{}"'
                       '\nDuplicate ports: {}\n'.format(switch, dupes))
                exc += msg

        if exc:
            log.error('Config logic validation failed')
            raise UserException(exc)



    def validate_config_logic(self):
        """Config logic validation"""

        #from lib.config import Config
        #self.cfg = Config(self.config)

        self._validate_version()
        self._validate_netmask_prefix()
        self._validate_physical_interfaces()
