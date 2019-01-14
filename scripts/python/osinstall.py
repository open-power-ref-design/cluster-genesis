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

import lib.logger as logger
from lib.genesis import get_package_path, get_sample_configs_path
import lib.utilities as u

GEN_PATH = get_package_path()
GEN_SAMPLE_CONFIGS_PATH = get_sample_configs_path()


class OSinstall(npyscreen.NPSAppManaged):

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
        return self.profile

    def update_profile(self, profile):
        self.profile = profile
        with open(GEN_PATH + 'profile.yml', 'w') as f:
            yaml.dump(self.profile, f, indent=4, default_flow_style=False)


class OSinstall_form(npyscreen.Form):
    def afterEditing(self):
        self.parentApp.setNextForm(self.next_form)

    def while_editing(self, instance):
        # instance is the instance of the widget you're moving into
        if self.prev_field and self.prev_field != 'OK':
            prev_fld_dtype = self.prof[self.prev_field]['dtype']
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
            elif 'int' in prev_fld_dtype:
                rng = self.prof[self.prev_field]['dtype'].lstrip('int').split('-')
                if int(val) < int(rng[0]) or int(val) > int(rng[1]):
                    msg = (f'Invalid Field value: {val}. Please enter a value '
                           f'between 2 and 4094.')
                    npyscreen.notify_confirm(msg, title=self.prev_field, editw=1)
        if instance.name == 'OK':  # Write the data
            self.verify_data()
            for item in self.prof:
                self.prof[item]['val'] = self.fields[item].value
            self.parentApp.update_profile(self.prof)

        self.prev_field = instance.name
        if instance.name != 'OK':
            self.helpmsg = self.prof[instance.name]['help']

    def verify_data(self):
        self.next_form = None
        val = self.fields['ISO image file'].value
        if not os.path.isfile(val):
            npyscreen.notify_confirm(f'Specified iso file does not exist: {val}',
                                     title=self.prev_field, editw=1)
            self.next_form = 'MAIN'

    def h_help(self, char):
        npyscreen.notify_confirm(self.helpmsg, title=self.prev_field, editw=1)

    def h_enter(self, char):
        npyscreen.notify_yes_no(f'Field Error: {self.field}', title='Enter', editw=1)


    def create(self):
        self.helpmsg = 'help help'
        self.prev_field = ''
        self.prof = self.parentApp.get_profile()
        self.fields = {}
        for item in self.prof:
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
                if self.prof[item]['ftype'] == 'file':
                    if not self.prof[item]['val']:
                        self.prof[item]['val'] = os.path.join(GEN_PATH, 'os-images')
                    self.fields[item] = self.add(npyscreen.TitleFilenameCombo, name=item,
                                                 value=str(self.prof[item]['val']),
                                                 begin_entry_at=20)
                    self.fields[item].entry_widget.add_handlers({curses.KEY_F1: self.h_help})
                elif 'ipv4mask' in self.prof[item]['dtype']:
                    self.fields[item] = self.add(npyscreen.TitleText, name=item,
                                                 value=str(self.prof[item]['val']),
                                                 begin_entry_at=20, width = 40,
                                                 relx=relx, rely=self.nextrely-1)

            # no ftype specified therefore Title text
            else:
                if relx:
                    self.fields[item] = self.add(npyscreen.TitleText,
                                                 name=item,
                                                 value=str(self.prof[item]['val']),
                                                 begin_entry_at=20, width=40, relx=relx)
                    self.fields[item].entry_widget.add_handlers({curses.KEY_F1: self.h_help})
                else:
                    self.fields[item] = self.add(npyscreen.TitleText, name=item,
                                                 value=str(self.prof[item]['val']),
                                                 begin_entry_at=20, width = 40)
                    self.fields[item].entry_widget.add_handlers({curses.KEY_F1: self.h_help})


if __name__ == '__main__':

    logger.create('nolog', 'info')
    log = logger.getlogger()

    profile = 'profile.yml'
    osi = OSinstall()
    osi.load_profile(profile)
    osi.run()
