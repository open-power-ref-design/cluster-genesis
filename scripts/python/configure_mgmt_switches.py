#!/usr/bin/env python
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

import lib.logger as logger
from lib.config import Config
from lib.switch import SwitchFactory
from lib.switch_exception import SwitchException
from lib.exception import UserCriticalException
# from write_switch_memory import WriteSwitchMemory

ACTIVE = 'active'
PASSIVE = 'passive'


def configure_mgmt_switches():

    LOG = logger.getlogger()
    cfg = Config()
    LOG.debug('------------------- configure_mgmt_switches -------------------')

    for index, switch_label in enumerate(cfg.yield_sw_mgmt_label()):
        mode = ACTIVE

        label = cfg.get_sw_mgmt_label(index)
        LOG.info('Configuring switch: {}'.format(switch_label))

        switch_class = cfg.get_sw_mgmt_class(index)
        if not switch_class:
            LOG.error('Unrecognized switch class')
            raise UserCriticalException('Unrecognized switch class')
        userid = None
        password = None
        switch_ip = None

        if cfg.is_passive_mgmt_switches():
            mode = PASSIVE

        try:
            userid = cfg.get_sw_mgmt_userid(index)
        except AttributeError:
            pass

        try:
            password = cfg.get_sw_mgmt_password(index)
        except AttributeError:
            try:
                cfg.get_sw_mgmt_ssh_key(index)
            except AttributeError:
                pass
            else:
                LOG.error(
                    'Switch authentication via ssh keys not yet supported')
                raise UserCriticalException(
                    'Switch authentication via ssh keys not yet supported')

        if mode == PASSIVE:
                sw = SwitchFactory.factory(
                    switch_class,
                    mode)

        elif mode == ACTIVE:
            # Try all ipaddrs in switches.interfaces
            for ip in cfg.yield_sw_mgmt_interfaces_ip(index):
                sw = SwitchFactory.factory(
                    switch_class,
                    ip,
                    userid,
                    password)

                if sw.is_pingable():
                    LOG.debug(
                        'Sucessfully pinged management switch \"%s\" at %s' %
                        (label, ip))
                    switch_ip = ip
                    break

                LOG.debug(
                    'Failed to ping management switch \"%s\" at %s' %
                    (label, ip))

            else:
                LOG.error('Management switch is not responding to pings')
                raise UserCriticalException(
                    'Management switch at address {} is not responding to '
                    'pings'.format(ip))

        LOG.debug(
            '%d: \"%s\" (%s) %s %s/%s' %
            (index, switch_label, mode, switch_ip, userid, password))

        vlan_mgmt = cfg.get_depl_netw_mgmt_vlan()
        vlan_mgmt = [x for x in vlan_mgmt if x is not None]
        LOG.debug('Management vlans: {}'.format(vlan_mgmt))

        vlan_client = cfg.get_depl_netw_client_vlan()

        for vlan in vlan_mgmt + vlan_client:
            if vlan:
                print('.', end="")
                sys.stdout.flush()
                sw.create_vlan(vlan)

        for intf_i, ip in enumerate(cfg.yield_sw_mgmt_interfaces_ip(index)):
            if ip != switch_ip:
                vlan = cfg.get_sw_mgmt_interfaces_vlan(index, intf_i)
                if vlan is None:
                    vlan = vlan_mgmt[0]
                netmask = cfg.get_sw_mgmt_interfaces_netmask(index, intf_i)

                try:
                    LOG.debug(
                        "Configuring mgmt switch \"%s\" inband interface. "
                        "(ip=%s netmask=%s vlan=%s)" %
                        (label, ip, netmask, vlan))
                    # sw.configure_interface(ip, netmask, vlan, port)
                    sw.configure_interface(ip, netmask, vlan)
                except SwitchException as exc:
                    LOG.warning(exc)

        for target_i, target in (
                enumerate(cfg.yield_sw_mgmt_links_target(index))):
            port = cfg.get_sw_mgmt_links_port(index, target_i)
            if target.lower() == 'deployer':
                try:
                    print('.', end="")
                    sys.stdout.flush()
                    vlans = vlan_mgmt + vlan_client
                    LOG.debug('Adding vlans {} to port {}'.format(vlans, port))
                    sw.add_vlans_to_port(port, vlans)
                except SwitchException as exc:
                    LOG.error(exc)
            else:
                vlan = cfg.get_sw_mgmt_links_vlan(index, target_i)
                if vlan is None:
                    if not vlan_mgmt:
                        vlan = 1
                    else:
                        vlan = vlan_mgmt[0]
                try:
                    sw.set_switchport_native_vlan(vlan, port)
                except SwitchException as exc:
                    LOG.error(exc)

        for if_type in ['ipmi', 'pxe']:
            vlan = cfg.get_depl_netw_client_vlan(if_type=if_type)[0]

            for port in cfg.yield_client_switch_ports(switch_label, if_type):
                if mode == 'passive' or sw.is_port_in_access_mode(port):
                    LOG.debug('Port %s is already in access mode' % (port))
                else:
                    LOG.error('Port %s is not in access mode' % (port))
                    raise UserCriticalException('Port %s is not in access mode'
                                                % (port))

                if vlan == sw.show_native_vlan(port):
                    LOG.debug(
                        'Management VLAN %s is already added to access port %s'
                        % (vlan, port))
                else:
                    print('.', end="")
                    sys.stdout.flush()
                    sw.set_switchport_native_vlan(vlan, port)

        # write switch memory?
        # if cfg.is_write_switch_memory():
        #     switch_mem = WriteSwitchMemory(log, INV_FILE)
        #     switch_mem.write_mgmt_switch_memory()


if __name__ == '__main__':
    logger.create()
    configure_mgmt_switches()
