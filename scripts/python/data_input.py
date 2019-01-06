#!/usr/bin/env python
# Copyright 2017 IBM Corp.
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
import yaml
import code
import readline
import re

import lib.logger as logger
from lib.utilities import Color
from lib.genesis import get_gen_path, get_sample_configs_path

GEN_PATH = get_gen_path()
GEN_SAMPLE_CONFIGS_PATH = get_sample_configs_path()


def get_profile():
    c = Color()
    log = logger.getlogger()
    print(f'{c.blue}hello{c.endc}')
    #log.info('log this')
    try:
        profile = yaml.load(open(GEN_PATH + 'profile.yml'))
    except IOError:
        profile = yaml.load(open(GEN_SAMPLE_CONFIGS_PATH + 'profile-template.yml'))
#        profile = {}
#        profile['bmc_vlan'] = {}
#        profile['bmc_vlan']['val'] = '11'
#        profile['bmc_vlan']['desc'] = 'BMC subnet'
#        hlp = ('The BMC subnet is the subnet which contains the BMC ports of the\n'
#                'nodes to be installed. Note that if Power-Up is configured to use\n'
#                'DHCP for allocating BMC addresses, the entire subnet is assumed to\n'
#                'be available for use. BMC ports can reside in the same subnet as\n'
#                'PXE ports.')
#        profile['bmc_vlan']['help'] = hlp
#
#        profile['pxe_vlan'] = {}
#        profile['pxe_vlan']['val'] = '12'
#        profile['pxe_vlan']['desc'] = 'PXE VLAN'
#        hlp = ('The PXE subnet is the subnet which contains the PXE ports of the\n'
#                'nodes to be installed. Note that if Power-Up is configured to use\n'
#                'DHCP for allocating PXE addresses, the entire subnet is assumed to\n'
#                'be available for use. PXE ports can reside in the same subnet as\n'
#                'BMC ports')
#        profile['pxe_vlan']['help'] = hlp
#
#        profile['bmc_subnet'] = {}
#        profile['bmc_subnet']['val'] = '192.168.11.0/24'
#        profile['bmc_subnet']['desc'] = 'BMC subnet'
#        hlp = ('The PXE subnet is the subnet which contains the PXE ports of the\n'
#                'nodes to be installed. Note that if Power-Up is configured to use\n'
#                'DHCP for allocating PXE addresses, the entire subnet is assumed to\n'                        'be available for use. PXE ports can reside in the same subnet as\n'
#                'BMC ports')
#        profile['bmc_subnet']['help'] = hlp
#
#        profile['pxe_subnet'] = {}
#        profile['pxe_subnet']['val'] = '192.168.12.0/24'
#        profile['pxe_subnet']['desc'] = 'PXE subnet'
#        hlp = ('The PXE subnet is the subnet which contains the PXE ports of the\n'
#                'nodes to be installed. Note that if Power-Up is configured to use\n'
#                'DHCP for allocating PXE addresses, the entire subnet is assumed to\n'                        'be available for use. PXE ports can reside in the same subnet as\n'
#                'BMC ports')
#        profile['pxe_subnet']['help'] = hlp

    #print(profile)
    #finally:
    #    with open(GEN_PATH + 'profile.yml', 'w') as f:
    #        yaml.dump(profile, f, default_flow_style=False)
    return profile


def rlinput(prompt, prefill=''):
    readline.set_startup_hook(lambda: readline.insert_text(prefill))
    try:
        return input(prompt)
    finally:
        readline.set_startup_hook()


def input_data(data):
    pass

#    i = -1
#    while i < 0 or i > _max:
#        i = int(input(prompt))
#    return i

def get_data():

    def input_item(_max, prompt='Enter a number: '):
        while 1:
            item = input(prompt)
            #item = re.search(r'^\d{1,2} *-{1,2}[a-z]+', item)
            item = re.search(r'^(\d{1,2}) *(-{1,2}[a-z]+)*', item)
            if item:
                i = int(item.group(1))
                if i < 0 or i > _max:
                    print(c.up_one + c.sol + c.clr_to_eol, end='')
                    continue
                if item.group(2) in ('-h', '--help'):
                    opt = '-h'
                else:
                    opt = ''
                return i, opt

    def input_ipaddr(item):
        while 1:
            d = rlinput(f"{item['desc']}: ", str(item['val']))
            m = re.search(r'\A(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
                         '(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\Z', d)
            if m:
                return d

    def input_vlan(item):
        d = ''
        #code.interact(banner='input_pxe_vlan', local=dict(globals(), **locals()))
        while not isinstance(d, int) or not (d > 1 and d < 4095):
            d = rlinput(f"{item['desc']}: ", str(item['val']))
            try:
                if '-h' in d:
                    print(item['help'])
                else:
                    d = int(d.rstrip('-h'))
            except:
                pass
            else:
                if isinstance(d, int):
                    if d < 1 or d > 4094:
                        print('Enter an integer between 2 and 4094')
                        d = ''
        return d

#    def input_subnet(item):
#        while 1:
#            d = rlinput(f"{item['desc']}: ", str(item['val']))
#        return d

    def input_pxe_vlan(item):
        return input_vlan(item)

    def input_bmc_vlan(item):
        return input_vlan(item)

    def input_bmc_subnet(item):
        return input_ipaddr(item)

    def input_bmc_subnet_mask(item):
        return input_ipaddr(item)

    def input_pxe_subnet(item):
        return input_ipaddr(item)

    def input_pxe_subnet_mask(item):
        return input_ipaddr(item)

    def input_iso_image(item):
        return

    def input_ifc(item):
        d = rlinput(f"{item['desc']}: ", str(item['val']))
        return d

    c = Color()
    profile = get_profile()
    while 1:
        print(c.clrscr + c.home, end='')
        keys = sorted(profile.keys())
        print(c.bold + 'OS Installation parameters: ' + c.endc)
        for i, key in enumerate(keys):
            print(f" {i + 1}) {profile[key]['desc']: <20}: "
                  f"{c.reverse}{profile[key]['val']}{c.endc}")
        print('\nSelect an item to edit. 0 to quit')
        item, opt = input_item(len(keys), f'Enter a number (0-{len(keys)}). '
                               '(append -h for help) ')
        item -= 1
        if item == -1:
            break
        if opt == '-h':
            print(profile[keys[item]]['help'])
            input('Press enter to continue ')
            continue
        print(f'item: {item}')

        func_name = 'input_' + keys[item]
        func_to_call = locals()[func_name]
        #code.interact(banner='here', local=dict(globals(), **locals()))
        val = func_to_call(profile[keys[item]])
        profile[keys[item]]['val'] = val

        with open(GEN_PATH + 'profile.yml', 'w') as f:
            yaml.dump(profile, f, default_flow_style=False)

    with open(GEN_PATH + 'profile.yml', 'w') as f:
        yaml.dump(profile, f, default_flow_style=False)

if __name__ == '__main__':
    """Show status of the Cluster Genesis environment
    Args:
        INV_FILE (string): Inventory file.
        LOG_LEVEL (string): Log level.

    Raises:
       Exception: If parameter count is invalid.
    """

    logger.create('nolog', 'info')
    log = logger.getlogger()
    ARGV_MAX = 3
    ARGV_COUNT = len(sys.argv)
    if ARGV_COUNT > ARGV_MAX:
        try:
            raise Exception()
        except:
            log.error('Invalid argument count')
            sys.exit('Invalid argument count')

    get_data()
