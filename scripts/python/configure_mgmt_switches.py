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

import argparse
import os.path
import sys

import lib.logger as logger
from lib.config import Config
from lib.switch import SwitchFactory
from lib.switch_exception import SwitchException
from lib.exception import UserCriticalException
from lib.genesis import GEN_PATH
# from write_switch_memory import WriteSwitchMemory

ACTIVE = 'active'
PASSIVE = 'passive'


def configure_mgmt_switches(config_file=None):

    LOG = logger.getlogger()
    cfg = Config(config_file)
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
                # Get the enumerations needed to call set_switchport_mode() and
                # allowed_vlans_port()
                port_mode, allow_op = sw.get_enums()

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
        LOG.debug('vlan_mgmt: {} , vlan_client: {}'.format(vlan_mgmt, vlan_client))
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
                    sw.set_switchport_mode(port, port_mode.TRUNK)
                except SwitchException as exc:
                    LOG.error(exc)
                try:
                    sw.allowed_vlans_port(port, allow_op.ADD, vlans)
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
                    sw.set_switchport_mode(port, port_mode.TRUNK)
                    sw.allowed_vlans_port(port, allow_op.NONE)
                    sw.allowed_vlans_port(port, allow_op.ADD, vlan)
                    sw.set_switchport_mode(port, port_mode.TRUNK, vlan)
                except SwitchException as exc:
                    LOG.error(exc)
        for if_type in ['ipmi', 'pxe']:
            vlan = cfg.get_depl_netw_client_vlan(if_type=if_type)[0]

            for port in cfg.yield_client_switch_ports(switch_label, if_type):
                if mode == 'passive':
                    LOG.debug('Set switchport mode - switch is in passive mode.')
                else:
                    print('.', end="")
                    sys.stdout.flush()
                    try:
                        LOG.debug('Setting port {} into {} mode with access '
                                  'vlan {}'.format(port, port_mode.ACCESS, vlan))
                        sw.set_switchport_mode(port, port_mode.ACCESS, vlan)
                    except SwitchException as exc:
                        LOG.error(exc)

        # write switch memory?
        # if cfg.is_write_switch_memory():
        #     switch_mem = WriteSwitchMemory(log, INV_FILE)
        #     switch_mem.write_mgmt_switch_memory()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('config_path', default='config.yml',
                        help='Config file path.  Absolute path or relative '
                        'to power-up/')

    parser.add_argument('--print', '-p', dest='log_lvl_print',
                        help='print log level', default='info')

    parser.add_argument('--file', '-f', dest='log_lvl_file',
                        help='file log level', default='info')

    args = parser.parse_args()

    if not os.path.isfile(args.config_path):
        args.config_path = GEN_PATH + args.config_path
        print('Using config path: {}'.format(args.config_path))
    if not os.path.isfile(args.config_path):
        sys.exit('{} does not exist'.format(args.config_path))

    logger.create(args.log_lvl_print, args.log_lvl_file)
    configure_mgmt_switches(args.config_path)
