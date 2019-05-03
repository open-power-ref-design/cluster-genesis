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

GEN_PATH = get_package_path()
GEN_SAMPLE_CONFIGS_PATH = get_sample_configs_path()

IPR = IPRoute()

PROFILE = os.path.join(GEN_PATH, 'profile.yml')
NODE_STATUS = os.path.join(GEN_PATH, 'osinstall_node_status.yml')

HTTP_ROOT_DIR = get_nginx_root_dir()
OSINSTALL_HTTP_DIR = 'osinstall'
CLIENT_STATUS_DIR = '/var/pup_install_status/'


def osinstall(profile_path):
    log = logger.getlogger()
    log.debug('osinstall')

    osi = OSinstall(profile_path)
    osi.run()


def dnsmasq_configuration(profile_object):
    p = profile_object.get_network_profile_tuple()
    dhcp_start = 21
    dhcp_lease_time = '5m'
    if (p.bmc_address_mode == 'static' or
            p.bmc_ethernet_ifc == p.pxe_ethernet_ifc):
        interfaces = p.pxe_ethernet_ifc
    else:
        interfaces = (p.bmc_ethernet_ifc + ',' + p.pxe_ethernet_ifc)

    pxe_network = IPNetwork(p.pxe_subnet_cidr)
    dhcp_pxe_ip_range = (str(pxe_network.network + dhcp_start) + ',' +
                         str(pxe_network.network + pxe_network.size - 1))

    rc = u.dnsmasq_config_pxelinux(interface=interfaces,
                                   dhcp_range=dhcp_pxe_ip_range,
                                   lease_time=dhcp_lease_time)

    if rc != 0:
        return rc

    if p.bmc_address_mode == 'dhcp':
        bmc_network = IPNetwork(p.bmc_subnet_cidr)
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

        j2_vars = {'default_user': 'rhel75',
                   'default_pass': 'passw0rd',
                   'pass_crypted': False,
                   'install_disk': None,
                   'domain': 'localdomain',
                   'timezone': 'America/Chicago',
                   'utc': True,
                   }

        pxe_network = IPNetwork(p_netw.pxe_subnet_cidr)
        j2_vars['http_server'] = ip_route_get_to(str(pxe_network.ip))

        j2_vars['http_repo_name'] = image_name
        j2_vars['http_repo_dir'] = os.path.join(http_osinstall,
                                                j2_vars['http_repo_name'])

        j2_vars['hostname'] = p_node.hostname

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


def initiate_pxeboot(profile_object, node_dict_file):
    log = logger.getlogger()
    p_node = profile_object.get_node_profile_tuple()
    nodes = yaml.full_load(open(node_dict_file))
    for node in nodes['selected'].values():
        ip = node['bmc_ip']
        userid = p_node.bmc_userid
        passwd = p_node.bmc_password
        bmc = Bmc(ip, userid, passwd)
        if bmc.is_connected():
            log.debug(f"Successfully connected to BMC: host={ip} "
                      f"userid={userid} password={passwd}")
            bmc.chassis_power('off')
            bmc.host_boot_source(source='network')
            bmc.chassis_power('on')
        else:
            log.error(f"Unable to connect to BMC: host={ip} "
                      f"userid={userid} password={passwd}")


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
              'Host IP Address', 'OS Info', f'Install Status{endc}']]
    for bmc_mac, value in nodes['selected'].items():
        color = None
        pxe_ip = _try_dict_key(value, 'pxe_ip')
        os_pretty_name = _try_dict_key(value, 'report_data', 'PRETTY_NAME')
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
                      os_pretty_name, install_status])
        if colorized and color is not None:
            table[-1][0] = color + table[-1][0]
            table[-1][-1] = table[-1][-1] + u.Color.endc
    if 'other' in nodes:
        for pxe_ip, value in nodes['other'].items():
            color = None
            os_pretty_name = _try_dict_key(value, 'report_data', 'ID') + " "
            os_pretty_name += _try_dict_key(value, 'report_data', 'VERSION_ID')
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
            table.append(['?', '?', '?', pxe_ip, os_pretty_name,
                          install_status])
            if colorized and color is not None:
                table[-1][0] = color + table[-1][0]
                table[-1][-1] = table[-1][-1] + u.Color.endc

    return tabulate(table, headers="firstrow")


def reset_bootdev(profile_object, node_dict_file, bmc_ip='all'):
    log = logger.getlogger()
    p_node = profile_object.get_node_profile_tuple()
    nodes = yaml.full_load(open(node_dict_file))
    for node in nodes['selected'].values():
        ip = node['bmc_ip']
        userid = p_node.bmc_userid
        passwd = p_node.bmc_password
        if bmc_ip == 'all' or bmc_ip == ip:
            bmc = Bmc(ip, userid, passwd)
            if bmc.is_connected():
                log.debug(f"Successfully connected to BMC: host={ip} "
                          f"userid={userid} password={passwd}")
                bmc.host_boot_source(source='disk')
            else:
                log.error(f"Unable to connect to BMC: host={ip} "
                          f"userid={userid} password={passwd}")


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
            self.profile = yaml.load(open(self.prof_path),
                                     Loader=AttrDictYAMLLoader)
        except IOError:
            self.log.error('Unable to open the profile file: '
                           f'{self.prof_path}')
            sys.exit(f'Unable to open the profile file: {self.prof_path}\n'
                     'Unable to continue with OS install')

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
    def __init__(self, prof_path, *args, **kwargs):
        super(OSinstall, self).__init__(*args, **kwargs)
        self.prof_path = prof_path
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
            if not self.ifcs.is_vlan_used_elsewhere(p.bmc_vlan_number,
                                                    bmc_ifc):
                self.ifcs.create_tagged_ifc(p.bmc_ethernet_ifc,
                                            p.bmc_vlan_number)

        if p.pxe_vlan_number:
            pxe_ifc = p.pxe_ethernet_ifc + '.' + p.pxe_vlan_number
            if not self.ifcs.is_vlan_used_elsewhere(p.pxe_vlan_number,
                                                    pxe_ifc):
                self.ifcs.create_tagged_ifc(p.pxe_ethernet_ifc,
                                            p.pxe_vlan_number)

        if not self.ifcs.find_unused_addr_and_add_to_ifc(bmc_ifc,
                                                         p.bmc_subnet_cidr):
            self.log.error(f'Failed to add an addr to {bmc_ifc}')

        if not self.ifcs.find_unused_addr_and_add_to_ifc(pxe_ifc,
                                                         p.pxe_subnet_cidr):
            self.log.error(f'Failed to add an addr to {pxe_ifc}')

#            cmd = f'nmap -PR {p.bmc_subnet_cidr}'
#            res, err, rc = u.sub_proc_exec(cmd)
#            if rc != 0:
#                self.log.error('An error occurred while scanning the BMC '
#                               'subnet')
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
#                self.log.error('Error occurred removing route from '
#                               f'{bmc_ifc}')


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

        if hasattr(self.form, 'status_table'):
            self.update_status_values()

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
        val_error = False
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
                                    values[index].split(', ')

                                # BMC MAC address as "nodes['selected']" key
                                nodes['selected'][data[2].upper()] = (
                                    {'serial': data[0].upper(),
                                     'model': data[1].upper(),
                                     'bmc_ip': data[3].upper()})

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
                    res = npyscreen.notify_yes_no(msg,
                                                  title='Profile validation',
                                                  editw=editw)

                if res:
                    if self.parentApp.NEXT_ACTIVE_FORM == 'MAIN':
                        self.parentApp.prof.update_network_profile(self.form)
                        self.next_form = 'NODE'
                        self.configure_services()
                    elif self.parentApp.NEXT_ACTIVE_FORM == 'NODE':
                        self.parentApp.prof.update_node_profile(self.form)
                        self.initiate_os_installation()
                        self.next_form = 'STATUS'
                    elif self.parentApp.NEXT_ACTIVE_FORM == 'STATUS':
                        self.parentApp.prof.update_status_profile(self.form)
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

            nodes = u.scan_subnet(p.bmc_subnet_cidr)
            node_dict = {node[0]: node[1] for node in nodes}

            self.fields['devices_found'].value = str(len(nodes))

            ips = [node[0] for node in nodes]

            nodes = u.scan_subnet_for_port_open(ips, 623)
            ips = [node[0] for node in nodes]
            self.fields['bmcs_found'].value = str(len(nodes))

            node_list = self._get_bmcs_sn_pn(ips, scan_uid, scan_pw)
            self.display()
            if node_list:
                for node in node_list:
                    if node not in self.talking_nodes:
                        self.talking_nodes[node] = (node_list[node] +
                                                    (node_dict[node], node))
            field_list = [', '.join(self.talking_nodes[node])
                          for node in self.talking_nodes]
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
        # npyscreen.notify_confirm(
        #         f'field: {field} prev field: {self.prev_field}', editw=1)
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
                    npyscreen.notify_confirm(('Invalid Field value: '
                                              f'{prev_fld_val}'),
                                             title=self.prev_field, editw=1)
                else:
                    if prev_fld_lnkd_flds:
                        prefix = int(self.fields[prev_fld_lnkd_flds.prefix].
                                     value.split()[-1])

                        net_addr = u.get_network_addr(prev_fld_val, prefix)
                        if net_addr != prev_fld_val:
                            npyscreen.notify_confirm(('IP addr modified to: '
                                                      f'{net_addr}'),
                                                     title=self.prev_field,
                                                     editw=1)
                            self.fields[self.prev_field].value = net_addr
                            self.display()

                        cidr = (prev_fld_val + '/' +
                                self.fields[prev_fld_lnkd_flds.prefix].
                                value.split()[-1])
                        ifc = self.parentApp.ifcs.get_interface_for_route(cidr)
                        # npyscreen.notify_confirm(f'ifc: {ifc}', editw=1)
                    if not ifc:
                        ifc = self.parentApp.ifcs.\
                            get_up_interfaces_names(_type='phys')
                    else:
                        ifc = [ifc]
                    if ifc:
                        self.fields[self.form[
                            self.prev_field]['lnkd_flds']['ifc']].values = ifc
                        idx = 0 if len(ifc) == 1 else None
                        self.fields[self.form[
                            self.prev_field]['lnkd_flds']['ifc']].value = idx
                        self.display()

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
                self.display()

                if prev_fld_lnkd_flds:
                    # get the ip address from the linked field
                    cidr = (self.fields[prev_fld_lnkd_flds.subnet].value +
                            '/' +
                            self.fields[self.prev_field].value.split()[-1])
                    # npyscreen.notify_confirm(f'cidr: {cidr}', editw=1)
                    ifc = self.parentApp.ifcs.get_interface_for_route(cidr)
                    if not ifc:
                        ifc = self.parentApp.ifcs.get_up_interfaces_names(
                            _type='phys')
                    else:
                        ifc = [ifc]
                    if ifc:
                        self.fields[self.form[
                            self.prev_field]['lnkd_flds']['ifc']].values = ifc
                        idx = 0 if len(ifc) == 1 else None
                        self.fields[self.form[
                            self.prev_field]['lnkd_flds']['ifc']].value = idx
                        self.display()

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

        if field:
            self.prev_field = field
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

    def configure_services(self):
        notify_title = "Configuring Services"
        status_dir = CLIENT_STATUS_DIR

        msg = "Adding firewall rules... "
        npyscreen.notify(msg, title=notify_title)
        rc = u.firewall_add_services(['http', 'tftp', 'dhcp'])
        if rc != 0:
            msg += "ERROR\nFailed to configure firewall!"
            npyscreen.notify_confirm(msg, title=notify_title, editw=1)
            self.next_form = None
            return

        msg += "done\nInstall and configure nginx... "
        npyscreen.notify(msg, title=notify_title)
        rc = nginx_setup(root_dir=HTTP_ROOT_DIR)
        if rc != 0:
            msg += "ERROR\nFailed to configure nginx!"
            npyscreen.notify_confirm(msg, title=notify_title, editw=1)
            self.next_form = None
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
            npyscreen.notify_confirm(msg, title=notify_title, editw=1)
            self.next_form = None
            return

        msg += "done\nConfigure dnsmasq... "
        npyscreen.notify(msg, title=notify_title)
        rc = dnsmasq_configuration(self.parentApp.prof)
        if rc != 0:
            msg += "ERROR\nFailed to configure dnsmasq!"
            npyscreen.notify_confirm(msg, title=notify_title, editw=1)
            self.next_form = None
            return
        msg += "done\n"
        npyscreen.notify(msg, title=notify_title)
        sleep(1)

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

    def _get_bmcs_sn_pn(self, node_list, uid, pw):
        """ Scan the node list for BMCs. Return the sn and pn of nodes which
        responded

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
                            extract_system_sn_pn(inv)

        for node in bmc_inst:
            bmc_inst[node].logout()

        return sn_pn_list

    def update_status_values(self):
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


def validate(profile_tuple):
    LOG = logger.getlogger()
    if profile_tuple.bmc_address_mode == "dhcp" or (
            profile_tuple.pxe_address_mode == "dhcp"):
        hasDhcpServers = u.has_dhcp_servers(profile_tuple.ethernet_port)
        if not hasDhcpServers:
            LOG.warn("No Dhcp servers found on {0}".format(
                profile_tuple.ethernet_port))
        else:
            LOG.info("Dhcp servers found on {0}".format(
                profile_tuple.ethernet_port))


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
