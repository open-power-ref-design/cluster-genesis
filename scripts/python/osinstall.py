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

import curses
import npyscreen
import os.path
import yaml
from orderedattrdict.yamlutils import AttrDictYAMLLoader
from collections import namedtuple
from pyroute2 import IPRoute

import lib.logger as logger
from lib.genesis import get_package_path, get_sample_configs_path
import lib.utilities as u

GEN_PATH = get_package_path()
GEN_SAMPLE_CONFIGS_PATH = get_sample_configs_path()

IPR = IPRoute()

logger.create('nolog', 'info')
LOG = logger.getlogger()
PROFILE = 'profile.yml'


class OSinstall(npyscreen.NPSAppManaged):

    def get_ifcs_addresses(self):
        """ Create a dictionary of links.  For each link, create list of cidr
        addresses
        """
        ifc_addresses = {}
        for link in IPR.get_links():
            link_name = link.get_attr('IFLA_IFNAME')
            ifc_addresses[link_name] = []
            for addr in IPR.get_addr(index=link['index']):
                ifc_addresses[link_name].append(
                    addr.get_attr('IFA_ADDRESS') + '/' + str(addr['prefixlen']))
        return ifc_addresses

    def get_ifcs_state(self):
        """ Create a dictionary of links.  For each link, val = operational state
        """
        ifcs_state = {}
        for link in IPR.get_links():
            link_name = link.get_attr('IFLA_IFNAME')
            ifcs_state[link_name] = link.get_attr('IFLA_OPERSTATE')
        return ifcs_state

    def get_up_phys_ifcs(self):
        """ Create a dictionary of links.  For each link, val = operational state
        """
        ifcs_up = []
        for link in IPR.get_links():
            if not link.get_attr('IFLA_LINKINFO'):
                if link.get_attr('IFLA_OPERSTATE') == 'UP':
                    link_name = link.get_attr('IFLA_IFNAME')
                    ifcs_up.append(link_name)
                    # ifcs_state[link_name] = link.get_attr('IFLA_OPERSTATE')
        return ifcs_up

    def onStart(self):
        self.addForm('MAIN', OSinstall_form, name='Welcome to PowerUP')

    def load_profile(self, profile):
        try:
            profile = yaml.load(open(GEN_PATH + profile), Loader=AttrDictYAMLLoader)
        except IOError:
            profile = yaml.load(open(GEN_SAMPLE_CONFIGS_PATH + 'profile-template.yml'),
                                Loader=AttrDictYAMLLoader)
        self.profile = profile

    def get_profile(self):
        """Returns an ordered attribute dictionary with the profile data.
        This is generally intended for use by the entry menu, not by application
        code
        """
        return self.profile

    def get_profile_tuple(self):
        """Returns a named tuple with the profile data
        OS install code should generally use this method to get the
        profile data.
        """
        p = self.get_profile()
        _list = []
        vals = ()
        for item in p:
            if 'subnet_prefix' not in item:
                _list.append(item)
                vals += (p[item].val,)
            # split the subnet prefix field into netmask and prefix
            else:
                _list.append(item)
                _list.append(item.replace('_prefix', '_mask'))
                vals += (p[item].val.split()[1],)
                vals += (p[item].val.split()[0],)

        proftup = namedtuple('ProfTup', _list)
        return proftup._make(vals)

    def update_profile(self, profile):
        self.profile = profile
        with open(GEN_PATH + 'profile.yml', 'w') as f:
            yaml.dump(self.profile, f, indent=4, default_flow_style=False)


class OSinstall_form(npyscreen.Form):
    def afterEditing(self):
        self.parentApp.setNextForm(self.next_form)

    def while_editing(self, instance):
        # instance is the instance of the widget you're moving into
        # map instance.name
        field = ''
        for item in self.prof:
            if instance.name == self.prof[item].desc:
                field = item
                break
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
                    try:
                        int(val)
                    except ValueError:
                        npyscreen.notify_confirm(f'Enter digits 0-9',
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

        if instance.name == 'OK':  # Write the data
            self.verify_data()
            for item in self.prof:
                if hasattr(self.prof[item], 'ftype'):
                    if self.prof[item]['ftype'] == 'eth-ifc':
                        self.prof[item]['val'] = self.eth_lst[self.fields[item].value]
                    elif self.prof[item]['ftype'] == 'select-one':
                        self.prof[item]['val'] = \
                            self.prof[item]['values'][self.fields[item].value[0]]
                    else:
                        self.prof[item]['val'] = self.fields[item].value
                else:
                    self.prof[item]['val'] = self.fields[item].value
            self.parentApp.update_profile(self.prof)

        if field:
            self.prev_field = field
        else:
            self.prev_field = ''

        if instance.name != 'OK':
            self.helpmsg = self.prof[field].help
        else:
            self.prev_field = ''

    def verify_data(self):
        self.next_form = None
        val = self.fields['iso_image_file'].value
        if not os.path.isfile(val):
            self.next_form = 'MAIN'
        #    npyscreen.notify_confirm(f'Specified iso file does not exist: {val}',
        #                             title=self.prev_field, editw=1)

    def h_help(self, char):
        npyscreen.notify_confirm(self.helpmsg, title=self.prev_field, editw=1)

    def h_enter(self, char):
        npyscreen.notify_yes_no(f'Field Error: {self.field}', title='Enter', editw=1)

    def create(self):
        ifcs = self.parentApp.get_ifcs_state()
        ifc_list = []
        for ifc in ifcs:
            if ifcs[ifc] == 'UP':
                ifc_list.append(ifc)
        self.helpmsg = 'help help'
        self.prev_field = ''
        self.prof = self.parentApp.get_profile()
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
#                self.fields[item].entry_widget.add_handlers({curses.KEY_F1:
#                                                            self.h_help})
            elif 'ipv4mask' in dtype:
                self.fields[item] = self.add(npyscreen.TitleText, name=fname,
                                             value=str(self.prof[item]['val']),
                                             begin_entry_at=20, width=40,
                                             relx=relx)
            elif 'eth-ifc' in ftype:
                eth = self.prof[item]['val']
                self.eth_lst = self.parentApp.get_up_phys_ifcs()
                if eth in self.eth_lst:
                    self.eth_lst.remove(eth)
                self.eth_lst = [eth] + self.eth_lst
                self.fields[item] = self.add(npyscreen.TitleCombo,
                                             name=fname,
                                             value=0,
                                             values=self.eth_lst,
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


def validate(profile_tuple):
    if profile_tuple.bmc_address_mode == "dhcp" or profile_tuple.pxe_address_mode == "dhcp":
        hasDhcpServers = u.has_dhcp_servers(profile_tuple.ethernet_port)
        if not hasDhcpServers:
            LOG.warn("No Dhcp servers found on {0}".format(profile_tuple.ethernet_port))
        else:
            LOG.info("Dhcp servers found on {0}".format(profile_tuple.ethernet_port))


def main():
    try:
        osi = OSinstall()
        osi.load_profile(PROFILE)
        osi.run()
        p = osi.get_profile_tuple()
        LOG.debug(p)
        validate(p)
        print(p)
    except KeyboardInterrupt:
        LOG.info("Exiting at user request")


if __name__ == '__main__':
    main()
