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
import code

import lib.logger as logger
from lib.genesis import get_package_path, get_sample_configs_path
import lib.utilities as u

GEN_PATH = get_package_path()
GEN_SAMPLE_CONFIGS_PATH = get_sample_configs_path()

IPR = IPRoute()


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
                self.prof_path = os.path.join(GEN_SAMPLE_CONFIGS_PATH,
                                          'profile-template.yml')
        #code.interact(banner='here', local=dict(globals(), **locals()))
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


class OSinstall(npyscreen.NPSAppManaged):
    def __init__(self, prof_path, *args, **kwargs):
        super(OSinstall, self).__init__(*args, **kwargs)
        self.prof_path = prof_path
        self.prof = Profile(self.prof_path)
        self.log = logger.getlogger()

    def onStart(self):
        self.addForm('MAIN', OSinstall_form, name='Welcome to PowerUP    '
                     'Press F1 in any field for field help')

    def is_valid_profile(self, prof):
        """ Validates the content of the profile data.
        Returns:
            msg (str) empty if passed, else contains warning and error msg
        """
        msg = ''
        # Since the user can skip fields by mouse clicking 'OK'
        # We need additional checking here:
        #  Need to add checks of iso file (check extension)
        #  Check for valid up interfaces
        bmc_subnet = prof['bmc_subnet']['val']
        bmc_subnet_prefix = prof['bmc_subnet_prefix']['val']
        bmc_subnet_prefix = bmc_subnet_prefix.split()[1]
        pxe_subnet = prof['pxe_subnet']['val']
        pxe_subnet_prefix = prof['pxe_subnet_prefix']['val']
        pxe_subnet_prefix = pxe_subnet_prefix.split()[1]
        iso_image_file = prof['iso_image_file']['val']
        if u.is_overlapping_addr(f'{bmc_subnet}/{bmc_subnet_prefix}',
                                 f'{pxe_subnet}/{pxe_subnet_prefix}'):
            msg += 'Warning, BMC and PXE subnets are overlapping\n'

        if bmc_subnet_prefix != pxe_subnet_prefix:
            msg += 'Warning, BMC and PXE subnets are different sizes\n'

        if not os.path.isfile(iso_image_file):
            msg += ('Error. Operating system ISO image file not found: \n'
                    f'{p.iso_image_file}')

        return msg

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
        """ Create a list of 'UP' links.
        """
        ifcs_up = []
        for link in IPR.get_links():
            if not link.get_attr('IFLA_LINKINFO'):
                if link.get_attr('IFLA_OPERSTATE') == 'UP':
                    link_name = link.get_attr('IFLA_IFNAME')
                    ifcs_up.append(link_name)
        return ifcs_up

    def _is_ifc_up(self, ifname):
        if 'UP' == self.ipr.get_links(
                self.ipr.link_lookup(ifname=ifname))[0].get_attr('IFLA_OPERSTATE'):
            return True
        return False

    def _wait_for_ifc_up(self, ifname, timespan=10):
        """ Waits up to timespan seconds for the specified interface to be up.
        Prints a message if the interface is not up in 2 seconds.
        Args:
            ifname (str) : Name of the interface
            timespan (int) : length of time to wait in seconds
        Returns:
            True if interface is up, False if not.
        """
        for t in range(2 * timespan):
            if t == 4:
                print(f'Waiting for interface {ifname} to come up.')
            if self._is_ifc_up(ifname):
                self.log.debug(f'Interface {ifname} is up.')
                return True
            time.sleep(0.5)
        self.log.info(f'Timeout waiting for interface {ifname} to come up.')
        return False

    def config_interfaces(self):
        self.ipr = IPRoute()
        p = self.prof.get_profile_tuple()
        # create any tagged vlan interfaces
        for vlan in (p.bmc_vlan_number, p.pxe_vlan_number):
            if vlan:
                ifc = p.ethernet_port + '.' + vlan
                # need check here to see if the vlan exists on any other interfaces
                # besides the one we're about to create (ifc)
                if not self.ipr.link_lookup(ifname=ifc):
                    self.log.debug(f'Creating vlan interface: {ifc}')
                    #code.interact(banner='here', local=dict(globals(), **locals()))
                    res = self.ipr.link("add", ifname=ifc, kind="vlan",
                        link=self.ipr.link_lookup(ifname=p.ethernet_port)[0],
                        vlan_id=int(vlan))
                    if res[0]['header']['error']:
                        self.log.debug(f'Error creating vlan interface: {ifc} {res}')
                    else:
                        self.ipr.link("set", index=self.ipr.link_lookup(ifname=ifc)[0],
                                      state="up")
                        if not self._wait_for_ifc_up(ifc):
                            self.log.error('Failed to bring up interface {ifc} ')

class OSinstall_form(npyscreen.ActionFormV2):
    def afterEditing(self):
        self.parentApp.setNextForm(self.next_form)

    def on_cancel(self):
        res = npyscreen.notify_yes_no('Quit without saving?', title='cancel 1',
                                      editw=1)
        self.next_form = None if res else 'MAIN'

    def on_ok(self):
        for item in self.prof:
            if hasattr(self.prof[item], 'ftype'):
                if self.prof[item]['ftype'] == 'eth-ifc':
                    self.prof[item]['val'] = self.eth_lst[self.fields[item].value]
                elif self.prof[item]['ftype'] == 'select-one':
                    self.prof[item]['val'] = \
                        self.prof[item]['values'][self.fields[item].value[0]]
                else:
                    #code.interact(banner='There', local=dict(globals(), **locals()))
                    self.prof[item]['val'] = self.fields[item].value
            else:
                self.prof[item]['val'] = self.fields[item].value

        #code.interact(banner='here', local=dict(globals(), **locals()))
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
            self.parentApp.prof.update_profile(self.prof)
            self.next_form = None
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


#        if instance.name == 'Press me':
#            if self.press_me_butt.value == True:
#                pass

        if field:
            self.prev_field = field
        else:
            self.prev_field = ''

        if instance.name not in ['OK', 'Cancel', 'CANCEL']:
            self.helpmsg = self.prof[field].help
        else:
            self.prev_field = ''

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
        self.prof = self.parentApp.prof.get_profile()
        #code.interact(banner='here', local=dict(globals(), **locals()))
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

#        self.press_me_butt = self.add(npyscreen.MiniButtonPress,
#                                     name='Press me')


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
        sys.exit('bye')
    logger.create('nolog', 'info')
    log = logger.getlogger()

    osi = OSinstall(args.prof_path)
    osi.run()
    #p = osi.prof.get_profile_tuple()
    # msg = osi.prof.is_valid_profile()
    # print(msg)
    #print(p)
    #osi.config_interfaces()
