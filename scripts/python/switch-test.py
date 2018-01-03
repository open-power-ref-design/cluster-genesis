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
import re
import readline
from shutil import copyfile
import yaml

# import lib.logger as logger
from lib.switch import SwitchFactory
from lib.switch_exception import SwitchException
from lib.genesis import GEN_PATH


def rlinput(prompt, prefill=''):
    readline.set_startup_hook(lambda: readline.insert_text(prefill))
    try:
        return raw_input(prompt)
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
    for key in dict.keys():
        print(key.ljust(10) + ' ' + str(dict[key]))
    print()


MAX_INTF = 128


def main():
    """Allows for interactive test of switch methods as well as
    interactive display of switch information.  A config file
    is created for each switch class and entered values are
    remembered to allow for rapid rerunning of tests.
    Can be called from the command line with 0 arguments.
    """

    # log = logger.getlogger()
    _class = rlinput('\nEnter switch class: ', '')
    cfg_file_path = GEN_PATH + 'scripts/python/switch-test-cfg-{}.yml'
    try:
        cfg = yaml.load(open(cfg_file_path.format(_class)))
    except:
        print('Could not load file: ' + cfg_file_path.format(_class))
        print('Copying from template file')
        try:
            copyfile(GEN_PATH + 'scripts/python/switch-test-cfg.template',
                     cfg_file_path.format(_class))
            cfg = yaml.load(open(cfg_file_path.format(_class)))
        except:
            print('Could not load file: ' + cfg_file_path.format(_class))
            sys.exit(1)
    test = cfg['test']
    host = cfg['host']
    vlan = cfg['vlan']
    vlans = cfg['vlans']
    ifc_addr = cfg['ifc_addr']
    ifc_netmask = cfg['ifc_netmask']
    port = cfg['port']
    switchport_mode = cfg['switchport_mode']
    mlag_ifc = cfg['mlag_ifc']
    lag_ifc = cfg['lag_ifc']

    host = rlinput('Enter host address: ', host)
    cfg['host'] = host

    try:
        with open(__file__, 'r') as f:
            text = f.read()
    except IOError as error:
        print('Unable to open file {}'.format(__file__))
        print(error)
        sys.exit(0)
    sw = SwitchFactory.factory(_class, host, 'admin', 'admin', mode='active')
    test = 1

    while test != 0:
        _text = text
        print('\nAvailable tests')
        _text = _text.split('# Test')
        for line in _text:
            match = re.search(r'if (\d+) == test', line)
            if match:
                print(match.group(1) + ' - ' + line.splitlines()[0])
        test = int(rlinput('\nEnter a test to run: (0 to exit) ', str(test)))
        cfg['test'] = test

        if 0 == test:
            sys.exit()

        # Test Is switch pingable
        if 1 == test:
            print('\nTesting if switch is pingable')
            pingable = sw.is_pingable()
            if not pingable:
                print('Can not communicate with switch.  Exiting.')
            else:
                print('Switch {} is pingable: {} '.format(host, pingable))

        # Test create an in-band management interface
        if 2 == test:
            print('\nTesting in-band interface creation')
            vlan = int(rlinput('Enter interface vlan: ', str(vlan)))
            cfg['vlan'] = vlan
            ifc_addr = rlinput('Enter interface address: ', ifc_addr)
            cfg['ifc_addr'] = ifc_addr
            ifc_netmask = rlinput('Enter interface netmask: ', ifc_netmask)
            cfg['ifc_netmask'] = ifc_netmask
            try:
                sw.configure_interface(ifc_addr, ifc_netmask, vlan)
                print('Created interface vlan {}'.format(vlan))
            except SwitchException as exc:
                print (exc)

        # Test remove interface
        if 3 == test:
            print('Testing remove interface')
            vlan = int(rlinput('Enter interface vlan: ', str(vlan)))
            cfg['vlan'] = vlan
            ifc_addr = rlinput('Enter interface address: ', ifc_addr)
            cfg['ifc_addr'] = ifc_addr
            ifc_netmask = rlinput('Enter interface netmask: ', ifc_netmask)
            cfg['ifc_netmask'] = ifc_netmask
            try:
                sw.remove_interface(vlan, ifc_addr, ifc_netmask)
                print('Removed interface vlan {}'.format(vlan))
            except SwitchException as exc:
                print(exc)

        # Test show in-band interfaces
        if 4 == test:
            print('\nTesting show in-band interfaces')
            ifc = rlinput(
                'Enter interface or vlan (leave blank to show all): ', '')
            format = rlinput('Enter format ("std" or leave blank ): ', 'std')
            if format == '':
                format = None
            ifcs = sw.show_interfaces(ifc, format=format)
            if format is None:
                print(ifcs)
            else:
                for ifc in ifcs:
                    print(ifc)

        # Test show mac address table
        if 5 == test:
            print('Test show mac address table: ')
            format = rlinput(
                'Enter desired return format (std, dict or raw): ', 'std')
            macs = sw.show_mac_address_table(format=format)
            if format == 'raw':
                print(macs)
            elif format == 'dict' or format == 'std':
                print_dict(macs)

        # Test show vlans
        if 6 == test:
            print(sw.show_vlans())

        # Test create vlan
        if 7 == test:
            print('\nTest create vlan')
            vlan = int(rlinput('Enter vlan: ', str(vlan)))
            cfg['vlan'] = vlan
            try:
                sw.create_vlan(vlan)
                print('Created vlan {}'.format(vlan))
            except SwitchException as exc:
                print(exc)

        # Test delete vlan
        if 8 == test:
            print('\nTest deleting vlan')
            vlan = int(rlinput('Enter vlan: ', str(vlan)))
            cfg['vlan'] = vlan
            try:
                sw.delete_vlan(vlan)
                print('Deleted vlan {}'.format(vlan))
            except SwitchException as exc:
                print(exc)

        # Test is port in trunk mode
        if 9 == test:
            print('\nTesting is port in trunk mode')
            port = int(rlinput('Enter port #: ', str(port)))
            cfg['port'] = port
            print(sw.is_port_in_trunk_mode(port))

        # Test is port in access mode
        if 10 == test:
            print('\nTesting is port in access mode')
            port = int(rlinput('Enter port #: ', str(port)))
            cfg['port'] = port
            print(sw.is_port_in_access_mode(port))

        # Test set switchport mode
        if 11 == test:
            print('\nTesting set switchport mode')
            port = int(rlinput('Enter port #: ', str(port)))
            cfg['port'] = port
            vlan = rlinput('Enter vlan (blank for None): ', str(vlan))
            if vlan == '':
                vlan = None
            else:
                cfg['vlan'] = int(vlan)
            switchport_mode = rlinput('Enter switchport mode: ', switchport_mode)
            cfg['switchport_mode'] = switchport_mode
            try:
                sw.set_switchport_mode(switchport_mode, port, vlan)
                print('Set switchport mode to ' + switchport_mode)
            except SwitchException as exc:
                print(exc)

        # Test add vlans to port
        if 12 == test:
            print('\nTesting add vlans to port')
            port = int(rlinput('Enter port #: ', str(port)))
            cfg['port'] = port
            vlans = rlinput('Enter vlan list: ', vlans)
            cfg['vlans'] = vlans
            try:
                sw.add_vlans_to_port(port, vlans)
            except SwitchException as exc:
                print(exc)

        # Test remove vlans from port
        if 13 == test:
            print('\nTesting remove vlans from port')
            port = int(rlinput('Enter port #: ', str(port)))
            cfg['port'] = port
            vlans = rlinput('Enter vlan list: ', vlans)
            cfg['vlans'] = vlans
            try:
                sw.remove_vlans_from_port(port, vlans)
            except SwitchException as exc:
                print(exc)

        # Test is vlan allowed for port
        if 14 == test:
            print('\nTesting is vlan allowed for port')
            port = int(rlinput('Enter port #: ', str(port)))
            cfg['port'] = port
            vlan = int(rlinput('Enter vlan: ', str(vlan)))
            cfg['vlan'] = vlan
            print(sw.is_vlan_allowed_for_port(vlan, port))

        # Test show ports
        if 15 == test:
            print('\nTesting show ports')
            format = rlinput('Enter format ("std" or leave blank ): ', 'std')
            if format == '':
                format = None
            ports = sw.show_ports(format=format)
            if format is None:
                print(ports)
            else:
                print_dict(ports)

        # Test show native vlan
        if 16 == test:
            print('\nTesting show native vlan')
            port = int(rlinput('Enter port #: ', str(port)))
            cfg['port'] = port
            print('Native vlan: {}'.format(sw.show_native_vlan(port)))

        # Test set native vlan
        if 17 == test:
            print('\nSet native vlan')
            port = int(rlinput('Enter port #: ', str(port)))
            cfg['port'] = port
            vlan = rlinput('Enter vlan #: ', vlan)
            cfg['vlan'] = vlan
            try:
                sw.set_switchport_native_vlan(vlan, port)
                print('Set native vlan succesful')
            except SwitchException as exc:
                print(exc)

        # Test set mtu for port
        if 18 == test:
            print('\nSet port mtu')
            port = int(rlinput('Enter port #: ', str(port)))
            mtu = rlinput('Enter mtu (0 for default mtu): ', 0)
            print(sw.set_mtu_for_port(port, mtu))

        # Test show MLAG interfaces summary
        if 19 == test:
            print(sw.show_mlag_interfaces())

        # Test create MLAG interface (MLAG port channel)
        if 20 == test:
            print('\nTest create MLAG interface')
            mlag_ifc = int(rlinput('Enter mlag ifc #: ', str(mlag_ifc)))
            cfg['mlag_ifc'] = mlag_ifc
            try:
                sw.create_mlag_interface(mlag_ifc)
                print('Created mlag ifc {}'.format(mlag_ifc))
            except SwitchException as exc:
                print(exc)

        # Test remove MLAG interface
        if 21 == test:
            print('\nTest remove MLAG interface')
            mlag_ifc = int(rlinput('Enter mlag ifc #: ', str(mlag_ifc)))
            cfg['mlag_ifc'] = mlag_ifc
            try:
                sw.remove_mlag_interface(mlag_ifc)
                print('Deleted mlag ifc {}'.format(mlag_ifc))
            except SwitchException as exc:
                print(exc)

        # Test deconfigure MLAG interface
        if 22 == test:
            try:
                sw.deconfigure_mlag()
            except SwitchException as exc:
                print(exc)

        # Test show LAG interfaces summary
        if 23 == test:
            print(sw.show_lag_interfaces())

        # Test create LAG interface (LAG port channel)
        if 24 == test:
            print('\nTest create LAG interface')
            lag_ifc = int(rlinput('Enter lag ifc #: ', str(lag_ifc)))
            cfg['lag_ifc'] = lag_ifc
            try:
                sw.create_lag_interface(lag_ifc)
                print('Created lag ifc {}'.format(lag_ifc))
            except SwitchException as exc:
                print(exc)

        # Test remove LAG interface
        if 25 == test:
            print('\nTest remove LAG interface')
            lag_ifc = int(rlinput('Enter lag ifc #: ', str(lag_ifc)))
            cfg['lag_ifc'] = lag_ifc
            try:
                sw.remove_lag_interface(lag_ifc)
                print('Deleted lag ifc {}'.format(lag_ifc))
            except SwitchException as exc:
                print(exc)

        yaml.dump(cfg, open(cfg_file_path.format(_class), 'w'),
                  default_flow_style=False)
        test = rlinput('\nPress enter to continue, or enter a test to run ', '')
        if test:
            test = int(test)


if __name__ == '__main__':
    """Interactive test for switch methods
    """

    # logger.create()
    main()
