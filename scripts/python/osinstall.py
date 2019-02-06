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
import copy
from orderedattrdict.yamlutils import AttrDictYAMLLoader
from collections import namedtuple
from pyroute2 import IPRoute
import sys
from time import sleep

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
        This is generally intended for use by Profile and the entry menu, not by
        application code
        """
        return self.profile

    def get_network_profile(self):
        """Returns an ordered attribute dictionary with the network profile data.
        This is generally intended for use by the entry menu, not by application
        code. deepcopy is used to return a new copy of the relevent profile, not
        a reference to the original.
        """
        return copy.deepcopy(self.profile.network)

    def get_network_profile_tuple(self):
        """Returns a named tuple constucted from the network profile data.
        OS install code should generally use this method to get the network
        profile data.
        """
        p = self.get_network_profile()
        _list = []
        vals = ()
        for item in p:
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
        """Returns an ordered attribute dictionary with the node profile data.
        This is generally intended for use by the entry menu, not by application
        code. deepcopy is used to return a new copy of the relevent profile, not
        a reference to the original.
        """
        return copy.deepcopy(self.profile.node)

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
        self.form_flow = (None, 'MAIN', 'NODE', None)

    def get_form_data(self):
        if self.creating_form == 'MAIN':
            return self.prof.get_network_profile()
        if self.creating_form == 'NODE':
            return self.prof.get_node_profile()

    def onStart(self):
        self.creating_form = 'MAIN'
        self.addForm('MAIN', Pup_form, name='Welcome to PowerUP    '
                     'Press F1 for field help', lines=24)

        self.creating_form = 'NODE'
        self.addForm('NODE', Pup_form, name='Welcome to PowerUP    '
                     'Press F1 for field help')

    def scan_for_nodes(self):
        sys.exit('scanned for nodes')

    def is_valid_profile(self, prof):
        """ Validates the content of the profile data.
        Returns:
            msg (str) empty if passed, else contains warning and error msg
        """
        msg = []
        if hasattr(prof, 'bmc_userid'):
            iso_image_file = prof['iso_image_file']['val']
            if not os.path.isfile(iso_image_file):
                msg += ["Error. Operating system ISO image file not found: ",
                        f"{prof['iso_image_file']['val']}"]
            return msg
        # Since the user can skip fields by mouse clicking 'OK'
        # We need additional checking here:
        #  Need to add checks of iso file (check extension)
        #  Check for valid up interfaces
        bmc_subnet_prefix = prof['bmc_subnet_prefix']['val'].split()[1]
        bmc_cidr = prof['bmc_subnet']['val'] + '/' + bmc_subnet_prefix
        pxe_subnet_prefix = prof['pxe_subnet_prefix']['val'].split()[1]
        pxe_cidr = prof['pxe_subnet']['val'] + '/' + pxe_subnet_prefix

        pxe_ethernet_ifc = prof['pxe_ethernet_ifc']['val']
        bmc_ethernet_ifc = prof['bmc_ethernet_ifc']['val']

        ifc = self.ifcs.is_route_overlapping(pxe_cidr, pxe_ethernet_ifc)
        if ifc:
            msg += ['- Warning, the subnet specified on the PXE interface',
                    f'  overlaps a subnet on interface {ifc}']

        ifc = self.ifcs.is_route_overlapping(bmc_cidr, bmc_ethernet_ifc)
        if ifc:
            msg += ['- Warning, the subnet specified on the BMC interface',
                    f'  overlaps a subnet on interface {ifc}']

        if u.is_overlapping_addr(bmc_cidr, pxe_cidr):
            msg += ['- Warning, BMC and PXE subnets are overlapping.']

        if bmc_subnet_prefix != pxe_subnet_prefix:
            msg += ['- Warning, BMC and PXE subnets are different sizes']

        if prof.bmc_address_mode.val == "dhcp" and prof.bmc_ethernet_ifc.val:
            dhcp = u.get_dhcp_servers(prof.bmc_ethernet_ifc.val)
            if dhcp:
                msg += ['- Warning a DHCP server exists already on',
                        '  the interface specified for BMC access. ',
                        f'  Offered address: {dhcp["IP Offered"]}',
                        f'  From server: {dhcp["Server Identifier"]}']

        if prof.pxe_ethernet_ifc.val:
            dhcp = u.get_dhcp_servers(prof.pxe_ethernet_ifc.val)
            if dhcp:
                msg += ['- Warning a DHCP server exists already on',
                        '  the interface specified for PXE access. ',
                        f'  Offered address: {dhcp["IP Offered"]}',
                        f'  From server: {dhcp["Server Identifier"]}']

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


class MyButtonPress(npyscreen.MiniButtonPress):

    def whenPressed(self):
        if self.name == 'Edit network config':
            self.parent.next_form = 'MAIN'
            self.parent.parentApp.switchForm('MAIN')
        if self.name == 'Scan for nodes':
            p = self.parent.parentApp.prof.get_network_profile_tuple()
            nodes = u.scan_subnet(p.bmc_subnet_cidr)
            self.parent.fields['node_list'].values = nodes
            self.parent.display()


class Pup_form(npyscreen.ActionFormV2):

    def beforeEditing(self):
        pass

    def afterEditing(self):
        self.parentApp.setNextForm(self.next_form)

    def create(self):
        self.y, self.x = self.useable_space()
        self.prev_field = ''
        self.node = self.parentApp.get_form_data()
        self.fields = {}  # dictionary for holding field instances
        self.next_form = self.parentApp.NEXT_ACTIVE_FORM
        self.node_list = []

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
                idx = 0 if eth else None
                self.fields[item] = self.add(npyscreen.TitleCombo,
                                             name=fname,
                                             value=idx,
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

            elif ftype == 'select-multi':
                if hasattr(self.node[item], 'val'):
                    if (hasattr(self.node[item], 'dtype') and
                            self.node[item]['dtype'] == 'no-save'):
                        value = list(self.node[item]['val'])
                    else:
                        value = self.node[item]['val']
                else:
                    value = None
                self.fields[item] = self.add(npyscreen.TitleMultiSelect, name=fname,
                                             max_height=10,
                                             value=value,
                                             values=self.node[item]['values'],
                                             scroll_exit=True,
                                             begin_entry_at=20, relx=relx)

            elif 'button' in ftype:
                if ',' in ftype:
                    x = int(self.node[item]['ftype'].lstrip('button').split(',')[0])
                    y = int(self.node[item]['ftype'].lstrip('button').split(',')[1])
                self.fields[item] = self.add(MyButtonPress,
                                             name=self.node[item]['desc'],
                                             relx=x,
                                             rely=y)

            # no ftype specified therefore Title text
            else:
                self.fields[item] = self.add(npyscreen.TitleText,
                                             name=fname,
                                             value=str(self.node[item]['val']),
                                             begin_entry_at=20, width=40,
                                             relx=relx)

            if hasattr(self.node[item], 'ftype') and 'button' in self.node[item]['ftype']:
                pass
            else:
                self.fields[item].entry_widget.add_handlers({curses.KEY_F1:
                                                            self.h_help})

    def on_cancel(self):
        fvl = self.parentApp._FORM_VISIT_LIST
        res = npyscreen.notify_yes_no('Quit without saving?',
                                      title='cancel 1',
                                      editw=1)
        if res:
            if len(fvl) == 1 and fvl[-1] == 'MAIN':
                self.next_form = None
            elif len(fvl) > 1:
                if fvl[-1] == 'NODE':
                    self.next_form = None
                elif fvl[-1] == 'MAIN':
                    self.next_form = fvl[-2]
        else:
            self.next_form = fvl[-1]

    def on_ok(self):
        for item in self.node:
            if hasattr(self.node[item], 'dtype') and self.node[item]['dtype'] == 'no-save':
                continue
            if hasattr(self.node[item], 'ftype'):
                if self.node[item]['ftype'] == 'eth-ifc':
                    # npyscreen.notify_confirm(f'ifc value: {self.fields[item].value}',
                    # editw=1)
                    if self.fields[item].value is None:
                        self.node[item]['val'] = None
                    else:
                        self.node[item]['val'] = \
                            self.fields[item].values[self.fields[item].value]
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
        msg = ['Validating network profile']
        if (hasattr(self.node, 'bmc_address_mode')):
            if self.node.bmc_address_mode.val == 'dhcp' or self.node.pxe_ethernet_ifc.val:
                msg += ['and checking for existing DHCP servers']
            npyscreen.notify(msg, title='Info')
            sleep(1)
        msg = self.parentApp.is_valid_profile(self.node)
        res = True
        if msg:
            if 'Error' in msg:
                npyscreen.notify_confirm(f'{msg}\n Please resolve issues.',
                                         title='cancel 1', editw=1)
                # stay on this form
                self.next_form = self.parentApp.NEXT_ACTIVE_FORM
                res = False
            else:
                msg += ['---------------------',
                        'Continue with OS install?',
                        '(No to continue editing the profile data)']

                editw = 1 if len(msg) < 10 else 0
                res = npyscreen.notify_yes_no(msg, title='Profile validation', editw=editw)

        if res:
            if self.parentApp.NEXT_ACTIVE_FORM == 'MAIN':
                self.parentApp.prof.update_network_profile(self.node)
                self.next_form = 'NODE'
            elif self.parentApp.NEXT_ACTIVE_FORM == 'NODE':
                self.parentApp.prof.update_node_profile(self.node)
                self.next_form = None

        else:
            # stay on this form
            self.next_form = self.parentApp.NEXT_ACTIVE_FORM

    def while_editing(self, instance):
        # instance is the instance of the widget you're moving into
        field = ''
        for item in self.node:
            # lookup field from instance name
            if instance.name == self.node[item].desc:
                field = item
                break
        # npyscreen.notify_confirm(f'field: {field} prev field: {self.prev_field}', editw=1)
        # On instantiation, self.prev_field is empty
        if self.prev_field:
            if field and hasattr(self.node[field], 'dtype'):
                field_dtype = self.node[field]['dtype']
            else:
                field_dtype = None
#            if hasattr(self.node[self.prev_field], 'dtype'):
#                prev_field_dtype = self.node[self.prev_field]['dtype']
#            else:
#                prev_field_dtype = None

#            if hasattr(self.node[self.prev_field], 'ftype'):
#                prev_field_ftype = self.node[self.prev_field]['ftype']
#            else:
#                prev_field_ftype = None

        if self.prev_field and field_dtype != 'no-save':
            if hasattr(self.node[self.prev_field], 'dtype'):
                prev_fld_dtype = self.node[self.prev_field]['dtype']
            else:
                prev_fld_dtype = 'text'
            if hasattr(self.node[self.prev_field], 'ftype'):
                prev_fld_ftype = self.node[self.prev_field]['ftype']
            else:
                prev_fld_ftype = 'text'
            if hasattr(self.node[self.prev_field], 'lnkd_flds'):
                prev_fld_lnkd_flds = self.node[self.prev_field]['lnkd_flds']
            else:
                prev_fld_lnkd_flds = None

            prev_fld_val = self.fields[self.prev_field].value

            if prev_fld_dtype == 'ipv4':
                if not u.is_ipaddr(prev_fld_val):
                    npyscreen.notify_confirm(f'Invalid Field value: {prev_fld_val}',
                                             title=self.prev_field, editw=1)
                else:
                    if prev_fld_lnkd_flds:
                        prefix = int(self.fields[prev_fld_lnkd_flds.prefix].value.split()[-1])

                        net_addr = u.get_network_addr(prev_fld_val, prefix)
                        if net_addr != prev_fld_val:
                            npyscreen.notify_confirm(f'IP addr modified to: {net_addr}',
                                                     title=self.prev_field, editw=1)
                            self.fields[self.prev_field].value = net_addr
                            self.display()

                        cidr = prev_fld_val + '/' + self.fields[prev_fld_lnkd_flds.prefix].value.split()[-1]
                        ifc = self.parentApp.ifcs.get_interface_for_route(cidr)
                        # npyscreen.notify_confirm(f'ifc: {ifc}', editw=1)
                    if not ifc:
                        ifc = self.parentApp.ifcs.get_up_interfaces_names(_type='phys')
                    else:
                        ifc = [ifc]
                    if ifc:
                        self.fields[self.node[self.prev_field]['lnkd_flds']['ifc']].values = ifc
                        idx = 0 if len(ifc) == 1 else None
                        self.fields[self.node[self.prev_field]['lnkd_flds']['ifc']].value = idx
                        self.display()

            elif prev_fld_dtype == 'ipv4mask':
                prefix = int(prev_fld_val.split()[-1])
                if prefix < 1 or prefix > 32:
                    npyscreen.notify_confirm(f'Invalid Field value: {prev_fld_val}',
                                             title=self.prev_field, editw=1)
                    prefix = 24
                # update the mask part of the field
                if len(prev_fld_val.split()[-1]) == 2:
                    mask = u.get_netmask(prefix)
                    self.fields[self.prev_field].value = f'{mask} {prefix}'
                    self.display()
                if prev_fld_lnkd_flds:
                    # get the ip address from the linked field
                    cidr = self.fields[prev_fld_lnkd_flds.subnet].value + '/' + prev_fld_val.split()[-1]
                    ifc = self.parentApp.ifcs.get_interface_for_route(cidr)
                    if not ifc:
                        ifc = self.parentApp.ifcs.get_up_interfaces_names(_type='phys')
                    else:
                        ifc = [ifc]
                    if ifc:
                        self.fields[self.node[self.prev_field]['lnkd_flds']['ifc']].values = ifc
                        idx = 0 if len(ifc) == 1 else None
                        self.fields[self.node[self.prev_field]['lnkd_flds']['ifc']].value = idx
                        self.display()

            elif 'int-or-none' in prev_fld_dtype:
                rng = self.node[self.prev_field]['dtype'].lstrip('int-or-none').\
                    split('-')
                if prev_fld_val:
                    prev_fld_val = prev_fld_val.strip(' ')
                if prev_fld_val and prev_fld_val != 'None':
                    try:
                        int(prev_fld_val)
                    except ValueError:
                        npyscreen.notify_confirm(f"Enter digits 0-9 or enter 'None' "
                                                 "or leave blank",
                                                 title=self.prev_field, editw=1)
                    else:
                        if int(prev_fld_val) < int(rng[0]) or int(prev_fld_val) > int(rng[1]):
                            msg = (f'Invalid Field value: {prev_fld_val}. Please leave empty or '
                                   'enter a value between 2 and 4094.')
                            npyscreen.notify_confirm(msg, title=self.prev_field, editw=1)

            elif 'int' in prev_fld_dtype:
                rng = self.node[self.prev_field]['dtype'].lstrip('int').split('-')
                if prev_fld_val:
                    try:
                        int(prev_fld_val)
                    except ValueError:
                        npyscreen.notify_confirm(f'Enter digits 0-9',
                                                 title=self.prev_field, editw=1)
                    else:
                        if int(prev_fld_val) < int(rng[0]) or int(prev_fld_val) > int(rng[1]):
                            msg = (f'Invalid Field value: {prev_fld_val}. Please enter a value '
                                   f'between 2 and 4094.')
                            npyscreen.notify_confirm(msg, title=self.prev_field, editw=1)

            elif 'file' in prev_fld_dtype:
                if not os.path.isfile(prev_fld_val):
                    npyscreen.notify_confirm(f'Specified iso file does not exist: {prev_fld_val}',
                                             title=self.prev_field, editw=1)
                elif '-iso' in prev_fld_dtype and '.iso' not in prev_fld_val:
                    npyscreen.notify_confirm('Warning, the selected file does not have a '
                                             '.iso extension',
                                             title=self.prev_field, editw=1)
            elif 'eth-ifc' in prev_fld_ftype:
                pass

        if field:
            self.prev_field = field
        else:
            self.prev_field = ''

        if instance.name not in ['OK', 'Cancel', 'CANCEL', 'Edit network config',
                                 'Scan for nodes']:
            self.helpmsg = self.node[field].help
        else:
            self.prev_field = ''

    def h_help(self, char):
        npyscreen.notify_confirm(self.helpmsg, title=self.prev_field, editw=1)

    def h_enter(self, char):
        npyscreen.notify_yes_no(f'Field Error: {self.field}', title='Enter', editw=1)

    def when_press_edit_networks(self):
        self.next_form = 'MAIN'
        self.parentApp.switchForm('MAIN')

    def scan_for_nodes(self):
        npyscreen.notify_confirm('Scanning for nodes')


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
#        n = pro.get_node_profile_tuple()
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
