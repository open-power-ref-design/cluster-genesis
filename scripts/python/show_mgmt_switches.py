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

import sys
import os.path
import subprocess
import readline
import netaddr

from lib.ssh import SSH, SSH_Exception
from lib.inventory import Inventory
from lib.logger import Logger

FILE_PATH = os.path.dirname(os.path.abspath(__file__))
ssh_log = FILE_PATH + '/gen_ssh.log'


def rlinput(prompt, prefill=''):
    readline.set_startup_hook(lambda: readline.insert_text(prefill))
    try:
        return input(prompt)
    finally:
        readline.set_startup_hook()


def main(log, inv_file):
    inv = Inventory(log, inv_file)
    print()
    mgmt_network_ext_cidr = None
    key_addr = None
    try:
        mgmt_network_port = inv.get_port_mgmt_network()
        userid = inv.get_userid_mgmt_switch()
        password = inv.get_password_mgmt_switch()
        mgmt_network_gen = inv.get_ipaddr_mgmt_network()
        mgmt_network_ext = inv.get_mgmt_switch_external_dev_ip()
        mgmt_network_ext_prefix = inv.get_mgmt_switch_external_prefix()
        mgmt_network_ext = mgmt_network_ext + '/' + mgmt_network_ext_prefix
        mgmt_network_ext = netaddr.IPNetwork(mgmt_network_ext)
        mgmt_network_ext_cidr = str(mgmt_network_ext.cidr)
    except KeyError:
        print('Switch access information not present in: {}'.format(inv_file))
        print('Cluster Genesis may be in "passive" mode')
    else:
        output = subprocess.check_output(['bash', '-c', 'ip route']
                                         ).decode("utf-8")
        if mgmt_network_ext_cidr in output:
            key_addr = 'addr_ext'
        elif mgmt_network_gen in output:
            key_addr = 'addr_gen'
        else:
            print('No route found using config file addresses')

    if key_addr:
        print('==============================')
        print('Defined switches: ')
        index = 1
        switches_m = {}
        for rack, ipv4 in inv.yield_mgmt_rack_ipv4():
            switches_m[index] = {'rack': rack, 'addr_gen': ipv4}
            index += 1

        index = 1
        for ipv4 in inv.yield_mgmt_switch_external_switch_ip():
            switches_m[index]['addr_ext'] = ipv4
            print(' ' + str(index) + ')  rack: ' +
                  switches_m[index]['rack'] + ',  external address: ' +
                  switches_m[index]['addr_ext'] + ',  Genesis address: ' +
                  switches_m[index]['addr_gen'])
            index += 1
        if not (len(switches_m) == 1):
            sw = get_int_input("\n\nSelect a switch: ", 1, len(switches_m))
        else:
            sw = 1
        addr = switches_m[sw][key_addr]
        print()

    else:
        # output = subprocess.check_output(['bash', '-c', 'ip route'])
        addr = '192.168.32.20/24'
        userid = 'admin'
        password = 'admin'
        while 1:
            addr = rlinput("Enter an address for the management switch: ", addr)
            mgmt_network_ext = netaddr.IPNetwork(addr)
            mgmt_network_ext_cidr = str(mgmt_network_ext.cidr)
            userid = rlinput("Enter a userid for the management switch: ", userid)
            password = rlinput("Enter a password for the management switch (last char = '.' to terminate): ", password)
            if password[-1:] == '.':
                sys.exit(0)
            output = subprocess.check_output(['bash', '-c', 'ip route']
                                             ).decode("utf-8")
            if mgmt_network_ext_cidr in output:
                addr = addr[:addr.find('/')]
                break

# the G8052 misbehaves & closes it's SSH connection
# after every paramiko 'exec_command', so using SSH
# with commands strung together

    ssh = SSH(log)
    cmd = 'show interface ip;show vlan;show interface port %s;' \
        % (str(mgmt_network_port))
    try:
        _, switch_info, _ = ssh.exec_cmd(
            addr,
            userid,
            password,
            cmd,
            ssh_log=ssh_log,
            look_for_keys=False)
    except SSH_Exception as exc:
        print('Failed to SSH to switch at {} using userid {} and password {}'
              .format(addr, userid, password))
        print(exc)
        sys.exit(1)
    print_lines(switch_info, ['Interface information:', 'IP4'])
    print('\n\nVLAN information: ')
    print_lines(switch_info, ['-  ------  -', ' VLAN '])
    print()
    print('Deployer port: ')
    print_lines(switch_info, ['Current port', 'VLANs'])
    print()


def print_lines(str, line_list):
    """Splits str at newline (\n) characters, then prints the lines which
    contain elements from line_list"""
    str = str.splitlines()
    index = 0
    for _ in range(len(str)):
        for substr in line_list:
            if (substr in str[index] or substr == '*'):
                print(str[index])
        index += 1


def get_int_input(prompt_str, minn, maxx):
    while 1:
        try:
            _input = int(input(prompt_str))
            if not (minn <= _input <= maxx):
                raise ValueError()
            else:
                break
        except ValueError:
            print("enter an integer between " +
                  str(minn) + ' and ' + str(maxx))
    return _input


if __name__ == '__main__':
    """Show status of the Cluster Genesis environment

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
        except:
            LOG.error('Invalid argument count')
            sys.exit(1)

    INV_FILE = sys.argv[1]
    LOG.set_level(sys.argv[2])

    main(LOG, INV_FILE)
