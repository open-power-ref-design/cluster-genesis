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
import re
import sys
from time import time, sleep

import lib.logger as logger
import lib.interfaces as interfaces
from lib.genesis import get_package_path, get_sample_configs_path
import lib.utilities as u
import lib.bmc as _bmc

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
                        f'  From server:     {dhcp["Server Identifier"]}']

        if prof.pxe_ethernet_ifc.val:
            dhcp = u.get_dhcp_servers(prof.pxe_ethernet_ifc.val)
            if dhcp:
                msg += ['- Warning a DHCP server exists already on',
                        '  the interface specified for PXE access. ',
                        f'  Offered address: {dhcp["IP Offered"]}',
                        f'  From server:     {dhcp["Server Identifier"]}']

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

        elif self.name == 'Scan for nodes':
            self.parent.scan = True
            self.name = 'Stop node scan'
            self.parent.keypress_timeout = 5  # 0.5 sec to initiate scanning in 0.5 s

        elif self.name == 'Stop node scan':
            self.parent.scan = False
            self.name = 'Scan for nodes'

        self.parent.display()


class Pup_form(npyscreen.ActionFormV2):

    def beforeEditing(self):
        pass

    def afterEditing(self):
        self.parentApp.setNextForm(self.next_form)

    def create(self, *args, **keywords):
        super(Pup_form, self).create(*args, **keywords)

        self.keypress_timeout = 50  # hundreds of ms
        self.scan = False
        self.scanning = False
        self.y, self.x = self.useable_space()
        self.prev_field = ''
        self.form = self.parentApp.get_form_data()
        self.fields = {}  # dictionary for holding field instances
        self.next_form = self.parentApp.NEXT_ACTIVE_FORM
        self.talking_nodes = {}  # Nodes we can talk to using ipmi or openBMC
        if hasattr(self.form, 'bmc_userid'):
            self.scan_uid = self.form.bmc_userid.val
            self.scan_pw = self.form.bmc_password.val

        for item in self.form:
            fname = self.form[item].desc
            if hasattr(self.form[item], 'floc'):
                if self.form[item]['floc'] == 'skipline':
                    self.nextrely += 1

                if 'sameline' in self.form[item]['floc']:
                    relx = int(self.form[item]['floc'].lstrip('sameline'))
                else:
                    relx = 2
            else:
                relx = 2
            # Place the field
            if hasattr(self.form[item], 'ftype'):
                ftype = self.form[item]['ftype']
            else:
                ftype = 'text'
            if hasattr(self.form[item], 'dtype'):
                dtype = self.form[item]['dtype']
            else:
                dtype = 'text'

            if ftype == 'file':
                if not self.form[item]['val']:
                    self.form[item]['val'] = os.path.join(GEN_PATH, 'os-images')
                self.fields[item] = self.add(npyscreen.TitleFilenameCombo,
                                             name=fname,
                                             value=str(self.form[item]['val']),
                                             begin_entry_at=20)

            elif 'ipv4mask' in dtype:
                self.fields[item] = self.add(npyscreen.TitleText, name=fname,
                                             value=str(self.form[item]['val']),
                                             begin_entry_at=20, width=40,
                                             relx=relx)
            elif 'eth-ifc' in ftype:
                eth = self.form[item]['val']
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
                if hasattr(self.form[item], 'val'):
                    value = self.form[item]['values'].index(self.form[item]['val'])
                else:
                    value = 0
                self.fields[item] = self.add(npyscreen.TitleSelectOne, name=fname,
                                             max_height=2,
                                             value=value,
                                             values=self.form[item]['values'],
                                             scroll_exit=True,
                                             begin_entry_at=20, relx=relx)

            elif ftype == 'select-multi':
                if hasattr(self.form[item], 'val'):
                    if (hasattr(self.form[item], 'dtype') and
                            self.form[item]['dtype'] == 'no-save'):
                        value = list(self.form[item]['val'])
                    else:
                        value = self.form[item]['val']
                else:
                    value = None
                self.fields[item] = self.add(npyscreen.TitleMultiSelect, name=fname,
                                             max_height=10,
                                             value=value,
                                             values=self.form[item]['values'],
                                             scroll_exit=True,
                                             begin_entry_at=20, relx=relx)

            elif 'button' in ftype:
                if ',' in ftype:
                    x = int(self.form[item]['ftype'].lstrip('button').split(',')[0])
                    y = int(self.form[item]['ftype'].lstrip('button').split(',')[1])
                self.fields[item] = self.add(MyButtonPress,
                                             name=self.form[item]['desc'],
                                             relx=x,
                                             rely=y)

            # no ftype specified therefore Title text
            else:
                self.fields[item] = self.add(npyscreen.TitleText,
                                             name=fname,
                                             value=str(self.form[item]['val']),
                                             begin_entry_at=20, width=40,
                                             relx=relx)

            if hasattr(self.form[item], 'ftype') and 'button' in self.form[item]['ftype']:
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
        fld_error = False
        val_error = False
        msg = []
        for item in self.form:
            if hasattr(self.form[item], 'dtype'):
                if self.form[item]['dtype'] == 'no-save':
                    continue
                elif self.form[item]['dtype'] == 'ipv4':
                    # npyscreen.notify_confirm(f"{self.fields[item].value}", editw=1)
                    if not u.is_ipaddr(self.fields[item].value):
                        fld_error = True
                        msg += [f'Invalid ipv4 address: {self.fields[item].value}']

            if hasattr(self.form[item], 'ftype'):
                if self.form[item]['ftype'] == 'eth-ifc':
                    if self.fields[item].value is None:
                        self.form[item]['val'] = None
                        fld_error = True
                        msg += ['Missing ethernet interface.']
                    else:
                        self.form[item]['val'] = \
                            self.fields[item].values[self.fields[item].value]
                elif self.form[item]['ftype'] == 'select-one':
                    self.form[item]['val'] = \
                        self.form[item]['values'][self.fields[item].value[0]]
                else:
                    if self.fields[item].value == 'None':
                        self.form[item]['val'] = None
                    else:
                        self.form[item]['val'] = self.fields[item].value
            else:
                if self.fields[item].value == 'None':
                    self.form[item]['val'] = None
                else:
                    self.form[item]['val'] = self.fields[item].value
        if not fld_error:
            popmsg = ['Validating network profile']
            if (hasattr(self.form, 'bmc_address_mode')):
                if (self.form.bmc_address_mode.val == 'dhcp' or
                        self.form.pxe_ethernet_ifc.val):
                    popmsg += ['and checking for existing DHCP servers']
                npyscreen.notify(popmsg, title='Info')
                sleep(1)

            msg += self.parentApp.is_valid_profile(self.form)
            if 'Error' in msg:
                val_error = True

            if not fld_error or val_error:
                res = True
                if msg:
                    msg += ['---------------------',
                            'Continue with OS install?',
                            '(No to continue editing the profile data)']

                    editw = 1 if len(msg) < 10 else 0
                    res = npyscreen.notify_yes_no(msg, title='Profile validation',
                                                  editw=editw)

                if res:
                    if self.parentApp.NEXT_ACTIVE_FORM == 'MAIN':
                        self.parentApp.prof.update_network_profile(self.form)
                        self.next_form = 'NODE'
                    elif self.parentApp.NEXT_ACTIVE_FORM == 'NODE':
                        self.parentApp.prof.update_node_profile(self.form)
                        self.next_form = None

        elif fld_error or val_error:
            msg += ['Please reslove issues.']
            npyscreen.notify_confirm(msg, title='cancel', editw=1)
            # stay on this form
            self.next_form = self.parentApp.NEXT_ACTIVE_FORM

    def get_mask_and_prefix(self, mask_prefix):
        """ Extracts a mask and prefix from a string containing a mask and / or
            a prefix.
        Args:
            mask_prefix (str): Of the form 'ipmask prefix' or ipmask or prefix
        """
        # npyscreen.notify_confirm(f'mask_prefix: {mask_prefix}', editw=1)
        match1 = re.search(r'(?:.*\s+)*((?:\d{1,3}\.){3}\d{1,3})\s*', mask_prefix)
        match2 = re.search(r'\s*(\d{1,2})\s*$', mask_prefix)

        if match1:
            try:
                parts = match1.group(1).strip().split('.')
                if len(parts) == 4 and all(0 <= int(part) < 256 for part in parts):
                    mask = match1.group(1)
            except (ValueError, AttributeError, TypeError):
                mask = None

        else:
            mask = None

        if match2:
            try:
                prefix = int(match2.group(1))
                prefix = prefix if 0 < prefix < 33 else None
            except (ValueError, TypeError):
                prefix = None
        else:
            prefix = None

        msg = ('The entered mask and prefix do not match. The prefix is given '
               'precendence. If you wish to enter just a netmask, a prefix will be '
               'calculated. If you wish to enter just a prefix, a netmask will be '
               'calulated.')

        tmp = u.get_prefix(mask) if mask else 0
        if prefix != tmp:
            npyscreen.notify_confirm(msg, editw=1)
        # npyscreen.notify_confirm(f'mask: {mask} prefix: {prefix}', editw=1)
        return mask, prefix

    def while_waiting(self):
        if self.scan:
            self.keypress_timeout = 100  # set scan loop back to 10 sec
            p = self.parentApp.prof.get_network_profile_tuple()
            msg = ["Initiating scan.",
                   "Enter 'Stop node scan' to stop node scanning"]
            npyscreen.notify(msg)
            sleep(1.5)
            self.display()
            # nodes is list of tuples (ip, mac)
            nodes = u.scan_subnet(p.bmc_subnet_cidr)
            node_dict = {node[0]: node[1] for node in nodes}

            self.fields['devices_found'].value = str(len(nodes))

            ips = [node[0] for node in nodes]

            nodes = u.scan_subnet_for_port_open(ips, 623)

            ips = [node[0] for node in nodes]
            self.fields['bmcs_found'].value = str(len(nodes))

            scan_uid = self.fields['bmc_userid'].value
            scan_pw = self.fields['bmc_password'].value

            if scan_uid != self.scan_uid or scan_pw != self.scan_pw:
                self.talking_nodes = {}
                self.fields['node_list'].values = [()]
                self.fields['node_list'].value = 0
                self.fields['devices_found'].value = None
                self.fields['bmcs_found'].value = None
                self.scan_uid = scan_uid
                self.scan_pw = scan_pw

            node_list = self._get_bmcs_sn_pn(ips, scan_uid, scan_pw)
            if node_list:
                for node in node_list:
                    if node not in self.talking_nodes:
                        self.talking_nodes[node] = node_list[node] + (node_dict[node], node)
            field_list = [', '.join(self.talking_nodes[node]) for node in self.talking_nodes]

            if len(self.talking_nodes) == int(self.fields['bmcs_found'].value):
                self.scan = False
                self.fields['scan_for_nodes'].name = 'Scan for nodes'

            # code.interact(banner='waiting - scan2', local=dict(globals(), **locals()))
            # npyscreen.notify_confirm(f'field list: {field_list}', editw=1)
            self.fields['node_list'].values = field_list
            self.display()

    def while_editing(self, instance):
        # instance is the instance of the widget you're moving into
        field = ''
        for item in self.form:
            # lookup field from instance name
            if instance.name == self.form[item].desc:
                field = item
                break
        # npyscreen.notify_confirm(f'field: {field} prev field: {self.prev_field}', editw=1)
        # On instantiation, self.prev_field is empty
        if self.prev_field:
            if field and hasattr(self.form[field], 'dtype'):
                field_dtype = self.form[field]['dtype']
            else:
                field_dtype = None

        if self.prev_field and field_dtype != 'no-save':
            if hasattr(self.form[self.prev_field], 'dtype'):
                prev_fld_dtype = self.form[self.prev_field]['dtype']
            else:
                prev_fld_dtype = 'text'
            if hasattr(self.form[self.prev_field], 'ftype'):
                prev_fld_ftype = self.form[self.prev_field]['ftype']
            else:
                prev_fld_ftype = 'text'
            if hasattr(self.form[self.prev_field], 'lnkd_flds'):
                prev_fld_lnkd_flds = self.form[self.prev_field]['lnkd_flds']
            else:
                prev_fld_lnkd_flds = None

            prev_fld_val = self.fields[self.prev_field].value

            if prev_fld_dtype == 'ipv4':
                if not u.is_ipaddr(prev_fld_val):
                    npyscreen.notify_confirm(f'Invalid Field value: {prev_fld_val}',
                                             title=self.prev_field, editw=1)
                else:
                    if prev_fld_lnkd_flds:
                        prefix = int(self.fields[prev_fld_lnkd_flds.prefix].
                                     value.split()[-1])

                        net_addr = u.get_network_addr(prev_fld_val, prefix)
                        if net_addr != prev_fld_val:
                            npyscreen.notify_confirm(f'IP addr modified to: {net_addr}',
                                                     title=self.prev_field, editw=1)
                            self.fields[self.prev_field].value = net_addr
                            self.display()

                        cidr = (prev_fld_val + '/' + self.fields[prev_fld_lnkd_flds.
                                prefix].value.split()[-1])
                        ifc = self.parentApp.ifcs.get_interface_for_route(cidr)
                        # npyscreen.notify_confirm(f'ifc: {ifc}', editw=1)
                    if not ifc:
                        ifc = self.parentApp.ifcs.get_up_interfaces_names(_type='phys')
                    else:
                        ifc = [ifc]
                    if ifc:
                        self.fields[self.form[self.prev_field]['lnkd_flds']['ifc']].\
                            values = ifc
                        idx = 0 if len(ifc) == 1 else None
                        self.fields[self.form[self.prev_field]['lnkd_flds']['ifc']].\
                            value = idx
                        self.display()

            elif prev_fld_dtype == 'ipv4mask':
                mask, prefix = self.get_mask_and_prefix(prev_fld_val)
                if not prefix and not mask:
                    npyscreen.notify_confirm(f'Invalid Field value: {prev_fld_val}',
                                             title=self.prev_field, editw=1)
                    prefix = 24
                    mask = '255.255.255.0'
                elif prefix:
                    mask = u.get_netmask(prefix)
                else:
                    prefix = u.get_prefix(mask)
                self.fields[self.prev_field].value = f'{mask} {prefix}'
                self.display()

                if prev_fld_lnkd_flds:
                    # get the ip address from the linked field
                    cidr = (self.fields[prev_fld_lnkd_flds.subnet].value + '/' +
                            self.fields[self.prev_field].value.split()[-1])
                    # npyscreen.notify_confirm(f'cidr: {cidr}', editw=1)
                    ifc = self.parentApp.ifcs.get_interface_for_route(cidr)
                    if not ifc:
                        ifc = self.parentApp.ifcs.get_up_interfaces_names(_type='phys')
                    else:
                        ifc = [ifc]
                    if ifc:
                        self.fields[self.form[self.prev_field]['lnkd_flds']['ifc']].\
                            values = ifc
                        idx = 0 if len(ifc) == 1 else None
                        self.fields[self.form[self.prev_field]['lnkd_flds']['ifc']].\
                            value = idx
                        self.display()

            elif 'int-or-none' in prev_fld_dtype:
                rng = self.form[self.prev_field]['dtype'].lstrip('int-or-none').\
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
                        if (int(prev_fld_val) < int(rng[0]) or
                                int(prev_fld_val) > int(rng[1])):
                            msg = (f'Invalid Field value: {prev_fld_val}. Please '
                                   'leave empty or enter a value between 2 and 4094.')
                            npyscreen.notify_confirm(msg, title=self.prev_field, editw=1)

            elif 'int' in prev_fld_dtype:
                rng = self.form[self.prev_field]['dtype'].lstrip('int').split('-')
                if prev_fld_val:
                    try:
                        int(prev_fld_val)
                    except ValueError:
                        npyscreen.notify_confirm(f'Enter digits 0-9',
                                                 title=self.prev_field, editw=1)
                    else:
                        if (int(prev_fld_val) < int(rng[0]) or
                                int(prev_fld_val) > int(rng[1])):
                            msg = (f'Invalid Field value: {prev_fld_val}. Please enter '
                                   'a value between 2 and 4094.')
                            npyscreen.notify_confirm(msg, title=self.prev_field, editw=1)

            elif 'file' in prev_fld_dtype:
                if not os.path.isfile(prev_fld_val):
                    npyscreen.notify_confirm('Specified iso file does not exist: '
                                             'f{prev_fld_val}',
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
                                 'Scan for nodes', 'Stop node scan']:
            if field:
                self.helpmsg = self.form[field].help
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

    def _get_bmcs_sn_pn(self, node_list, uid, pw):
        """ Scan the node list for BMCs. Return the sn and pn of nodes which responded
        Args:
            node_list: Tuple or list of node ipv4 addresses
        returns:
            List of tuples containing ip, sn, pn
        """
        # create dict to hold Bmc class instances
        bmc_inst = {}
        # list for responding BMCs
        sn_pn_list = {}

        for ip in node_list:
            this_bmc = _bmc.Bmc(ip, uid, pw, 'ipmi')
            if this_bmc.is_connected():
                bmc_inst[ip] = this_bmc

        # Create dict to hold inventory gathering sub process instances
        sub_proc_instance = {}
        # Start a sub process instance to gather inventory for each node.
        for node in bmc_inst:
            sub_proc_instance[node] = bmc_inst[node].get_system_inventory_in_background()
        # poll for inventory gathering completion
        st_time = time()
        timeout = 15  # seconds

        while time() < st_time + timeout and len(sn_pn_list) < len(bmc_inst):
            for node in sub_proc_instance:
                if sub_proc_instance[node].poll() is not None:
                    if sub_proc_instance[node].poll() == 0 and node not in sn_pn_list:
                        inv, stderr = sub_proc_instance[node].communicate()
                        inv = inv.decode('utf-8')
                        sn_pn_list[node] = bmc_inst[node].extract_system_sn_pn(inv)

        for node in bmc_inst:
            bmc_inst[node].logout()

        return sn_pn_list


def main(prof_path):
    log = logger.getlogger()

    try:
        osi = OSinstall(prof_path)
        osi.run()
#        routes = osi.ifcs.get_interfaces_routes()
#        for route in routes:
#            print(f'{route:<12}: {routes[route]}')

#        pro = Profile(prof_path)
#        p = pro.get_network_profile_tuple()
#        nodes = u.scan_subnet(p.bmc_subnet_cidr)
#        ips = [node[0] for node in nodes]
#        #code.interact(banner='osinstall.main1', local=dict(globals(), **locals()))
#        nodes = u.scan_subnet_for_port_open(ips, 623)
#        ips = [node[0] for node in nodes]
#        n = pro.get_node_profile_tuple()
#        code.interact(banner='osinstall.main2', local=dict(globals(), **locals()))
#        sn_pn_good_list = _get_bmcs_sn_pn(ips, n.bmc_userid, n.bmc_password)
#        code.interact(banner='osinstall.main4', local=dict(globals(), **locals()))

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
    logger.create('nolog', 'nolog')
    main(args.prof_path)
