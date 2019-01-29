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
import argparse
import xmlrpc.client
import re

from lib.inventory import Inventory
import lib.genesis as gen
import lib.logger as logger


def cobbler_add_systems(cfg_file=None):
    LOG = logger.getlogger()

    cobbler_user = gen.get_cobbler_user()
    cobbler_pass = gen.get_cobbler_pass()
    cobbler_server = xmlrpc.client.Server("http://127.0.0.1/cobbler_api")
    token = cobbler_server.login(cobbler_user, cobbler_pass)

    inv = Inventory(cfg_file=cfg_file)

    for index, hostname in enumerate(inv.yield_nodes_hostname()):
        ipv4_ipmi = inv.get_nodes_ipmi_ipaddr(0, index)
        userid_ipmi = inv.get_nodes_ipmi_userid(index)
        password_ipmi = inv.get_nodes_ipmi_password(index)
        ipv4_pxe = inv.get_nodes_pxe_ipaddr(0, index)
        mac_pxe = inv.get_nodes_pxe_mac(0, index)
        cobbler_profile = gen.check_os_profile(
            re.sub("[.]iso", "", inv.get_nodes_os_profile(index)))
        raid1_enabled = False

        new_system_create = cobbler_server.new_system(token)

        cobbler_server.modify_system(
            new_system_create,
            "name",
            hostname,
            token)
        cobbler_server.modify_system(
            new_system_create,
            "hostname",
            hostname,
            token)
        cobbler_server.modify_system(
            new_system_create,
            "power_address",
            ipv4_ipmi,
            token)
        cobbler_server.modify_system(
            new_system_create,
            "power_user",
            userid_ipmi,
            token)
        cobbler_server.modify_system(
            new_system_create,
            "power_pass",
            password_ipmi,
            token)
        cobbler_server.modify_system(
            new_system_create,
            "power_type",
            "ipmilan",
            token)
        cobbler_server.modify_system(
            new_system_create,
            "profile",
            cobbler_profile,
            token)
        cobbler_server.modify_system(
            new_system_create,
            'modify_interface',
            {
                "macaddress-eth0": mac_pxe,
                "ipaddress-eth0": ipv4_pxe,
                "dnsname-eth0": hostname},
            token)
        ks_meta = ""
        disks = inv.get_nodes_os_install_device(index)
        if disks is not None:
            if isinstance(disks, str):
                ks_meta += 'install_disk=%s ' % disks
            elif isinstance(disks, list) and len(disks) == 2:
                ks_meta += (
                    'install_disk=%s install_disk_2=%s ' %
                    (disks[0], disks[1]))
                raid1_enabled = True
            else:
                LOG.error(
                    '%s: Invalid install_device value: %s '
                    'Must be string or two item list.' %
                    (hostname, disks))
        if raid1_enabled:
            ks_meta += 'raid1_enabled=true '
        domain = inv.get_nodes_os_domain(index)
        if domain is not None:
            ks_meta += 'domain=%s ' % domain
        users = inv.get_nodes_os_users(index)
        if users is not None:
            for user in users:
                if 'name' in user and user['name'] != 'root':
                    ks_meta += 'default_user=%s ' % user['name']
                    LOG.debug("%s: Using \'%s\' as default user" %
                              (hostname, user['name']))
                    if 'password' in user:
                        ks_meta += ('passwd=%s passwdcrypted=true ' %
                                    user['password'])
                    break
            else:
                LOG.debug("%s: No default user found" % hostname)
        else:
            LOG.debug("%s: No users defined" % hostname)
        if ks_meta != "":
            cobbler_server.modify_system(
                new_system_create,
                "ks_meta",
                ks_meta,
                token)
        kernel_options = inv.get_nodes_os_kernel_options(index)
        if 'ubuntu-18.04' in cobbler_profile.lower():
            if kernel_options is None:
                kernel_options = ''
            if 'netcfg/do_not_use_netplan=true' not in kernel_options:
                kernel_options += ' netcfg/do_not_use_netplan=true'
        if kernel_options is not None:
            cobbler_server.modify_system(
                new_system_create,
                "kernel_options",
                kernel_options,
                token)
            cobbler_server.modify_system(
                new_system_create,
                "kernel_options_post",
                kernel_options,
                token)
        comment = ""
        cobbler_server.modify_system(
            new_system_create,
            "comment",
            comment,
            token)

        cobbler_server.save_system(new_system_create, token)

        LOG.info(
            "Cobbler Add System: name=%s, profile=%s" %
            (hostname, cobbler_profile))

    cobbler_server.sync(token)
    LOG.info("Running Cobbler sync")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('config_path', default='config.yml',
                        help='Config file path.  Absolute path or relative '
                        'to power-up/')

    parser.add_argument('--print', '-p', dest='log_lvl_print',
                        help='print log level', default='info')

    parser.add_argument('--file', '-f', dest='log_lvl_file',
                        help='file log level', default='info')

    args = parser.parse_args()

    logger.create(args.log_lvl_print, args.log_lvl_file)

    if not os.path.isfile(args.config_path):
        args.config_path = gen.GEN_PATH + args.config_path
        print('Using config path: {}'.format(args.config_path))
    if not os.path.isfile(args.config_path):
        sys.exit('{} does not exist'.format(args.config_path))

    cobbler_add_systems(args.config_path)
