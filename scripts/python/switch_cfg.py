#!/usr/bin/env python3
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

import argparse
import sys
import re
import readline
from shutil import copyfile
import yaml

import lib.logger as logger
from lib.switch import SwitchFactory
from lib.switch_exception import SwitchException
from lib.genesis import GEN_PATH, Color


def rlinput(prompt, prefill=''):
    readline.set_startup_hook(lambda: readline.insert_text(prefill))
    try:
        return input(prompt)
    finally:
        readline.set_startup_hook()


def _get_available_interface(interfaces):
    intf = 0
    while intf < MAX_INTF:
        intf += 1
        match = re.search(
            r'^%d:\s+IP4\s+' % intf,
            interfaces,
            re.MULTILINE)
        if match:
            continue
        return intf


def print_dict(dict):
    if not dict:
        print('{}')
    for key in sorted(dict.keys()):
        print(key.ljust(10) + ' ' + str(dict[key]))
    print()


MAX_INTF = 128


def main(_class, host):
    """Allows for interactive test of switch methods as well as
    interactive display of switch information.  A config file
    is created for each switch class and entered values are
    remembered to allow for rapid rerunning of tests.
    Can be called from the command line with 0 arguments.
    """

    log = logger.getlogger()
    cfg_file_path = GEN_PATH + 'scripts/python/switch-cfg-{}.yml'
    try:
        cfg = yaml.full_load(open(cfg_file_path.format(_class)))
    except:
        print('Could not load file: ' + cfg_file_path.format(_class))
        print('Copying from template file')
        try:
            copyfile(GEN_PATH + 'scripts/python/switch-cfg-template.yml',
                     cfg_file_path.format(_class))
            cfg = yaml.full_load(open(cfg_file_path.format(_class)))
        except:
            print('Could not load file: ' + cfg_file_path.format(_class))
            sys.exit(1)

    try:
        test = cfg['test']
        vlan = cfg['vlan']
        vlans = cfg['vlans']
        ifc_addr = cfg['ifc_addr']
        ifc_netmask = cfg['ifc_netmask']
        port = cfg['port']
        ports = cfg['ports']
        switchport_mode = cfg['switchport_mode']
        mlag_ifc = cfg['mlag_ifc']
        lag_ifc = cfg['lag_ifc']
        operation = cfg['operation']
    except KeyError:
        test = '1'
        vlan = 20
        vlans = 20, 21
        ifc_addr = '192.168.32.20'
        ifc_netmask = '255.255.255.0'
        port = 1
        ports = 1, 2
        switchport_mode = 'access'
        mlag_ifc = 36
        lag_ifc = 1
        operation = 'ADD'

    sw = SwitchFactory.factory(_class, host, 'admin', 'admin', mode='active')
    # Get needed enumerations
    port_mode, allow_op = sw.get_enums()
    test = 1

    def show_menu():
        menu = {}
        menu[0.1] = 'Available tests (0 to exit) :\n'
        menu[1] = {'desc': 'Ping switch', 'func': '_ping_switch'}
        menu[2] = {'desc': 'Show MAC address table', 'func': '_show_macs'}
        menu[4] = {'desc': 'Show VLANs', 'func': '_show_vlans'}
        menu[3] = {'desc': 'show port information', 'func': '_show_ports'}
        menu[5] = {'desc': 'Create VLANs', 'func': '_create_vlans'}
        menu[6] = {'desc': 'Delete VLANs', 'func': '_delete_vlans'}
        menu[8] = {'desc': 'Is port in trunk mode', 'func': '_is_port_in_trunk_mode'}
        menu[9] = {'desc': 'Is port in access mode', 'func': '_is_port_in_access_mode'}
        menu[7] = {'desc': 'Set switchport mode', 'func': '_set_switchport_mode'}
        menu[10] = {'desc': 'Set allowed VLANs on port', 'func': '_set_allowed_vlans'}
        menu[11] = {'desc': 'Is VLAN(s) allowed on port', 'func': '_is_vlan_allowed'}
        menu[12] = {'desc': 'Show native / access VLAN', 'func': '_show_native_vlan'}
        menu[13] = {'desc': 'Set MTU on port', 'func': '_set_mtu'}
        menu[13.1] = '{}       Mgmt interface functions {}'.format(Color.bold, Color.endc)
        menu[14] = {'desc': 'Create an in-band interface', 'func': '_create_inband_ifc'}
        menu[15] = {'desc': 'Delete an in-band interface', 'func': '_delete_inband_ifc'}
        menu[16] = {'desc': 'show in-band interface(s)', 'func': '_show_inband_ifc'}
        menu[30.1] = '{}       Port channel functions  {}'.format(Color.bold, Color.endc)
        menu[31] = {'desc': 'Show port channels', 'func': '_show_port_channel_interfaces'}
        menu[32] = {'desc': 'Create port channel', 'func': '_create_port_channel_interface'}
        menu[33] = {'desc': 'Add ports to port channel', 'func': '_add_ports_to_port_channel'}
        menu[34] = {'desc': 'Delete port channel', 'func': '_delete_port_channel'}
        menu[35] = {'desc': 'Set port channel mode', 'func': '_set_port_channel_mode'}
        menu[36] = {'desc': 'Set allowed vlans on port channel',
                    'func': '_set_allowed_vlans_port_channel'}
        menu[40.1] = '{}       vPC / MLAG functions{}'.format(Color.bold, Color.endc)
        menu[41] = {'desc': 'Is MLAG configured on switch', 'func': '_is_mlag'}
        menu[42] = {'desc': 'Show MLAG interfaces', 'func': '_show_mlag_ifcs'}
        menu[43] = {'desc': 'Create MLAG interface', 'func': '_create_mlag_ifc'}
        menu[44] = {'desc': 'Delete MLAG interface', 'func': '_delete_mlag_ifc'}
        menu[45] = {'desc': 'Add ports to MLAG port channel', 'func':
                    '_add_ports_to_mlag_port_channel'}
        menu[46] = {'desc': 'Set allowed vlans on MLAG port channel',
                    'func': '_set_allowed_vlans_mlag_port_channel'}
        print('\n\n')
        for item in sorted(menu.keys()):
            if not isinstance(item, int):
                print(menu[item])
            elif isinstance(menu[item], dict):
                print(item, ' - ', menu[item]['desc'])
        return menu

    def _ping_switch(cfg):
        print('\nPinging switch at {}'.format(host))
        pingable = sw.is_pingable()
        if not pingable:
            print('Switch not responding to pings.')
        else:
            print('Switch {} is pingable: {} '.format(host, pingable))

    def _create_inband_ifc(cfg):
        print('\nTesting in-band interface creation')
        cfg['vlan'] = int(rlinput('Enter interface vlan: ', str(cfg['vlan'])))
        cfg['ifc_addr'] = rlinput('Enter interface address: ', cfg['ifc_addr'])
        cfg['ifc_netmask'] = rlinput('Enter interface netmask: ', cfg['ifc_netmask'])
        try:
            sw.configure_interface(cfg['ifc_addr'], cfg['ifc_netmask'], cfg['vlan'])
            print('Created interface vlan {}'.format(cfg['vlan']))
        except SwitchException as exc:
            print(exc)

    def _delete_inband_ifc(cfg):
        print('Testing remove interface')
        cfg['vlan'] = int(rlinput('Enter interface vlan: ', str(cfg['vlan'])))
        cfg['ifc_addr'] = rlinput('Enter interface address: ', cfg['ifc_addr'])
        cfg['ifc_netmask'] = rlinput('Enter interface netmask: ', cfg['ifc_netmask'])
        try:
            sw.remove_interface(cfg['vlan'], cfg['ifc_addr'], cfg['ifc_netmask'])
            print('Removed interface vlan {}'.format(cfg['vlan']))
        except SwitchException as exc:
            print(exc)

    def _show_inband_ifc(cfg):
        print('\nTesting show in-band interfaces')
        ifc = rlinput(
            'Enter interface # or vlan (leave blank to show all): ', '')
        format = rlinput('Enter format ("std" or leave blank ): ', 'std')
        if format == '':
            format = None
        ifcs = sw.show_interfaces(ifc, format=format)
        if format is None:
            print(ifcs)
        else:
            for ifc in ifcs:
                print(ifc)

    def _show_macs(cfg):
        print('Test show mac address table: ')
        format = rlinput(
            'Enter desired return format (std, dict or raw): ', 'std')
        macs = sw.show_mac_address_table(format=format)
        if format == 'raw':
            print(macs)
        elif format == 'dict' or format == 'std':
            print_dict(macs)

    def _show_ports(cfg):
        print('\nTesting show ports')
        format = rlinput('Enter format ("std" or "raw" ): ', 'std')
        ports = sw.show_ports(format=format)
        if format == 'raw':
            print(ports)
        else:
            print_dict(ports)

    def _show_vlans(cfg):
        print(sw.show_vlans())

    def _create_vlans(cfg):
        print('\nTest create vlan')
        cfg['vlan'] = int(rlinput('Enter vlan: ', str(cfg['vlan'])))
        try:
            sw.create_vlan(cfg['vlan'])
            print('Created vlan {}'.format(cfg['vlan']))
        except SwitchException as exc:
            print(exc)

    # Test delete vlan
    def _delete_vlans(cfg):
        print('\nTest deleting vlan')
        cfg['vlan'] = int(rlinput('Enter vlan: ', str(cfg['vlan'])))
        try:
            sw.delete_vlan(cfg['vlan'])
            print('Deleted vlan {}'.format(cfg['vlan']))
        except SwitchException as exc:
            print(exc)

    # Test is port in trunk mode
    def _is_port_in_trunk_mode(cfg):
        print('\nTesting is port in trunk mode')
        cfg['port'] = rlinput('Enter port #: ', str(cfg['port']))
        print(sw.is_port_in_trunk_mode(cfg['port']))

    # Test is port in access mode
    def _is_port_in_access_mode(cfg):
        print('\nTesting is port in access mode')
        cfg['port'] = rlinput('Enter port #: ', str(cfg['port']))
        print(sw.is_port_in_access_mode(cfg['port']))

    # Test set switchport mode
    def _set_switchport_mode(cfg):
        print('\nTesting set switchport mode')
        cfg['port'] = rlinput('Enter port #: ', str(cfg['port']))
        cfg['switchport_mode'] = rlinput('Enter switchport mode(TRUNK|HYBRID|'
                                         'ACCESS): ', cfg['switchport_mode'])
        if cfg['switchport_mode'] in ('TRUNK', 'HYBRID'):
            prompt = 'Enter native vlan / PVID (blank for None): '
        else:
            prompt = 'Enter access vlan (blank for default): '
        cfg['vlan'] = rlinput(prompt, str(cfg['vlan']))
        if cfg['vlan'] == '':
            cfg['vlan'] = None
        else:
            cfg['vlan'] = int(cfg['vlan'])
        try:
            sw.set_switchport_mode(cfg['port'], port_mode[cfg['switchport_mode']],
                                   cfg['vlan'])
            print('Set switchport mode to ' + cfg['switchport_mode'])
        except SwitchException as exc:
            print(exc)

    # Test set  vlans on trunk / hybrid port
    def _set_allowed_vlans(cfg):
        print('\nTest set vlans on port')
        cfg['operation'] = rlinput('Enter operation (ADD|ALL|EXCEPT|NONE|REMOVE): ',
                                   cfg['operation'])
        cfg['port'] = rlinput('Enter port #: ', str(cfg['port']))
        cfg['vlans'] = rlinput("Enter vlans (ex: '4' or '4,6' or '2-5'): ",
                               str(cfg['vlans']))
        try:
            sw.allowed_vlans_port(cfg['port'], allow_op[cfg['operation']],
                                  cfg['vlans'].split())
            print('{} vlans {} to port interface {}'.format(allow_op[cfg['operation']],
                  cfg['vlans'], cfg['port']))
        except SwitchException as exc:
            print(exc)

    # Test is/are vlan(s) allowed for trunk port
    def _is_vlan_allowed(cfg):
        print('\nTesting is vlan allowed for port')
        cfg['port'] = rlinput('Enter port #: ', str(cfg['port']))
        cfg['vlans'] = rlinput('Enter vlan(s): ', str(cfg['vlans']))
        print(sw.is_vlan_allowed_for_port(cfg['vlans'], cfg['port']))

    def _show_native_vlan(cfg):
        print('\nTesting show native vlan')
        cfg['port'] = rlinput('Enter port #: ', str(cfg['port']))
        print('Native vlan: {}'.format(sw.show_native_vlan(cfg['port'])))

    # Test set mtu for port
    def _set_mtu(cfg):
        print('\nSet port mtu')
        cfg['port'] = rlinput('Enter port #: ', str(cfg['port']))
        mtu = rlinput('Enter mtu (0 for default mtu): ', 0)
        print(sw.set_mtu_for_port(cfg['port'], mtu))

    # Test show port channel (LAG) interfaces summary
    def _show_port_channel_interfaces(cfg):
        print(sw.show_port_channel_interfaces())

    # Test create port channel (LAG) interface
    def _create_port_channel_interface(cfg):
        print('\nTest create port channel interface')
        cfg['lag_ifc'] = int(rlinput('Enter port channel #: ', str(cfg['lag_ifc'])))
        try:
            sw.create_lag_interface(cfg['lag_ifc'])
            print('Created port channel ifc {}'.format(cfg['lag_ifc']))
        except SwitchException as exc:
            print(exc)

    # Test set port channel mode
    def _set_port_channel_mode(cfg):
        print('\nTest set port channel mode')
        cfg['lag_ifc'] = rlinput('Enter port channel #: ', str(cfg['lag_ifc']))
        cfg['switchport_mode'] = rlinput('Enter switchport mode(trunk | access): ',
                                         cfg['switchport_mode'])
        try:
            sw.set_port_channel_mode(lag_ifc, port_mode[cfg['switchport_mode']])
        except SwitchException as exc:
            print(exc)

    # Test reserved
    def _add_ports_to_port_channel(cfg):
        cfg['lag_ifc'] = rlinput('Enter lag ifc #: ', str(cfg['lag_ifc']))
        cfg['ports'] = rlinput('Enter ports: ', str(cfg['ports']))
        ports = cfg['ports'].split()
        try:
            sw.add_ports_to_port_channel_ifc(ports, cfg['lag_ifc'])
            print('Added ports {} to lag interface {}'.format(cfg['ports'], cfg['lag_ifc']))
        except SwitchException as exc:
            print(exc)

    # Test set vlans on port channel (LAG)
    def _set_allowed_vlans_port_channel(cfg):
        print('\nTest set vlans on port channel')
        cfg['operation'] = rlinput('Enter operation (ADD|ALL|EXCEPT|NONE|REMOVE): ',
                                   cfg['operation'])
        cfg['lag_ifc'] = rlinput('Enter port channel ifc #: ', str(cfg['lag_ifc']))
        cfg['vlans'] = rlinput("Enter vlans (ex: '4' or '4 6' or '2-5'): ",
                               str(cfg['vlans']))
        try:
            sw.allowed_vlans_port_channel(cfg['lag_ifc'], allow_op[cfg['operation']],
                                          cfg['vlans'].split())
            print('{} vlans {} to port channel interface {}'.format(cfg['operation'],
                  cfg['vlans'], cfg['lag_ifc']))
        except SwitchException as exc:
            print(exc)

    # Test remove LAG interface
    def _delete_port_channel(cfg):
        print('\nTest remove LAG interface')
        cfg['lag_ifc'] = int(rlinput('Enter lag ifc #: ', str(cfg['lag_ifc'])))
        try:
            sw.remove_lag_interface(cfg['lag_ifc'])
            print('Deleted lag ifc {}'.format(cfg['lag_ifc']))
        except SwitchException as exc:
            print(exc)

    def _is_mlag(cfg):
        print(sw.is_mlag_configured())

    # Test show MLAG interfaces summary
    def _show_mlag_ifcs(cfg):
        print(sw.show_mlag_interfaces())

    # Test create MLAG interface (MLAG port channel)
    def _create_mlag_ifc(cfg):
        print('\nTest create MLAG interface')
        cfg['mlag_ifc'] = int(rlinput('Enter mlag ifc #: ', str(cfg['mlag_ifc'])))
        try:
            sw.create_mlag_interface(cfg['mlag_ifc'])
            print('Created mlag ifc {}'.format(cfg['mlag_ifc']))
        except SwitchException as exc:
            print(exc)

    def _add_ports_to_mlag_port_channel(cfg):
        cfg['lag_ifc'] = rlinput('Enter lag ifc #: ', str(cfg['lag_ifc']))
        cfg['ports'] = rlinput('Enter ports: ', str(cfg['ports']))
        ports = cfg['ports'].split()
        try:
            sw.bind_ports_to_mlag_interface(ports, cfg['lag_ifc'])
            print('Added ports {} to lag interface {}'.format(cfg['ports'], cfg['lag_ifc']))
        except SwitchException as exc:
            print(exc)

    def _set_allowed_vlans_mlag_port_channel(cfg):
        print('\nTest set vlans on port channel')
        cfg['operation'] = rlinput('Enter operation (ADD|ALL|EXCEPT|NONE|REMOVE): ',
                                   cfg['operation'])
        cfg['lag_ifc'] = rlinput('Enter port channel ifc #: ', str(cfg['lag_ifc']))
        cfg['vlans'] = rlinput("Enter vlans (ex: '4' or '4,6' or '2-5'): ",
                               str(cfg['vlans']))
        try:
            sw.allowed_vlans_mlag_port_channel(cfg['lag_ifc'], allow_op[cfg['operation']],
                                               cfg['vlans'].split())
            print('{} vlans {} to port channel interface {}'.format(cfg['operation'],
                  cfg['vlans'], cfg['lag_ifc']))
        except SwitchException as exc:
            print(exc)

    # Test remove MLAG interface
    def _delete_mlag_ifc(cfg):
        print('\nTest remove MLAG interface')
        cfg['mlag_ifc'] = int(rlinput('Enter mlag ifc #: ', str(cfg['mlag_ifc'])))
        try:
            sw.remove_mlag_interface(cfg['mlag_ifc'])
            print('Deleted mlag ifc {}'.format(cfg['mlag_ifc']))
        except SwitchException as exc:
            print(exc)

    # Test deconfigure MLAG interface
    def _deconfigure_mlag(cfg):
        try:
            sw.deconfigure_mlag()
        except SwitchException as exc:
            print(exc)

    test = ''
    while test != 0:
        if not test:
            menu = show_menu()
            test = rlinput('{}\nEnter a test to run: {}'.format(Color.blue, Color.endc), '')
        try:
            test = int(test)
        except ValueError:
            test = 99

        if test == 0:
            sys.exit(0)

        if test != 99:
            func_name = menu[test]['func']
            func_to_call = locals()[func_name]
            func_to_call(cfg)

            yaml.dump(cfg, open(cfg_file_path.format(_class), 'w'),
                      default_flow_style=False)
        test = rlinput('\nPress enter to continue or a test to run ', '')


if __name__ == '__main__':
    """Interactive test for switch methods
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('clas', choices=['cisco', 'mellanox', 'lenovo'],
                        help='switch class')
    parser.add_argument('host', help='Host name or ip address')
    parser.add_argument('--print', '-p', dest='log_lvl_print',
                        help='print log level', default='info')
    parser.add_argument('--file', '-f', dest='log_lvl_file',
                        help='file log level', default='info')
    args = parser.parse_args()

    logger.create(args.log_lvl_print, args.log_lvl_file)
    main(args.clas, args.host)
