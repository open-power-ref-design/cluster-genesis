#!/usr/bin/env python
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
import curses
import npyscreen
import os.path
import yaml
from orderedattrdict.yamlutils import AttrDictYAMLLoader
from collections import namedtuple
from pyroute2 import IPRoute
import sys
from time import sleep
import code

import lib.logger as logger
import lib.interfaces as interfaces
from lib.genesis import get_package_path, get_sample_configs_path
import lib.utilities as u

GEN_PATH = get_package_path()
GEN_SAMPLE_CONFIGS_PATH = get_sample_configs_path()

IPR = IPRoute()

PROFILE = 'profile.yml'


def osinstall(profile_path):
    log = logger.getlogger()
    log.debug('osinstall')
    osi = OSinstall(profile_path)
    osi.run()

#    osi.config_interfaces()
#    validate(p)


class Profile():
    def __init__(self, prof_path='profile-template.yml'):
        self.log = logger.getlogger()
        if prof_path == 'profile-template.yml':
            self.prof_path = os.path.join(GEN_SAMPLE_CONFIGS_PATH,
                                          'profile-template.yml')
        else:
            if not os.path.dirname(prof_path):
                self.prof_path = os.path.join(GEN_PATH, prof_path)
            else:
                self.prof_path = prof_path
            if not os.path.isfile(self.prof_path):
                self.log.info('No profile file found.  Using template.')
                sleep(1)
                self.prof_path = os.path.join(GEN_SAMPLE_CONFIGS_PATH,
                                              'profile-template.yml')
        try:
            self.profile = yaml.load(open(self.prof_path), Loader=AttrDictYAMLLoader)
        except IOError:
            self.log.error(f'Unable to open the profile file: {self.prof_path}')
            sys.exit(f'Unable to open the profile file: {self.prof_path}\n'
                     'Unable to continue with OS install')

    def get_profile(self):
        """Returns an ordered attribute dictionary with the profile data.
        This is generally intended for use by the entry menu, not by application
        code
        """
        return self.profile

    def get_network_profile(self):
        """Returns an ordered attribute dictionary with the network profile data.
        This is generally intended for use by the entry menu, not by application
        code
        """
        return self.profile.network

    def get_network_profile_tuple(self):
        """Returns a named tuple constucted from the network profile data
        OS install code should generally use this method to get the network
        profile data.
        """
        p = self.get_network_profile()
        _list = []
        vals = ()
        for item in p:
            #code.interact(banner='get profile', local=dict(globals(), **locals()))
            if 'subnet_prefix' in item:
                # split the subnet prefix field into netmask and prefix
                _list.append(item)
                _list.append(item.replace('_prefix', '_mask'))
                vals += (p[item].val.split()[1],)
                vals += (p[item].val.split()[0],)
            else:
                _list.append(item)
                vals += (p[item].val,)
        _list.append('bmc_subnet_cidr')
        vals += (p.bmc_subnet.val + '/' + p.bmc_subnet_prefix.val.split()[1],)
        _list.append('pxe_subnet_cidr')
        vals += (p.pxe_subnet.val + '/' + p.pxe_subnet_prefix.val.split()[1],)

        proftup = namedtuple('ProfTup', _list)
        return proftup._make(vals)

    def update_network_profile(self, profile):
        self.profile.network = profile
        with open(GEN_PATH + 'profile.yml', 'w') as f:
            yaml.dump(self.profile, f, indent=4, default_flow_style=False)

    def get_node_profile(self):
        """Returns an ordered attribute dictionary with the network profile data.
        This is generally intended for use by the entry menu, not by application
        code
        """
        return self.profile.node

    def get_node_profile_tuple(self):
        """Returns a named tuple constucted from the network profile data
        OS install code should generally use this method to get the network
        profile data.
        """
        n = self.get_node_profile()
        _list = []
        vals = ()
        for item in n:
            _list.append(item)
            vals += (n[item].val,)

            #code.interact(banner='get profile', local=dict(globals(), **locals()))
#            if 'subnet_prefix' in item:
#                # split the subnet prefix field into netmask and prefix
#                _list.append(item)
#                _list.append(item.replace('_prefix', '_mask'))
#                vals += (p[item].val.split()[1],)
#                vals += (p[item].val.split()[0],)
#            else:
#                _list.append(item)
#                vals += (p[item].val,)

#        _list.append('bmc_subnet_cidr')
#        vals += (p.bmc_subnet.val + '/' + p.bmc_subnet_prefix.val.split()[1],)
#        _list.append('pxe_subnet_cidr')
#        vals += (p.pxe_subnet.val + '/' + p.pxe_subnet_prefix.val.split()[1],)

        proftup = namedtuple('ProfTup', _list)
        return proftup._make(vals)

    def update_node_profile(self, profile):
        self.profile.node = profile
        with open(GEN_PATH + 'profile.yml', 'w') as f:
            yaml.dump(self.profile, f, indent=4, default_flow_style=False)


class OSinstall(npyscreen.NPSAppManaged):
    def __init__(self, prof_path, *args, **kwargs):
        super(OSinstall, self).__init__(*args, **kwargs)
        self.prof_path = prof_path
        self.prof = Profile(self.prof_path)
        self.log = logger.getlogger()
        # create an Interfaces instance
        self.ifcs = interfaces.Interfaces()
        self.NODE_FORM = False

    def onStart(self):
        self.addForm('MAIN', Network_form, name='Welcome to PowerUP    '
                     'Press F1 for field help', lines=24)

        self.addForm('NODE', Node_form, name='Welcome to PowerUP    '
                     'Press F1 for field help')

    def is_valid_profile(self, prof):
        """ Validates the content of the profile data.
        Returns:
            msg (str) empty if passed, else contains warning and error msg
        """
        msg = ''
        #code.interact(banner='here', local=dict(globals(), **locals()))
        if hasattr(prof, 'bmc_userid'):
            return msg
        # Since the user can skip fields by mouse clicking 'OK'
        # We need additional checking here:
        #  Need to add checks of iso file (check extension)
        #  Check for valid up interfaces
        bmc_subnet_prefix = prof['bmc_subnet_prefix']['val'].split()[1]
        bmc_cidr = prof['bmc_subnet']['val'] + '/' + bmc_subnet_prefix
        pxe_subnet_prefix = prof['pxe_subnet_prefix']['val'].split()[1]
        pxe_cidr = prof['pxe_subnet']['val'] + '/' + pxe_subnet_prefix

        iso_image_file = prof['iso_image_file']['val']
        pxe_ethernet_ifc = prof['pxe_ethernet_ifc']['val']
        bmc_ethernet_ifc = prof['bmc_ethernet_ifc']['val']

        ifc = self.ifcs.is_route_overlapping(pxe_cidr, pxe_ethernet_ifc)
        if ifc:
            msg += ('Warning, the subnet specified on the PXE interface\n'
                    f'overlaps a subnet on interface {ifc}\n')

        ifc = self.ifcs.is_route_overlapping(bmc_cidr, bmc_ethernet_ifc)
        if ifc:
            msg += ('Warning, the subnet specified on the BMC interface\n'
                    f'overlaps a subnet on interface {ifc}\n')

        if u.is_overlapping_addr(bmc_cidr, pxe_cidr):
            msg += 'Warning, BMC and PXE subnets are overlapping\n'

        if bmc_subnet_prefix != pxe_subnet_prefix:
            msg += 'Warning, BMC and PXE subnets are different sizes\n'

        if not os.path.isfile(iso_image_file):
            msg += ("Error. Operating system ISO image file not found: \n"
                    f"{prof['iso_image_file']['val']}")

        return msg

    def config_interfaces(self):
        p = self.prof.get_profile_tuple()
        bmc_ifc = p.bmc_ethernet_ifc
        pxe_ifc = p.pxe_ethernet_ifc

        # create tagged vlan interfaces if any
        if p.bmc_vlan_number:
            bmc_ifc = p.bmc_ethernet_ifc + '.' + p.bmc_vlan_number
            if not self.ifcs.is_vlan_used_elsewhere(p.bmc_vlan_number, bmc_ifc):
                self.ifcs.create_tagged_ifc(p.bmc_ethernet_ifc, p.bmc_vlan_number)

        if p.pxe_vlan_number:
            pxe_ifc = p.pxe_ethernet_ifc + '.' + p.pxe_vlan_number
            if not self.ifcs.is_vlan_used_elsewhere(p.pxe_vlan_number, pxe_ifc):
                self.ifcs.create_tagged_ifc(p.pxe_ethernet_ifc, p.pxe_vlan_number)

        if not self.ifcs.find_unused_addr_and_add_to_ifc(bmc_ifc, p.bmc_subnet_cidr):
            self.log.error(f'Failed to add an addr to {bmc_ifc}')

        if not self.ifcs.find_unused_addr_and_add_to_ifc(pxe_ifc, p.pxe_subnet_cidr):
            self.log.error(f'Failed to add an addr to {pxe_ifc}')

#            cmd = f'nmap -PR {p.bmc_subnet_cidr}'
#            res, err, rc = u.sub_proc_exec(cmd)
#            if rc != 0:
#                self.log.error('An error occurred while scanning the BMC subnet')
#            bmc_addr_dict = {}
#            res = res.split('Nmap scan report')
#            for item in res:
#                ip = re.search(r'\d+\.\d+\.\d+\.\d+', item, re.DOTALL)
#                if ip:
#                    mac = re.search(r'((\w+:){5}\w+)', item, re.DOTALL)
#                    if mac:
#                        bmc_addr_dict[ip.group(0)] = mac.group(1)
#                    else:
#                        bmc_addr_dict[ip.group(0)] = ''
#            #code.interact(banner='There', local=dict(globals(), **locals()))
#            # Remove the temp route
#            res = self.ifcs.route('del', dst=p.bmc_subnet_cidr,
#                            oif=self.ifcs.link_lookup(ifname=bmc_ifc)[0])
#            if res[0]['header']['error']:
#                self.log.error(f'Error occurred removing route from {bmc_ifc}')


class Network_form(npyscreen.ActionFormV2):
    def afterEditing(self):
        self.parentApp.setNextForm(self.next_form)

    def on_cancel(self):
        res = npyscreen.notify_yes_no('Quit without saving?', title='cancel 1',
                                      editw=1)
        if res and self.parentApp.NODE_FORM:
            self.next_form = 'NODE'
        elif res:
            self.next_form = None
        else:
            self.next_form = 'MAIN'

    def on_ok(self):
        for item in self.prof:
            if hasattr(self.prof[item], 'ftype'):
                if self.prof[item]['ftype'] == 'eth-ifc':
                    self.prof[item]['val'] = self.fields[item].values[self.fields[item].value]
                elif self.prof[item]['ftype'] == 'select-one':
                    self.prof[item]['val'] = \
                        self.prof[item]['values'][self.fields[item].value[0]]
                else:
                    if self.fields[item].value == 'None':
                        self.prof[item]['val'] = None
                    else:
                        self.prof[item]['val'] = self.fields[item].value
            else:
                if self.fields[item].value == 'None':
                    self.prof[item]['val'] = None
                else:
                    self.prof[item]['val'] = self.fields[item].value

        msg = self.parentApp.is_valid_profile(self.prof)
        res = True
        if msg:
            if 'Error' in msg:
                npyscreen.notify_confirm(f'{msg}\n Please resolve issues.',
                                         title='cancel 1', editw=1)
                self.next_form = 'MAIN'
                res = False
            else:
                msg = (msg + '--------------------- \nBegin OS install?\n'
                       '(No to continue editing the profile data.)')
                res = npyscreen.notify_yes_no(msg, title='Profile validation', editw=1)

        if res:
            self.parentApp.prof.update_network_profile(self.prof)
            self.next_form = 'NODE'
        else:
            self.next_form = 'MAIN'

    def while_editing(self, instance):
        # instance is the instance of the widget you're moving into
        # map instance.name
        field = ''
        for item in self.prof:
            if instance.name == self.prof[item].desc:
                field = item
                break
        # On instantiation, self.prev_field is empty
        if self.prev_field:
            if hasattr(self.prof[self.prev_field], 'dtype'):
                prev_fld_dtype = self.prof[self.prev_field]['dtype']
            else:
                prev_fld_dtype = 'text'
            if hasattr(self.prof[self.prev_field], 'ftype'):
                prev_fld_ftype = self.prof[self.prev_field]['ftype']
            else:
                prev_fld_ftype = 'text'

            val = self.fields[self.prev_field].value

            if prev_fld_dtype == 'ipv4' or 'ipv4-' in prev_fld_dtype:
                if not u.is_ipaddr(val):
                    npyscreen.notify_confirm(f'Invalid Field value: {val}',
                                             title=self.prev_field, editw=1)
                else:
                    if 'ipv4-' in prev_fld_dtype:
                        mask_field = prev_fld_dtype.split('-')[-1]
                        prefix = int(self.fields[mask_field].value.split()[-1])
                        net_addr = u.get_network_addr(val, prefix)
                        if net_addr != val:
                            npyscreen.notify_confirm(f'IP addr modified to: {net_addr}',
                                                     title=self.prev_field, editw=1)
                            self.fields[self.prev_field].value = net_addr
                            self.display()

            elif prev_fld_dtype == 'ipv4mask':
                prefix = int(val.split()[-1])
                if prefix < 1 or prefix > 32:
                    npyscreen.notify_confirm(f'Invalid Field value: {val}',
                                             title=self.prev_field, editw=1)
                    prefix = 24
                if len(val.split()[-1]) == 2:
                    mask = u.get_netmask(prefix)
                    self.fields[self.prev_field].value = f'{mask} {prefix}'
                    self.display()

            elif 'int-or-none' in prev_fld_dtype:
                rng = self.prof[self.prev_field]['dtype'].lstrip('int-or-none').\
                    split('-')
                if val:
                    val = val.strip(' ')
                if val and val != 'None':
                    try:
                        int(val)
                    except ValueError:
                        npyscreen.notify_confirm(f"Enter digits 0-9 or enter 'None' "
                                                 "or leave blank",
                                                 title=self.prev_field, editw=1)
                    else:
                        if int(val) < int(rng[0]) or int(val) > int(rng[1]):
                            msg = (f'Invalid Field value: {val}. Please leave empty or '
                                   'enter a value between 2 and 4094.')
                            npyscreen.notify_confirm(msg, title=self.prev_field, editw=1)

            elif 'int' in prev_fld_dtype:
                rng = self.prof[self.prev_field]['dtype'].lstrip('int').split('-')
                if val:
                    try:
                        int(val)
                    except ValueError:
                        npyscreen.notify_confirm(f'Enter digits 0-9',
                                                 title=self.prev_field, editw=1)
                    else:
                        if int(val) < int(rng[0]) or int(val) > int(rng[1]):
                            msg = (f'Invalid Field value: {val}. Please enter a value '
                                   f'between 2 and 4094.')
                            npyscreen.notify_confirm(msg, title=self.prev_field, editw=1)

            elif 'file' in prev_fld_dtype:
                if not os.path.isfile(val):
                    npyscreen.notify_confirm(f'Specified iso file does not exist: {val}',
                                             title=self.prev_field, editw=1)
                elif '-iso' in prev_fld_dtype and '.iso' not in val:
                    npyscreen.notify_confirm('Warning, the selected file does not have a '
                                             '.iso extension',
                                             title=self.prev_field, editw=1)
            elif 'eth-ifc' in prev_fld_ftype:
                pass

        if field:
            self.prev_field = field
        else:
            self.prev_field = ''

        if instance.name not in ['OK', 'Cancel', 'CANCEL', 'Press me']:
            self.helpmsg = self.prof[field].help
        else:
            self.prev_field = ''

    def h_help(self, char):
        npyscreen.notify_confirm(self.helpmsg, title=self.prev_field, editw=1)

    def h_enter(self, char):
        npyscreen.notify_yes_no(f'Field Error: {self.field}', title='Enter', editw=1)

    def create(self):
        self.y, self.x = self.useable_space()
        self.prev_field = ''
        self.prof = self.parentApp.prof.get_network_profile()
        self.fields = {}  # dictionary for holding field instances

        for item in self.prof:
            fname = self.prof[item].desc
            if hasattr(self.prof[item], 'floc'):
                if self.prof[item]['floc'] == 'skipline':
                    self.nextrely += 1

                if 'sameline' in self.prof[item]['floc']:
                    relx = int(self.prof[item]['floc'].lstrip('sameline'))
                else:
                    relx = 2
            else:
                relx = 2
            # Place the field
            if hasattr(self.prof[item], 'ftype'):
                ftype = self.prof[item]['ftype']
            else:
                ftype = 'text'
            if hasattr(self.prof[item], 'dtype'):
                dtype = self.prof[item]['dtype']
            else:
                dtype = 'text'

            if ftype == 'file':
                if not self.prof[item]['val']:
                    self.prof[item]['val'] = os.path.join(GEN_PATH, 'os-images')
                self.fields[item] = self.add(npyscreen.TitleFilenameCombo,
                                             name=fname,
                                             value=str(self.prof[item]['val']),
                                             begin_entry_at=20)

            elif 'ipv4mask' in dtype:
                self.fields[item] = self.add(npyscreen.TitleText, name=fname,
                                             value=str(self.prof[item]['val']),
                                             begin_entry_at=20, width=40,
                                             relx=relx)
            elif 'eth-ifc' in ftype:
                eth = self.prof[item]['val']
                eth_lst = self.parentApp.ifcs.get_up_interfaces_names(_type='phys')
                # Get the existing value to the top of the list
                if eth in eth_lst:
                    eth_lst.remove(eth)
                eth_lst = [eth] + eth_lst if eth else eth_lst
                self.fields[item] = self.add(npyscreen.TitleCombo,
                                             name=fname,
                                             value=0,
                                             values=eth_lst,
                                             begin_entry_at=20,
                                             scroll_exit=False)
            elif ftype == 'select-one':
                if hasattr(self.prof[item], 'val'):
                    value = self.prof[item]['values'].index(self.prof[item]['val'])
                else:
                    value = 0
                self.fields[item] = self.add(npyscreen.TitleSelectOne, name=fname,
                                             max_height=2,
                                             value=value,
                                             values=self.prof[item]['values'],
                                             scroll_exit=True,
                                             begin_entry_at=20, relx=relx)

            # no ftype specified therefore Title text
            else:
                self.fields[item] = self.add(npyscreen.TitleText,
                                             name=fname,
                                             value=str(self.prof[item]['val']),
                                             begin_entry_at=20, width=40,
                                             relx=relx)
            self.fields[item].entry_widget.add_handlers({curses.KEY_F1:
                                                        self.h_help})


class Node_form(npyscreen.ActionFormV2):
    def beforeEditing(self):
        # Set NODE_FORM so other forms can know that the node form was entered
        self.parentApp.NODE_FORM = True

    def afterEditing(self):
        self.parentApp.setNextForm(self.next_form)

    def on_cancel(self):
        res = npyscreen.notify_yes_no('Quit without saving?', title='cancel 1',
                                      editw=1)
        self.next_form = None if res else 'NODE'

    def on_ok(self):
        for item in self.node:
            if hasattr(self.node[item], 'ftype'):
                if self.node[item]['ftype'] == 'eth-ifc':
                    self.node[item]['val'] = self.fields[item].values[self.fields[item].value]
                elif self.node[item]['ftype'] == 'select-one':
                    self.node[item]['val'] = \
                        self.node[item]['values'][self.fields[item].value[0]]
                else:
                    if self.fields[item].value == 'None':
                        self.node[item]['val'] = None
                    else:
                        self.node[item]['val'] = self.fields[item].value
            else:
                if self.fields[item].value == 'None':
                    self.node[item]['val'] = None
                else:
                    self.node[item]['val'] = self.fields[item].value

        msg = self.parentApp.is_valid_profile(self.node)
        res = True
        if msg:
            if 'Error' in msg:
                npyscreen.notify_confirm(f'{msg}\n Please resolve issues.',
                                         title='cancel 1', editw=1)
                self.next_form = 'MAIN'
                res = False
            else:
                msg = (msg + '--------------------- \nBegin OS install?\n'
                       '(No to continue editing the profile data.)')
                res = npyscreen.notify_yes_no(msg, title='Profile validation', editw=1)

        if res:
            self.parentApp.prof.update_node_profile(self.node)
            self.next_form = None
        else:
            self.next_form = 'MAIN'

    def while_editing(self, instance):
        # instance is the instance of the widget you're moving into
        # map instance.name
        field = ''
        for item in self.node:
            if instance.name == self.node[item].desc:
                field = item
                break
        # On instantiation, self.prev_field is empty
        if self.prev_field:
            if hasattr(self.node[self.prev_field], 'dtype'):
                prev_fld_dtype = self.node[self.prev_field]['dtype']
            else:
                prev_fld_dtype = 'text'
            if hasattr(self.node[self.prev_field], 'ftype'):
                prev_fld_ftype = self.node[self.prev_field]['ftype']
            else:
                prev_fld_ftype = 'text'

            val = self.fields[self.prev_field].value

            if prev_fld_dtype == 'ipv4' or 'ipv4-' in prev_fld_dtype:
                if not u.is_ipaddr(val):
                    npyscreen.notify_confirm(f'Invalid Field value: {val}',
                                             title=self.prev_field, editw=1)
                else:
                    if 'ipv4-' in prev_fld_dtype:
                        mask_field = prev_fld_dtype.split('-')[-1]
                        prefix = int(self.fields[mask_field].value.split()[-1])
                        net_addr = u.get_network_addr(val, prefix)
                        if net_addr != val:
                            npyscreen.notify_confirm(f'IP addr modified to: {net_addr}',
                                                     title=self.prev_field, editw=1)
                            self.fields[self.prev_field].value = net_addr
                            self.display()

            elif prev_fld_dtype == 'ipv4mask':
                prefix = int(val.split()[-1])
                if prefix < 1 or prefix > 32:
                    npyscreen.notify_confirm(f'Invalid Field value: {val}',
                                             title=self.prev_field, editw=1)
                    prefix = 24
                if len(val.split()[-1]) == 2:
                    mask = u.get_netmask(prefix)
                    self.fields[self.prev_field].value = f'{mask} {prefix}'
                    self.display()

            elif 'int-or-none' in prev_fld_dtype:
                rng = self.node[self.prev_field]['dtype'].lstrip('int-or-none').\
                    split('-')
                if val:
                    val = val.strip(' ')
                if val and val != 'None':
                    try:
                        int(val)
                    except ValueError:
                        npyscreen.notify_confirm(f"Enter digits 0-9 or enter 'None' "
                                                 "or leave blank",
                                                 title=self.prev_field, editw=1)
                    else:
                        if int(val) < int(rng[0]) or int(val) > int(rng[1]):
                            msg = (f'Invalid Field value: {val}. Please leave empty or '
                                   'enter a value between 2 and 4094.')
                            npyscreen.notify_confirm(msg, title=self.prev_field, editw=1)

            elif 'int' in prev_fld_dtype:
                rng = self.node[self.prev_field]['dtype'].lstrip('int').split('-')
                if val:
                    try:
                        int(val)
                    except ValueError:
                        npyscreen.notify_confirm(f'Enter digits 0-9',
                                                 title=self.prev_field, editw=1)
                    else:
                        if int(val) < int(rng[0]) or int(val) > int(rng[1]):
                            msg = (f'Invalid Field value: {val}. Please enter a value '
                                   f'between 2 and 4094.')
                            npyscreen.notify_confirm(msg, title=self.prev_field, editw=1)

            elif 'file' in prev_fld_dtype:
                if not os.path.isfile(val):
                    npyscreen.notify_confirm(f'Specified iso file does not exist: {val}',
                                             title=self.prev_field, editw=1)
                elif '-iso' in prev_fld_dtype and '.iso' not in val:
                    npyscreen.notify_confirm('Warning, the selected file does not have a '
                                             '.iso extension',
                                             title=self.prev_field, editw=1)
            elif 'eth-ifc' in prev_fld_ftype:
                pass


        if instance.name == 'Press me':
            if self.press_me_butt.value == True:
                npyscreen.notify_confirm('Hey, you pressed me',
                                         title=self.prev_field, editw=1)

        if field:
            self.prev_field = field
        else:
            self.prev_field = ''

        if instance.name not in ['OK', 'Cancel', 'CANCEL', 'Edit network config', 'Scan for nodes']:
            self.helpmsg = self.node[field].help
        else:
            self.prev_field = ''

    def h_help(self, char):
        npyscreen.notify_confirm(self.helpmsg, title=self.prev_field, editw=1)

    def h_enter(self, char):
        npyscreen.notify_yes_no(f'Field Error: {self.field}', title='Enter', editw=1)

    def when_press_edit_networks(self):
        #npyscreen.notify_confirm('You press the me button')
        self.next_form = 'MAIN'
        self.parentApp.switchForm('MAIN')

    def scan_for_nodes(self):
        npyscreen.notify_confirm('Scanning for nodes')

    def create(self):
        self.y, self.x = self.useable_space()
        self.prev_field = ''
        self.node = self.parentApp.prof.get_node_profile()
        self.fields = {}  # dictionary for holding field instances

        for item in self.node:
            fname = self.node[item].desc
            if hasattr(self.node[item], 'floc'):
                if self.node[item]['floc'] == 'skipline':
                    self.nextrely += 1

                if 'sameline' in self.node[item]['floc']:
                    relx = int(self.node[item]['floc'].lstrip('sameline'))
                else:
                    relx = 2
            else:
                relx = 2
            # Place the field
            if hasattr(self.node[item], 'ftype'):
                ftype = self.node[item]['ftype']
            else:
                ftype = 'text'
            if hasattr(self.node[item], 'dtype'):
                dtype = self.node[item]['dtype']
            else:
                dtype = 'text'

            if ftype == 'file':
                if not self.node[item]['val']:
                    self.node[item]['val'] = os.path.join(GEN_PATH, 'os-images')
                self.fields[item] = self.add(npyscreen.TitleFilenameCombo,
                                             name=fname,
                                             value=str(self.node[item]['val']),
                                             begin_entry_at=20)

            elif 'ipv4mask' in dtype:
                self.fields[item] = self.add(npyscreen.TitleText, name=fname,
                                             value=str(self.node[item]['val']),
                                             begin_entry_at=20, width=40,
                                             relx=relx)
            elif 'eth-ifc' in ftype:
                eth = self.node[item]['val']
                eth_lst = self.parentApp.ifcs.get_up_interfaces_names(_type='phys')
                # Get the existing value to the top of the list
                if eth in eth_lst:
                    eth_lst.remove(eth)
                eth_lst = [eth] + eth_lst if eth else eth_lst
                self.fields[item] = self.add(npyscreen.TitleCombo,
                                             name=fname,
                                             value=0,
                                             values=eth_lst,
                                             begin_entry_at=20,
                                             scroll_exit=False)
            elif ftype == 'select-one':
                if hasattr(self.node[item], 'val'):
                    value = self.node[item]['values'].index(self.node[item]['val'])
                else:
                    value = 0
                self.fields[item] = self.add(npyscreen.TitleSelectOne, name=fname,
                                             max_height=2,
                                             value=value,
                                             values=self.node[item]['values'],
                                             scroll_exit=True,
                                             begin_entry_at=20, relx=relx)

            # no ftype specified therefore Title text
            else:
                self.fields[item] = self.add(npyscreen.TitleText,
                                             name=fname,
                                             value=str(self.node[item]['val']),
                                             begin_entry_at=20, width=40,
                                             relx=relx)
            self.fields[item].entry_widget.add_handlers({curses.KEY_F1:
                                                        self.h_help})

        self.scan_for_nodes = self.add(npyscreen.MiniButtonPress,
                                       when_pressed_function=self.scan_for_nodes,
                                       name='Scan for nodes',
                                       rely=-3)

        self.edit_networks = self.add(npyscreen.MiniButtonPress,
                                      when_pressed_function=self.when_press_edit_networks,
                                      name='Edit network config',
                                      rely=-3, relx=25)


def validate(profile_tuple):
    LOG = logger.getlogger()
    if profile_tuple.bmc_address_mode == "dhcp" or profile_tuple.pxe_address_mode == "dhcp":
        hasDhcpServers = u.has_dhcp_servers(profile_tuple.ethernet_port)
        if not hasDhcpServers:
            LOG.warn("No Dhcp servers found on {0}".format(profile_tuple.ethernet_port))
        else:
            LOG.info("Dhcp servers found on {0}".format(profile_tuple.ethernet_port))


def main(prof_path):
    log = logger.getlogger()

    try:
        osi = OSinstall(prof_path)
        osi.run()
#        routes = osi.ifcs.get_interfaces_routes()
#        for route in routes:
#            print(f'{route:<12}: {routes[route]}')
        pro = Profile(prof_path)
        p = pro.get_network_profile_tuple()
        log.debug(p)
        n = pro.get_node_profile_tuple()
        #code.interact(banner='here', local=dict(globals(), **locals()))
#        res = osi.ifcs.get_interfaces_names()
#        print(res)
#        res = osi.ifcs.get_up_interfaces_names('phys')
#        print(res)
#        osi.config_interfaces()
#        validate(p)
#        print(p)
    except KeyboardInterrupt:
        log.info("Exiting at user request")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('prof_path', help='Full path to the profile file.',
                        nargs='?', default='profile.yml')
    parser.add_argument('--print', '-p', dest='log_lvl_print',
                        help='print log level', default='info')
    parser.add_argument('--file', '-f', dest='log_lvl_file',
                        help='file log level', default='info')
    args = parser.parse_args()

    if args.log_lvl_print == 'debug':
        print(args)
    logger.create('nolog', 'info')
    main(args.prof_path)
