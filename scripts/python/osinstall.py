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
from netaddr import IPNetwork
from jinja2 import Template
from time import time, sleep, localtime, gmtime, strftime
import json
from tabulate import tabulate

import lib.logger as logger
import lib.interfaces as interfaces
from lib.genesis import get_package_path, get_sample_configs_path, \
    get_os_images_path, get_nginx_root_dir
import lib.utilities as u
from nginx_setup import nginx_setup
from ip_route_get_to import ip_route_get_to
from lib.bmc import Bmc
from set_bootdev_clients import set_bootdev_clients
from set_power_clients import set_power_clients
from lib.genesis import get_power_wait

GEN_PATH = get_package_path()
GEN_SAMPLE_CONFIGS_PATH = get_sample_configs_path()

IPR = IPRoute()

PROFILE = os.path.join(GEN_PATH, 'profile.yml')
NODE_STATUS = os.path.join(GEN_PATH, 'osinstall_node_status.yml')

HTTP_ROOT_DIR = get_nginx_root_dir()
OSINSTALL_HTTP_DIR = 'osinstall'
CLIENT_STATUS_DIR = '/var/pup_install_status/'

POWER_WAIT = get_power_wait()


def osinstall(profile_path):
    log = logger.getlogger()
    log.debug('osinstall')

#    on_ok_fns_list = ('is_valid_profile', 'config_interfaces',
#                      'check_for_existing_dhcp', 'add_firewall_rules',
#                      'install_and_configure_nginx', 'configure_dnsmasq')

    on_ok_fns_list = {}
    on_ok_fns_list['MAIN'] = \
        {'is_valid_profile': 'Validating network profile',
         'config_interfaces': 'Configuring network interfaces',
         'check_for_existing_dhcp': 'Checking for existing DHCP servers...',
         'add_firewall_rules': 'Adding firewall rules',
         'install_and_configure_nginx': 'Installing and configuring Nginx...',
         'configure_dnsmasq': 'Configuring dsnmasq for DHCP'}

    osi = OSinstall(profile_path, on_ok_fns_list=on_ok_fns_list)
    osi.run()


def dnsmasq_configuration(form_data):
    bmc_ethernet_ifc = form_data.bmc_ethernet_ifc.val
    bmc_subnet_cidr = form_data.bmc_subnet.val + '/' + \
        form_data.bmc_subnet_prefix.val.split()[-1]
    bmc_address_mode = form_data.bmc_address_mode.val

    pxe_ethernet_ifc = form_data.pxe_ethernet_ifc.val
    pxe_subnet_cidr = form_data.pxe_subnet.val + '/' + \
        form_data.pxe_subnet_prefix.val.split()[-1]

    dhcp_start = 21
    dhcp_lease_time = '5m'
    if (bmc_address_mode == 'static' or
            bmc_ethernet_ifc == pxe_ethernet_ifc):
        interfaces = pxe_ethernet_ifc
    else:
        interfaces = (bmc_ethernet_ifc + ',' + pxe_ethernet_ifc)

    pxe_network = IPNetwork(pxe_subnet_cidr)
    dhcp_pxe_ip_range = (str(pxe_network.network + dhcp_start) + ',' +
                         str(pxe_network.network + pxe_network.size - 1))

    rc = u.dnsmasq_config_pxelinux(interface=interfaces,
                                   dhcp_range=dhcp_pxe_ip_range,
                                   lease_time=dhcp_lease_time,
                                   disable_dns=True)

    if rc != 0:
        return rc

    if bmc_address_mode == 'dhcp':
        bmc_network = IPNetwork(bmc_subnet_cidr)
        dhcp_bmc_ip_range = (str(bmc_network.network + dhcp_start) + ',' +
                             str(bmc_network.network + bmc_network.size - 1))
        rc = u.dnsmasq_add_dhcp_range(dhcp_range=dhcp_bmc_ip_range,
                                      lease_time=dhcp_lease_time)

    return rc


def extract_install_image(profile_object):
    http_root = HTTP_ROOT_DIR
    http_osinstall = OSINSTALL_HTTP_DIR

    p = profile_object.get_node_profile_tuple()

    image_dir = os.path.join(http_root, http_osinstall)
    if not os.path.isdir(image_dir):
        os.makedirs(image_dir)
        os.chmod(image_dir, 0o755)
    kernel, initrd = u.extract_iso_image(p.iso_image_file, image_dir)

    return kernel, initrd


def render_kickstart(profile_object, kickstart_template=None):
    http_root = HTTP_ROOT_DIR
    http_osinstall = OSINSTALL_HTTP_DIR

    p_netw = profile_object.get_network_profile_tuple()
    p_node = profile_object.get_node_profile_tuple()

    kickstart = None

    image_name = os.path.basename(p_node.iso_image_file)[:-4]

    if kickstart_template is None:
        if 'ubuntu' in image_name.lower():
            kickstart_template = os.path.join(get_os_images_path(),
                                              'config/ubuntu-default.seed.j2')
        elif 'rhel' in image_name.lower():
            kickstart_template = os.path.join(get_os_images_path(),
                                              'config/RHEL-7-default.ks.j2')

    if kickstart_template is not None:
        kickstart = os.path.join(http_osinstall,
                                 os.path.basename(kickstart_template))
        if kickstart.endswith('.j2'):
            kickstart = kickstart[:-3]
        kickstart_out = os.path.join(http_root,
                                     http_osinstall,
                                     os.path.basename(kickstart_template))
        if kickstart_out.endswith('.j2'):
            kickstart_out = kickstart_out[:-3]

        j2_vars = {'pass_crypted': False,
                   'install_disk': None,
                   'timezone': 'America/Chicago',
                   'utc': True}

        pxe_network = IPNetwork(p_netw.pxe_subnet_cidr)
        j2_vars['http_server'] = ip_route_get_to(str(pxe_network.ip))

        j2_vars['http_repo_name'] = image_name
        j2_vars['http_repo_dir'] = os.path.join(http_osinstall,
                                                j2_vars['http_repo_name'])

        j2_vars['hostname'] = p_node.hostname

        j2_vars['domain'] = p_node.domain

        j2_vars['default_user'] = p_node.username

        j2_vars['default_pass'] = p_node.password

        with open(kickstart_template, 'r') as file_object:
            template = Template(file_object.read())

        with open(kickstart_out, 'w') as file_object:
            file_object.write(template.render(**j2_vars))

        os.chmod(kickstart_out, 0o755)

    return kickstart


def copy_pup_report_scripts():
    http_root = HTTP_ROOT_DIR
    http_osinstall = OSINSTALL_HTTP_DIR
    for filename in os.listdir(os.path.join(get_os_images_path(), 'config')):
        if filename.endswith('.sh'):
            u.copy_file(os.path.join(get_os_images_path(), 'config', filename),
                        os.path.join(http_root, http_osinstall),
                        metadata=False)


def pxelinux_configuration(profile_object, kernel, initrd, kickstart):
    log = logger.getlogger()
    http_osinstall = 'osinstall'

    p_netw = profile_object.get_network_profile_tuple()
    p_node = profile_object.get_node_profile_tuple()

    pxe_network = IPNetwork(p_netw.pxe_subnet_cidr)
    server = ip_route_get_to(str(pxe_network.ip))
    if server not in pxe_network:
        log.error(f'No direct route to PXE subnet! route={server}')

    kopts = None
    if 'ubuntu' in kernel.lower():
        kopts = ('netcfg/dhcp_timeout=1024 netcfg/do_not_use_netplan=true '
                 f'hostname={p_node.hostname} domain=localdomain ')
        if kickstart is not None:
            kopts += 'netcfg/choose_interface=auto auto-install/enable=true'

    u.pxelinux_set_default(
        server=server,
        kernel=os.path.join(http_osinstall, kernel),
        initrd=os.path.join(http_osinstall, initrd),
        kickstart=kickstart,
        kopts=kopts)


def get_selected_clients(profile_object, node_dict_file, bmc_ip='all'):
    p_node = profile_object.get_node_profile_tuple()
    nodes = yaml.full_load(open(node_dict_file))
    clients = {}
    for node in nodes['selected'].values():
        if bmc_ip == 'all' or bmc_ip == node['bmc_ip']:
            clients[node['bmc_ip']] = (p_node.bmc_userid,
                                       p_node.bmc_password,
                                       node['bmc_type'])
    return clients


def initiate_pxeboot(profile_object, node_dict_file):
    clients = get_selected_clients(profile_object, node_dict_file)
    set_power_clients('off', clients=clients, wait=POWER_WAIT)
    set_bootdev_clients('network', persist=False, clients=clients)
    set_power_clients('on', clients=clients, wait=POWER_WAIT)


def update_install_status(node_dict_file, start_time, write_results=True):
    """ Update client node installation status

    Args:
        node_dict_file (str): Selected nodes dictionary file path

        start_time (int): UNIX Epoch time - only status reported _after_
                          this time will be inspected

        write_results (bool, optional): Write updated node dictionary to
                                        file (using 'node_dict_file' path)

    Returns:
        dict: Selected node dictionary with updated 'start_time',
              'finish_time', and 'report_data' values

    """
    log = logger.getlogger()
    status_dir = CLIENT_STATUS_DIR
    nodes = yaml.full_load(open(node_dict_file))

    def _associate_pxe_to_bmc(nodes, pxe_ip, report_data=None):
        for bmc_mac, value in nodes['selected'].items():
            if 'pxe_ip' in value and value['pxe_ip'] == pxe_ip:
                return bmc_mac

        if report_data is not None:
            try:
                for channel in ['1', '8']:
                    bmc_mac = (
                        report_data[f'ipmitool_lan_print_{channel}']
                                   ['MAC Address'].upper())
                    if bmc_mac in nodes['selected']:
                        return bmc_mac
            except KeyError:
                log.debug('No ipmitool_lan_print MAC Address in report data')
            try:
                for fru in report_data['ipmitool_fru_print']:
                    if 'Chassis Serial' in fru:
                        for bmc_mac, value in nodes['selected'].items():
                            if fru['Chassis Serial'] == value['serial']:
                                return bmc_mac
            except KeyError:
                log.debug('No ipmitool_fru_print in report data')

        log.debug(f'Unable to associate PXE IP \'{pxe_ip}\' with client node')
        return None

    for filename in os.listdir(status_dir):
        filepath = os.path.join(status_dir, filename)
        if start_time is not None and start_time < os.path.getmtime(filepath):
            pxe_ip = filename.split('_')[0]
            status = filename.split('_')[1]

            try:
                with open(filepath) as json_file:
                    report_data = json.load(json_file)
            except (json.decoder.JSONDecodeError, UnicodeDecodeError):
                report_data = None

            bmc_mac = _associate_pxe_to_bmc(nodes, pxe_ip, report_data)

            if bmc_mac in nodes['selected']:
                nodes['selected'][bmc_mac]['pxe_ip'] = pxe_ip
                nodes['selected'][bmc_mac][status + '_time'] = (
                    os.path.getmtime(filepath))
                try:
                    if (nodes['selected'][bmc_mac]['start_time'] >=
                            nodes['selected'][bmc_mac]['finish_time']):
                        nodes['selected'][bmc_mac]['finish_time'] = None
                except (KeyError, TypeError):
                    pass
                if report_data is not None:
                    nodes['selected'][bmc_mac]['report_data'] = report_data
            else:
                if 'other' not in nodes:
                    nodes['other'] = {}
                if pxe_ip not in nodes['other']:
                    nodes['other'][pxe_ip] = {}
                nodes['other'][pxe_ip][status + '_time'] = (
                    os.path.getmtime(filepath))
                try:
                    if (nodes['other'][pxe_ip]['start_time'] >=
                            nodes['other'][pxe_ip]['finish_time']):
                        nodes['other'][pxe_ip]['finish_time'] = None
                except (KeyError, TypeError):
                    pass
                if (status == 'start' and
                        'finish_time' in nodes['other'][pxe_ip]):
                    nodes['other'][pxe_ip]['finish_time'] = None
                if report_data is not None:
                    nodes['other'][pxe_ip]['report_data'] = report_data
                log.debug('Unable to associate client installation report '
                          f'with a selected node: {filename}')
    if write_results:
        with open(NODE_STATUS, 'w') as f:
            yaml.dump(nodes, f, indent=4, default_flow_style=False)

    return nodes


def get_install_status(node_dict_file, colorized=False):
    """ Get client node installation status table

    Args:
        node_dict_file (str): Selected nodes dictionary file path

        colorized (bool, optional): Add color escapes to easily differentiate
                                    status of each line

    Returns:
        str: Installation status table
    """
    nodes = yaml.full_load(open(node_dict_file))

    def _try_dict_key(dictionary, *keys):
        value = dictionary
        try:
            for key in keys:
                value = value[key]
            if value is None:
                value = '-'
            return value
        except KeyError:
            return '-'

    if colorized:
        bold = u.Color.bold
        endc = u.Color.endc
    else:
        bold = ''
        endc = ''

    table = [[f'{bold}Serial', 'BMC MAC Address', 'BMC IP Address',
              'Host IP Address', f'Install Status{endc}']]
    for bmc_mac, value in nodes['selected'].items():
        color = None
        pxe_ip = _try_dict_key(value, 'pxe_ip')
        if _try_dict_key(value, 'start_time') != '-':
            if _try_dict_key(value, 'finish_time') != '-':
                color = u.Color.green
                finish_time = _try_dict_key(value, 'finish_time')
                start_time = _try_dict_key(value, 'start_time')
                elapsed_time = strftime("%Mm %Ss", gmtime(finish_time -
                                                          start_time))
                install_status = ("Finished: " +
                                  strftime("%x %X %Z",
                                           localtime(finish_time)) +
                                  f" ({elapsed_time})")
            else:
                color = u.Color.yellow
                start_time = _try_dict_key(value, 'start_time')
                install_status = ("Started: " +
                                  strftime("%Mm %Ss",
                                           gmtime(time() - start_time)))
        else:
            install_status = "-"
        table.append([value['serial'], bmc_mac, value['bmc_ip'], pxe_ip,
                      install_status])
        if colorized and color is not None:
            table[-1][0] = color + table[-1][0]
            table[-1][-1] = table[-1][-1] + u.Color.endc
    if 'other' in nodes:
        for pxe_ip, value in nodes['other'].items():
            color = None
            if _try_dict_key(value, 'start_time') != '-':
                if _try_dict_key(value, 'finish_time') != '-':
                    color = u.Color.green
                    finish_time = _try_dict_key(value, 'finish_time')
                    start_time = _try_dict_key(value, 'start_time')
                    elapsed_time = strftime("%Mm %Ss", gmtime(finish_time -
                                                              start_time))
                    install_status = ("Finished: " +
                                      strftime("%x %X %Z",
                                               localtime(finish_time)) +
                                      f" ({elapsed_time})")
                else:
                    color = u.Color.yellow
                    start_time = _try_dict_key(value, 'start_time')
                    install_status = ("Started: " +
                                      strftime("%Mm %Ss",
                                               gmtime(time() - start_time)))
            else:
                install_status = "-"
            table.append(['?', '?', '?', pxe_ip, install_status])
            if colorized and color is not None:
                table[-1][0] = color + table[-1][0]
                table[-1][-1] = table[-1][-1] + u.Color.endc

    return tabulate(table, headers="firstrow")


def reset_bootdev(profile_object, node_dict_file, bmc_ip='all'):
    clients = get_selected_clients(profile_object,
                                   node_dict_file,
                                   bmc_ip=bmc_ip)
    set_bootdev_clients('disk', persist=False, clients=clients)


class Profile():
    def __init__(self, prof_path='profile-template.yml'):
        profile_template_path = os.path.join(GEN_SAMPLE_CONFIGS_PATH,
                                             'profile-template.yml')

        def _update_profile():
            """Converts a pre version 1.0 (version-less) profile.yml file into
            a version 1.0 profile.
            """
            try:
                profile_template = yaml.load(open(profile_template_path),
                                             Loader=AttrDictYAMLLoader)
            except IOError:
                self.log.error('Unable to open the profile file: '
                               f'{self.prof_path}')
                sys.exit(f'Unable to open the profile file: {self.prof_path}\n'
                         'Unable to continue with OS install')
            for fld, fld_data in self.profile.network.items():
                if hasattr(fld_data, 'lnkd_flds'):
                    del(self.profile.network[fld].lnkd_flds)

            for fld, fld_data in profile_template.network.items():
                if hasattr(fld_data, 'smart_update'):
                    self.profile.network[fld]['smart_update'] = fld_data.smart_update

            self.profile.status = profile_template.status

        self.log = logger.getlogger()
        if prof_path == 'profile-template.yml':
            self.prof_path = profile_template_path
        else:
            if not os.path.dirname(prof_path):
                self.prof_path = os.path.join(GEN_PATH, prof_path)
            else:
                self.prof_path = prof_path
            if not os.path.isfile(self.prof_path):
                self.log.info('No profile file found.  Using template.')
                sleep(1)
                self.prof_path = profile_template_path
        try:
            self.profile = yaml.load(open(self.prof_path),
                                     Loader=AttrDictYAMLLoader)
        except IOError:
            self.log.error('Unable to open the profile file: '
                           f'{self.prof_path}')
            sys.exit(f'Unable to open the profile file: {self.prof_path}\n'
                     'Unable to continue with OS install')
        else:
            if 'version' not in self.profile:
                _update_profile()

    def get_profile(self):
        """Returns an ordered attribute dictionary with the profile data.
        This is generally intended for use by Profile and the entry menu, not
        by application code
        """
        return self.profile

    def get_network_profile(self):
        """Returns an ordered attribute dictionary with the network profile
        data. This is generally intended for use by the entry menu, not by
        application code. deepcopy is used to return a new copy of the relevent
        profile, not a reference to the original.
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
        with open(PROFILE, 'w') as f:
            yaml.dump(self.profile, f, indent=4, default_flow_style=False)

    def get_node_profile(self):
        """Returns an ordered attribute dictionary with the node profile data.
        This is generally intended for use by the entry menu, not by
        application code. deepcopy is used to return a new copy of the relevent
        profile, not a reference to the original.
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
        with open(PROFILE, 'w') as f:
            yaml.dump(self.profile, f, indent=4, default_flow_style=False)

    def get_status_profile(self):
        """Returns an ordered attribute dictionary with the node profile data.
        This is generally intended for use by the entry menu, not by
        application code. deepcopy is used to return a new copy of the relevent
        profile, not a reference to the original.
        """
        return copy.deepcopy(self.profile.status)

    def update_status_profile(self, profile):
        self.profile.status = profile
        with open(PROFILE, 'w') as f:
            yaml.dump(self.profile, f, indent=4, default_flow_style=False)


class OSinstall(npyscreen.NPSAppManaged):
    def __init__(self, prof_path, on_ok_fns_list, *args, **kwargs):
        super(OSinstall, self).__init__(*args, **kwargs)
        self.prof_path = prof_path
        self.on_ok_fns_list = on_ok_fns_list
        self.prof = Profile(self.prof_path)
        self.log = logger.getlogger()
        # create an Interfaces instance
        self.ifcs = interfaces.Interfaces()
        self.form_flow = (None, 'MAIN', 'NODE', 'STATUS', None)

    def get_form_data(self):
        if self.creating_form == 'MAIN':
            return self.prof.get_network_profile()
        if self.creating_form == 'NODE':
            return self.prof.get_node_profile()
        if self.creating_form == 'STATUS':
            return self.prof.get_status_profile()

    def onStart(self):
        self.creating_form = 'STATUS'
        self.addForm('STATUS', Pup_form, name='Welcome to PowerUP    '
                     'Press F1 for field help')

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
        elif hasattr(prof, 'nodes_finished'):
            finished_count = int(prof['nodes_finished']['val']
                                 .split('/', 1)[0])
            selected_count = int(prof['nodes_finished']['val']
                                 .split('/', 1)[1])
            if finished_count < selected_count:
                msg += [f"Error. Only {prof['nodes_finished']['val']} ",
                        "clients reporting as finished."]
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

        bmc_vlan = prof['bmc_vlan_number'].val
        pxe_vlan = prof['pxe_vlan_number'].val

        conflict_ifc = self.ifcs.is_vlan_used_elsewhere(bmc_vlan, bmc_ethernet_ifc)
        if conflict_ifc and conflict_ifc != (prof['bmc_ethernet_ifc'].val + '.' +
                                             prof['bmc_vlan_number'].val):
            msg += [f'- Error - the chosen BMC vlan ({bmc_vlan}) is already in '
                    f'use on another interface. ({conflict_ifc})']

        conflict_ifc = self.ifcs.is_vlan_used_elsewhere(pxe_vlan, pxe_ethernet_ifc)
        if conflict_ifc and conflict_ifc != (prof['pxe_ethernet_ifc'].val + '.' +
                                             prof['pxe_vlan_number'].val):
            msg += [f'- Error - the chosen PXE vlan ({pxe_vlan}) is already in '
                    f'use on another interface. ({conflict_ifc})']

        ifc = self.ifcs.is_route_overlapping(pxe_cidr, pxe_ethernet_ifc)
        if ifc:
            msg += ['- Error - the subnet specified on the PXE interface',
                    f'  overlaps a subnet on interface {ifc}']

        ifc = self.ifcs.is_route_overlapping(bmc_cidr, bmc_ethernet_ifc)
        if ifc:
            msg += ['- Error - the subnet specified on the BMC interface',
                    f'  overlaps a subnet on interface {ifc}']

        if (u.is_overlapping_addr(bmc_cidr, pxe_cidr) and
                pxe_ethernet_ifc != bmc_ethernet_ifc):
            msg += ['- Warning - BMC and PXE subnets are overlapping.']

        if bmc_subnet_prefix != pxe_subnet_prefix:
            msg += ['- Warning - BMC and PXE subnets are different sizes']

        return msg

    def config_interfaces(self, form_data):
        msg = []
        bmc_ifc = form_data.bmc_ethernet_ifc.val
        bmc_vlan = form_data.bmc_vlan_number.val
        bmc_cidr = form_data.bmc_subnet.val + '/' + \
            form_data.bmc_subnet_prefix.val.split()[-1]

        pxe_ifc = form_data.pxe_ethernet_ifc.val
        pxe_vlan = form_data.pxe_vlan_number.val
        pxe_cidr = form_data.pxe_subnet.val + '/' + \
            form_data.pxe_subnet_prefix.val.split()[-1]

        up_ifcs = self.ifcs.get_up_interfaces_names()
        phys_up_ifcs = self.ifcs.get_up_interfaces_names(_type='phys')

        if bmc_ifc in phys_up_ifcs:
            if bmc_vlan:
                in_use_ifc = self.ifcs.is_vlan_used_elsewhere(bmc_vlan, bmc_ifc)
                if not in_use_ifc or in_use_ifc == bmc_ifc + '.' + bmc_vlan:
                    self.ifcs.create_tagged_ifc(bmc_ifc, bmc_vlan)
                    bmc_ifc = bmc_ifc + '.' + bmc_vlan
            else:
                pass  # non tagged

        else:
            if bmc_ifc not in up_ifcs:
                msg += ['BMC interface is not up']

        if pxe_ifc in phys_up_ifcs:
            if pxe_vlan:
                in_use_ifc = self.ifcs.is_vlan_used_elsewhere(pxe_vlan, pxe_ifc)
                if not in_use_ifc or in_use_ifc == pxe_ifc + '.' + pxe_vlan:
                    self.ifcs.create_tagged_ifc(pxe_ifc, pxe_vlan)
                    pxe_ifc = pxe_ifc + '.' + pxe_vlan
            else:
                pass  # non tagged

        else:
            if pxe_ifc not in up_ifcs:
                msg += ['PXE interface is not up']

        if not self.ifcs.find_unused_addr_and_add_to_ifc(bmc_ifc, bmc_cidr):
            self.log.error(f'Failed to add an addr to {bmc_ifc}')
            msg += f'Failed to add an addr to {bmc_ifc}'
        else:
            # Update form data with new vlan interface
            form_data.bmc_ethernet_ifc.val = bmc_ifc

        if not self.ifcs.find_unused_addr_and_add_to_ifc(pxe_ifc, pxe_cidr):
            self.log.error(f'Failed to add an addr to {pxe_ifc}')
            msg += f'Failed to add an addr to {pxe_ifc}'
        else:
            # Update form data with new vlan interface
            form_data.pxe_ethernet_ifc.val = pxe_ifc

        return msg

    def check_for_existing_dhcp(self, form_data):
        msg = []
        bmc_addrs = self.ifcs.get_interface_addresses(form_data.bmc_ethernet_ifc.val)
        pxe_addrs = self.ifcs.get_interface_addresses(form_data.pxe_ethernet_ifc.val)
        if (form_data.bmc_address_mode.val == 'dhcp' and
                form_data.bmc_ethernet_ifc.val):
            dhcp = u.get_dhcp_servers(form_data.bmc_ethernet_ifc.val)
            if dhcp and dhcp["Server Identifier"] not in bmc_addrs:
                msg += ['- Warning a DHCP server exists already on',
                        '  the interface specified for BMC access. ',
                        f'  Offered address: {dhcp["IP Offered"]}',
                        f'  From server:     {dhcp["Server Identifier"]}']

        dhcp = u.get_dhcp_servers(form_data.pxe_ethernet_ifc.val)
        if dhcp and dhcp["Server Identifier"] not in pxe_addrs:
            msg += ['- Warning a DHCP server exists already on',
                    '  the interface specified for PXE access. ',
                    f'  Offered address: {dhcp["IP Offered"]}',
                    f'  From server:     {dhcp["Server Identifier"]}']

        return msg

    def add_firewall_rules(self, form_data):
        msg = []
        rc = u.firewall_add_services(['http', 'tftp', 'dhcp'])
        if rc != 0:
            msg = "Error\nFailed to configure firewall!"
        return msg

    def install_and_configure_nginx(self, form_data):
        status_dir = CLIENT_STATUS_DIR
        msg = []
        rc = nginx_setup(root_dir=HTTP_ROOT_DIR)
        if rc != 0:
            msg += "ERROR\nFailed to configure nginx!"
            return

        if not os.path.isdir(status_dir):
            os.makedirs(status_dir)
            os.chmod(status_dir, 0o777)
        nginx_location = {f'/client_status/':
                          [f'alias {status_dir}',
                           'dav_methods PUT',
                           'create_full_put_path on',
                           'dav_access user:rw group:rw all:rw',
                           'allow all',
                           'autoindex on']}

        rc = u.nginx_modify_conf('/etc/nginx/conf.d/server1.conf',
                                 locations=nginx_location)
        if rc != 0:
            msg += "ERROR\nFailed to configure nginx!"
            return

    def configure_dnsmasq(self, form_data):
        msg = []
        rc = dnsmasq_configuration(form_data)
        if rc != 0:
            msg += "Error\nFailed to configure dnsmasq!"
        return msg

    def mask_ipv4_field(self, subnet_prefix_field, field, fields, form):
        """ Updates a field specified by ifc_field so that it contains a valid
        subnet for the subnet specified in subnet_field.
        Args:
            subnet_prefix_field(str): A form field corresponding to the subnet mask.
            field(str): The field to mask. (the current field getting smart updated)
            fields(dict): Dictionary holding the pup_form field instances
            form(dict): Dictionary holding the form definition (profile.yml)
        """
        prefix = int(fields[subnet_prefix_field].value.split()[-1])
        msg = ''
        net_addr = u.get_network_addr(fields[field].value, prefix)
        if net_addr != fields[field].value:
            msg = (f'IP addr {fields[field].value} masked by '
                   f'{subnet_prefix_field} to: {net_addr}')
            fields[field].value = net_addr
        return msg

    def get_ifc_from_route(self, subnet_field, subnet_prefix_field, field, fields, form):
        """Updates an eth-ifc field with the appropriate Ethernet Ifc if an interface
        exists which has the specified route.
        """
        cidr = (fields[subnet_field].value + '/' +
                fields[subnet_prefix_field].value.split()[-1])
        if fields[field].value:
            current_ifc = fields[field].values[fields[field].value]
        else:
            current_ifc = ''
        ifc_with_route = self.ifcs.get_interface_for_route(cidr)
        if ifc_with_route:
            ifc = ifc_with_route
            idx = 0
            fields[field].values = [ifc]
            fields[field].value = idx
        else:
            phys_ifcs = self.ifcs.get_up_interfaces_names(_type='phys')
            if current_ifc in phys_ifcs:
                pass
            else:
                idx = None
                ifc = phys_ifcs
                fields[field].values = ifc
                fields[field].value = idx

    def show_if_phys_ifc(self, ifc_field, subnet_field, subnet_prefix_field,
                         field, fields, form):
        """ show a field specified by field, if the interface specified
        in the ifc field value is a physical interface and the subnet
        specified in subnet does not have an existing route out of the box.
        Args:
            ifc_field(str): A form field corresponding to an ethernet interface.
            subnet_field(str): A form field corresponding to an ethernet interface subnet.
            subnet_prefix_field(str): A form field corresponding to the subnet mask.
            field(str): The field to hide. (the current field getting smart updated)
            fields(dict): Dictionary holding the pup_form field instances
            form(dict): Dictionary holding the form definition (profile.yml)
        """
        if fields[ifc_field].value is not None:
            ifc = fields[ifc_field].values[fields[ifc_field].value]
        else:
            ifc = ''

        if fields[subnet_field].value is not None:
            subnet = fields[subnet_field].value
        else:
            subnet = ''

        subnet_prefix = fields[subnet_prefix_field].value.split()[-1]
        subnet_cidr = subnet + '/' + subnet_prefix

        phys_eth_lst = self.ifcs.get_up_interfaces_names(_type='phys')
        routes = self.ifcs.get_interfaces_routes()

        if ifc in phys_eth_lst and subnet_cidr not in routes[ifc]:
            fields[field].hidden = False
        else:
            fields[field].hidden = True
            fields[field].value = ''

    def on_ok_fns(self, fn_to_run, form_data, active_form):
        if active_form == 'MAIN':
            if fn_to_run == 'is_valid_profile':
                msg = self.is_valid_profile(form_data)

            if fn_to_run == 'config_interfaces':
                msg = self.config_interfaces(form_data)

            if fn_to_run == 'check_for_existing_dhcp':
                msg = self.check_for_existing_dhcp(form_data)

            if fn_to_run == 'add_firewall_rules':
                msg = self.add_firewall_rules(form_data)

            if fn_to_run == 'install_and_configure_nginx':
                msg = self.install_and_configure_nginx(form_data)

            if fn_to_run == 'configure_dnsmasq':
                msg = self.configure_dnsmasq(form_data)

        if active_form == 'NODE':
            pass

        return msg


class MyButtonPress(npyscreen.MiniButtonPress):

    def whenPressed(self):
        if self.name == 'Edit network config':
            self.parent.next_form = 'MAIN'
            self.parent.parentApp.switchForm('MAIN')

        elif self.name == 'Scan for nodes':
            self.parent.scan = True
            # self.name = 'Stop node scan'
            # 0.5 sec to initiate scanning in 0.5 s
            self.parent.keypress_timeout = 5

        elif self.name == 'Stop node scan':
            self.parent.scan = False
            self.name = 'Scan for nodes'

        self.parent.display()


class Pup_form(npyscreen.ActionFormV2):
    install_start_time = None
    pxeboot_enabled = False

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
        node_status_path = os.path.join(GEN_PATH, 'osinstall_node_status.yml')
        if os.path.isfile(node_status_path):
            os.remove(node_status_path)

        if hasattr(self.form, 'bmc_userid'):
            self.scan_uid = self.form.bmc_userid.val
            self.scan_pw = self.form.bmc_password.val
        if hasattr(self.form, 'status_table'):
            self.check_install_status = True
        else:
            self.check_install_status = False

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

            if hasattr(self.form[item], 'hidden'):
                hidden = self.form[item]['hidden']
            else:
                hidden = False

            if ftype == 'file':
                if not self.form[item]['val']:
                    self.form[item]['val'] = os.path.join(GEN_PATH,
                                                          'os-images')
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
                eth_lst = self.parentApp.ifcs.get_up_interfaces_names(
                    _type='phys')
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
                    value = self.form[item]['values'].index(
                        self.form[item]['val'])
                else:
                    value = 0
                self.fields[item] = self.add(npyscreen.TitleSelectOne,
                                             name=fname,
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
                self.fields[item] = self.add(npyscreen.TitleMultiSelect,
                                             name=fname,
                                             max_height=10,
                                             value=value,
                                             values=self.form[item]['values'],
                                             scroll_exit=True,
                                             begin_entry_at=20, relx=relx)

            elif 'button' in ftype:
                if ',' in ftype:
                    x = int(self.form[item]['ftype'].lstrip(
                        'button').split(',')[0])
                    y = int(self.form[item]['ftype'].lstrip(
                        'button').split(',')[1])
                self.fields[item] = self.add(MyButtonPress,
                                             name=self.form[item]['desc'],
                                             relx=x,
                                             rely=y)

            elif ftype == 'ftext':
                self.fields[item] = self.add(npyscreen.FixedText,
                                             name=fname,
                                             value=str(self.form[item]['val']),
                                             max_width=self.x - (28 + 2),
                                             relx=28)

            elif ftype == 'tftext':
                self.fields[item] = self.add(npyscreen.TitleFixedText,
                                             name=fname,
                                             value=str(self.form[item]['val']),
                                             max_width=self.x - (28 + 2),
                                             relx=relx)

            elif ftype == 'pager':
                self.fields[item] = self.add(npyscreen.Pager,
                                             name=fname,
                                             values=self.form[item]['values'])

            # no ftype specified therefore Title text
            else:
                self.fields[item] = self.add(npyscreen.TitleText,
                                             name=fname,
                                             value=str(self.form[item]['val']),
                                             hidden=hidden,
                                             begin_entry_at=20, width=40,
                                             relx=relx)

            if hasattr(self.form[item], 'ftype') and \
                    ('button' in self.form[item]['ftype'] or
                     'ftext' in self.form[item]['ftype'] or
                     'pager' in self.form[item]['ftype']):
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
        res = True
        fld_error = False
        msg = []
        for item in self.form:
            if hasattr(self.form[item], 'dtype'):
                if self.form[item]['dtype'] == 'no-save':
                    if item == 'node_list':
                        if len(self.fields[item].value) == 0:
                            msg += [('No nodes selected!\n'
                                    'Exit without installing to any clients?')]
                            res = npyscreen.notify_yes_no(msg, title='Warning',
                                                          editw=1)
                            if res:
                                self.next_form = None
                                sys.exit("Ending OSInstall at user request")
                        else:
                            nodes = {'selected': {}}
                            for index in self.fields[item].value:
                                data = self.fields['node_list'].\
                                    values[index].split()

                                # BMC MAC address as "nodes['selected']" key
                                nodes['selected'][data[2].upper()] = (
                                    {'serial': data[0].upper(),
                                     'model': data[1].upper(),
                                     'bmc_ip': data[3].upper(),
                                     'bmc_type': data[4]})

                            with open(NODE_STATUS, 'w') as f:
                                yaml.dump(nodes, f, indent=4,
                                          default_flow_style=False)
                    continue
                    if item == 'pxeboot_status':
                        if Pup_form.pxeboot_enabled:
                            msg += [('PXE Install is still enabled!\n'
                                    'Exit without disabling?')]
                            res = npyscreen.notify_yes_no(msg, title='Warning',
                                                          editw=1)
                    continue
                elif self.form[item]['dtype'] == 'ipv4':
                    # npyscreen.notify_confirm(f"{self.fields[item].value}",
                    #                          editw=1)
                    if not u.is_ipaddr(self.fields[item].value):
                        fld_error = True
                        msg += [('Invalid ipv4 address: '
                                 f'{self.fields[item].value}')]

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

        if fld_error:
            msg += ['---------------------',
                    'Continue with OS install?',
                    '(No to continue editing the profile data)']

            editw = 1 if len(msg) < 10 else 0
            res = npyscreen.notify_yes_no(msg, title='Profile validation',
                                          editw=editw)

        # Note that the self.parentApp.NEXT_ACTIVE_FORM is actually the
        # current form
        ok_fns_err = False
        if self.parentApp.NEXT_ACTIVE_FORM in ('MAIN',):  # ('MAIN', 'NODE', 'STATUS'):
            on_ok_fns_list = self.parentApp.on_ok_fns_list[self.parentApp.NEXT_ACTIVE_FORM]
            if not fld_error or res:
                popmsg = ''
                for fn in on_ok_fns_list:
                    popmsg += on_ok_fns_list[fn] + '\n'
                    npyscreen.notify(popmsg, title='Info')
                    msg = self.parentApp.on_ok_fns(fn, self.form,
                                                   self.parentApp.NEXT_ACTIVE_FORM)
                    sleep(1)
                    if msg:
                        if 'Error' in ' '.join(msg) or 'ERROR' in ' '.join(msg):
                            msg += ['Please resolve issues before continuing.']
                            npyscreen.notify_confirm(msg, title='cancel', editw=1)
                            ok_fns_err = True
                            break
                        res = False
                        msg += ['---------------------',
                                'Continue with OS install?',
                                '(No to continue editing the profile data)']
                        editw = 1 if len(msg) < 10 else 0
                        res = npyscreen.notify_yes_no(msg, title='Profile validation',
                                                      editw=editw)
                    if not res:
                        break
            if not ok_fns_err and res:
                if self.parentApp.NEXT_ACTIVE_FORM == 'MAIN':
                    self.parentApp.prof.update_network_profile(self.form)
                    self.next_form = 'NODE'

        if res:
            if self.parentApp.NEXT_ACTIVE_FORM == 'NODE':
                self.parentApp.prof.update_node_profile(self.form)
                self.initiate_os_installation()
                self.next_form = 'STATUS'
            elif self.parentApp.NEXT_ACTIVE_FORM == 'STATUS':
                self.parentApp.prof.update_status_profile(self.form)
                self.next_form = None
        else:
            # stay on this form
            self.next_form = self.parentApp.NEXT_ACTIVE_FORM

    def get_mask_and_prefix(self, mask_prefix):
        """ Extracts a mask and prefix from a string containing a mask and / or
            a prefix.
        Args:
            mask_prefix (str): Of the form 'ipmask prefix' or ipmask or prefix
        """
        msg = ''
        mask_prefix = mask_prefix.strip()
        if mask_prefix:
            mask = mask_prefix.split()[0]
            prefix = mask_prefix.split()[-1]
        else:
            msg = ('Neither the netmask or prefix are valid.\n'
                   'Using default netmask and prefix')
            mask = '255.255.255.0'
            prefix = '24'
        prefix_match = re.search(r'^(\d{1,2})\s*$', prefix)

        if u.is_netmask(mask):
            pass
        else:
            mask = None

        if prefix_match:
            try:
                prefix = int(prefix_match.group(1))
                prefix = prefix if 0 < prefix < 33 else None
            except (ValueError, TypeError):
                prefix = None
        else:
            prefix = None

        tmp = u.get_prefix(mask) if mask else 0
        if prefix and mask and prefix != tmp:
            msg = ('The entered mask and prefix do not match. The prefix is '
                   'given precendence. If you wish to enter just a netmask, '
                   'a prefix will be calculated. If you wish to enter just '
                   'a prefix, a netmask will be calulated.')
            mask = u.get_netmask(prefix)
        elif prefix and not mask:
            mask = u.get_netmask(prefix)
        elif mask and not prefix:
            prefix = u.get_prefix(mask)
        elif (not prefix) and not mask:
            msg = ('Neither the netmask or prefix are valid.\n'
                   'Using default netmask and prefix')
            mask = '255.255.255.0'
            prefix = '24'

        if msg:
            npyscreen.notify_confirm(msg, editw=1)
        return mask, prefix

    def write_node_list(self, node_list):
        pass

    def while_waiting(self):
        if self.scan:  # Initiated by button press
            scan_uid = self.fields['bmc_userid'].value
            scan_pw = self.fields['bmc_password'].value
            if scan_uid != self.scan_uid or scan_pw != self.scan_pw:
                self.talking_nodes = {}
                self.fields['node_list'].values = [None]
                self.fields['node_list'].value = []
                self.fields['devices_found'].value = None
                self.fields['bmcs_found'].value = None
                self.scan_uid = scan_uid
                self.scan_pw = scan_pw

            self.keypress_timeout = 100  # set scan loop back to 10 sec
            p = self.parentApp.prof.get_network_profile_tuple()

            msg = ['Attempting to communicate with BMCs']
            npyscreen.notify(msg)
            # basic icmp 'ping' scan. returns (ip, mac)
            nodes = u.scan_subnet(p.bmc_subnet_cidr)
            device_dict = {node[0]: node[1] for node in nodes}

            self.fields['devices_found'].value = str(len(nodes))

            ips = [node[0] for node in nodes]

            nodes = []
            node_dict = {}
            # Access BMCs for serial number and part number
            for port in ('2200', '623'):
                # get list of tuples of (ip, mac)
                _nodes = u.scan_subnet_for_port_open(ips, port)
                if _nodes:
                    nodes += _nodes
                    _ips = [item[0] for item in _nodes]
                    node_dict.update(self._get_bmcs_sn_pn(_ips, scan_uid, scan_pw, port))
                if len(_nodes) == len(ips):
                    break

            if nodes:
                self.fields['bmcs_found'].value = str(len(nodes))
            # Replace any spaces in serial and part number with dashes
            # so that the individual data fields can be later retrieved with a split()
            for _node in node_dict:
                node = list(node_dict[_node])
                node[0] = node[0].replace(' ', '-')
                node[1] = node[1].replace(' ', '-')
                node_dict[_node] = node

            self.display()
            if node_dict:
                for node in node_dict:
                    if node not in self.talking_nodes:
                        self.talking_nodes[node] = (f'{node_dict[node][0]:>16}' +
                                                    f'{node_dict[node][1]:^18}' +
                                                    f'{device_dict[node]:^19} {node:^17}' +
                                                    f'{node_dict[node][2]:^9}')
            field_list = [self.talking_nodes[node] for node in self.talking_nodes]
            field_list = [None] if field_list == [] else field_list
            bmcs_found_cnt = self.fields['bmcs_found'].value

            try:
                bmcs_found_cnt = int(self.fields['bmcs_found'].value)
            except (TypeError, ValueError):
                bmcs_found_cnt = 0
            if len(self.talking_nodes) == bmcs_found_cnt:
                self.scan = False
                self.fields['scan_for_nodes'].name = 'Scan for nodes'
            else:
                self.fields['scan_for_nodes'].name = 'Stop node scan'
            self.display()
            self.fields['node_list'].values = field_list
            self.display()
        elif self.check_install_status:
            self.keypress_timeout = 10  # set scan loop to 1 sec
            self.update_status_values()
            self.display()

    def while_editing(self, instance):
        # instance is the instance of the widget you're moving into
        field = ''
        for item in self.form:
            # lookup field from instance name
            if instance.name == self.form[item].desc:
                field = item
                break
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

            prev_fld_val = self.fields[self.prev_field].value

            if prev_fld_dtype == 'ipv4':
                if not u.is_ipaddr(prev_fld_val):
                    npyscreen.notify_confirm(('Invalid Field value: '
                                              f'{prev_fld_val}'),
                                             title=self.prev_field, editw=1)

            elif prev_fld_dtype == 'ipv4mask':
                mask, prefix = self.get_mask_and_prefix(prev_fld_val)
                if not prefix and not mask:
                    npyscreen.notify_confirm(('Invalid Field value: '
                                              f'{prev_fld_val}'),
                                             title=self.prev_field, editw=1)
                    prefix = 24
                    mask = '255.255.255.0'
                elif prefix:
                    mask = u.get_netmask(prefix)
                else:
                    prefix = u.get_prefix(mask)
                self.fields[self.prev_field].value = f'{mask} {prefix}'

            elif 'int-or-none' in prev_fld_dtype:
                rng = self.form[self.prev_field]['dtype'].\
                    lstrip('int-or-none').split('-')
                if prev_fld_val:
                    prev_fld_val = prev_fld_val.strip(' ')
                if prev_fld_val and prev_fld_val != 'None':
                    try:
                        int(prev_fld_val)
                    except ValueError:
                        npyscreen.notify_confirm("Enter digits 0-9 or enter "
                                                 "'None' or leave blank",
                                                 title=self.prev_field,
                                                 editw=1)
                    else:
                        if (int(prev_fld_val) < int(rng[0]) or
                                int(prev_fld_val) > int(rng[1])):
                            msg = (f'Invalid Field value: {prev_fld_val}. '
                                   'Please leave empty or enter a value '
                                   'between 2 and 4094.')
                            npyscreen.notify_confirm(msg,
                                                     title=self.prev_field,
                                                     editw=1)

            elif 'int' in prev_fld_dtype:
                rng = self.form[self.prev_field]['dtype'].lstrip('int').\
                    split('-')
                if prev_fld_val:
                    try:
                        int(prev_fld_val)
                    except ValueError:
                        npyscreen.notify_confirm(f'Enter digits 0-9',
                                                 title=self.prev_field,
                                                 editw=1)
                    else:
                        if (int(prev_fld_val) < int(rng[0]) or
                                int(prev_fld_val) > int(rng[1])):
                            msg = (f'Invalid Field value: {prev_fld_val}. '
                                   'Please enter a value between 2 and 4094.')
                            npyscreen.notify_confirm(msg,
                                                     title=self.prev_field,
                                                     editw=1)

            elif 'file' in prev_fld_dtype:
                if not os.path.isfile(prev_fld_val):
                    npyscreen.notify_confirm('Specified iso file does not '
                                             f'exist: {prev_fld_val}',
                                             title=self.prev_field, editw=1)
                elif '-iso' in prev_fld_dtype and '.iso' not in prev_fld_val:
                    npyscreen.notify_confirm('Warning, the selected file does '
                                             'not have a .iso extension',
                                             title=self.prev_field, editw=1)
            elif 'eth-ifc' in prev_fld_ftype:
                pass

        for fld_name, fld_data in self.form.items():
            if hasattr(fld_data, 'smart_update'):
                for fn in fld_data.smart_update:
                    args_list = fld_data.smart_update[fn]
                    func_to_call = getattr(self.parentApp, fn)
                    msg = func_to_call(*args_list, fld_name, self.fields, self.form)
                    if msg:
                        npyscreen.notify_confirm(msg, title=fld_name, editw=1)
                    self.display()

        if field:
            self.prev_field = field
            self.display()
        else:
            self.prev_field = ''
        if instance.name not in ['OK', 'Cancel', 'CANCEL',
                                 'Edit network config', 'Scan for nodes',
                                 'Stop node scan', 'node list header']:
            if field:
                self.helpmsg = self.form[field].help
        else:
            self.prev_field = ''

    def h_help(self, char):
        npyscreen.notify_confirm(self.helpmsg, title=self.prev_field, editw=1)

    def h_enter(self, char):
        npyscreen.notify_yes_no(f'Field Error: {self.field}', title='Enter',
                                editw=1)

    def when_press_edit_networks(self):
        self.next_form = 'MAIN'
        self.parentApp.switchForm('MAIN')

    def initiate_os_installation(self):
        notify_title = "Client OS Installation"

        msg = "Extracting files from install image... "
        npyscreen.notify(msg, title=notify_title)
        kernel, initrd = extract_install_image(self.parentApp.prof)

        msg += "done\nGenerate kickstart file... "
        npyscreen.notify(msg, title=notify_title)
        kickstart = render_kickstart(self.parentApp.prof)

        msg += "done\nCopying pup report scripts... "
        npyscreen.notify(msg, title=notify_title)
        copy_pup_report_scripts()

        msg += "done\nGenerate pxelinux configuration... "
        npyscreen.notify(msg, title=notify_title)
        pxelinux_configuration(self.parentApp.prof, kernel, initrd, kickstart)
        Pup_form.pxeboot_enabled = True
        Pup_form.install_start_time = time()

        msg += "done\nPXE boot nodes... "
        npyscreen.notify(msg, title=notify_title)
        initiate_pxeboot(self.parentApp.prof, NODE_STATUS)

        msg += "done\n"

    def _get_bmcs_sn_pn(self, node_list, uid, pw, bmc_type):
        """ Scan the node list for BMCs. Return the sn and pn of nodes which
        responded

        Args:
            node_list(tup or list): Node ipv4 addresses
            bmc_type(str): BMC type, can be 'open' or '2200' for openBMC or
                       '623' or 'ipmi' for ipmi based BMCs
        returns:
            Dictionary. Keys are ip address. Values are tuple containing
                sn, pn, bmc_type
        """
        # create dict to hold Bmc class instances
        bmc_inst = {}
        # list for responding BMCs
        sn_pn_list = {}
        if bmc_type in ('2200', 'openbmc'):
            for ip in node_list:
                this_bmc = Bmc(ip, uid, pw, 'openbmc')
                if this_bmc.is_connected():
                    bmc_inst[ip] = this_bmc
            for ip in bmc_inst:
                sn_pn = bmc_inst[ip].get_system_sn_pn() + ('openbmc',)
                sn_pn_list[ip] = sn_pn

        elif bmc_type in ('623', 'ipmi'):
            for ip in node_list:
                this_bmc = Bmc(ip, uid, pw, 'ipmi')
                if this_bmc.is_connected():
                    bmc_inst[ip] = this_bmc

            # Create dict to hold inventory gathering sub process instances
            sub_proc_instance = {}
            # Start a sub process instance to gather inventory for each node.
            for node in bmc_inst:
                sub_proc_instance[node] = bmc_inst[node].\
                    get_system_inventory_in_background()
            # poll for inventory gathering completion
            st_time = time()
            timeout = 15  # seconds

            while time() < st_time + timeout and len(sn_pn_list) < len(bmc_inst):
                for node in sub_proc_instance:
                    if sub_proc_instance[node].poll() is not None:
                        if (sub_proc_instance[node].poll() == 0 and
                                node not in sn_pn_list):
                            inv, stderr = sub_proc_instance[node].communicate()
                            inv = inv.decode('utf-8')
                            sn_pn_list[node] = bmc_inst[node].\
                                extract_system_sn_pn(inv) + ('ipmi',)

        for node in bmc_inst:
            bmc_inst[node].logout()

        return sn_pn_list

    def update_status_values(self):
        self.fields['installation_image'].value = (
            os.path.basename(
                self.parentApp.prof.get_node_profile_tuple().iso_image_file))

        if Pup_form.pxeboot_enabled:
            self.fields['pxeboot_status'].value = 'Enabled'
        else:
            self.fields['pxeboot_status'].value = 'Disabled'

        if Pup_form.install_start_time is not None:
            self.fields['start_time'].value = (
                strftime("%x %X %Z", localtime(Pup_form.install_start_time)))

        if os.path.isfile(NODE_STATUS):
            node_status = update_install_status(NODE_STATUS,
                                                Pup_form.install_start_time,
                                                write_results=True)

            total_nodes = len(node_status['selected'])
            total_nodes_finished = 0
            other_nodes_finished = 0
            for bmc_mac, node in node_status['selected'].items():
                try:
                    if float(node['finish_time']) > float(node['start_time']):
                        total_nodes_finished += 1
                        reset_bootdev(self.parentApp.prof, NODE_STATUS,
                                      node['bmc_ip'])
                except (KeyError, TypeError):
                    pass
            if 'other' in node_status:
                for bmc_mac, node in node_status['other'].items():
                    try:
                        if (float(node['finish_time']) >
                                float(node['start_time'])):
                            total_nodes_finished += 1
                            other_nodes_finished += 1
                    except (KeyError, TypeError):
                        pass
            self.fields['nodes_finished'].value = (f'{total_nodes_finished} / '
                                                   f'{total_nodes}')
            if total_nodes_finished >= total_nodes:
                reset_bootdev(self.parentApp.prof, NODE_STATUS)
                u.pxelinux_set_local_boot()
                Pup_form.pxeboot_enabled = False
            self.fields['status_table'].values = (
                get_install_status(NODE_STATUS, colorized=False).splitlines())


def main(prof_path):
    log = logger.getlogger()

    try:
        osi = OSinstall(prof_path)
        osi.run()
#        routes = osi.ifcs.get_interfaces_routes()
#        for route in routes:
#            print(f'{route:<12}: {routes[route]}')

#        pro = Profile(prof_path)
#        profile = pro.get_profile()
#        p = pro.get_network_profile_tuple()
#        nodes = u.scan_subnet(p.bmc_subnet_cidr)
#        ips = [node[0] for node in nodes]
#        # code.interact(banner='osinstall.main1',
#        #               local=dict(globals(), **locals()))
#        nodes = u.scan_subnet_for_port_open(ips, 623)
#        ips = [node[0] for node in nodes]
#        n = pro.get_node_profile_tuple()
#        code.interact(banner='osinstall.main2',
#                      local=dict(globals(), **locals()))
#        sn_pn_good_list = _get_bmcs_sn_pn(ips, n.bmc_userid, n.bmc_password)
#        code.interact(banner='osinstall.main4',
#                      local=dict(globals(), **locals()))

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
