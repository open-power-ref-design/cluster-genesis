#!/usr/bin/env python
# Copyright 2018 IBM Corp.
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

from __future__ import nested_scopes, generators, division, absolute_import, \
    with_statement, print_function, unicode_literals

import xmlrpclib

from lib.inventory import Inventory
import lib.logger as logger

COBBLER_USER = 'cobbler'
COBBLER_PASS = 'cobbler'

INV_IPV4_IPMI = 'ipv4-ipmi'
INV_USERID_IPMI = 'userid-ipmi'
INV_PASSWORD_IPMI = 'password-ipmi'
INV_OS_NAME = 'name'
INV_OS_PASSWORD = 'password'
INV_IPV4_PXE = 'ipv4-pxe'
INV_MAC_PXE = 'mac-pxe'
INV_CHASSIS_PART_NUMBER = 'chassis-part-number'
INV_CHASSIS_SERIAL_NUMBER = 'chassis-serial-number'
INV_MODEL = 'model'
INV_SERIAL_NUMBER = 'serial-number'
INV_TEMPLATE = 'template'

INV_NODES_TEMPLATES = 'node-templates'
INV_COBBLER_PROFILE = 'cobbler-profile'
INV_OS_DISK = 'os-disk'
INV_ARCH = 'architecture'
INV_KOPTS = 'kernel-options'


def cobbler_add_systems():
    LOG = logger.getlogger()

    cobbler_server = xmlrpclib.Server("http://127.0.0.1/cobbler_api")
    token = cobbler_server.login(COBBLER_USER, COBBLER_PASS)

    inv = Inventory()

    for index, hostname in enumerate(inv.yield_nodes_hostname()):
        ipv4_ipmi = inv.get_nodes_ipmi_ipaddr(0, index)
        userid_ipmi = inv.get_nodes_ipmi_userid(index)
        password_ipmi = inv.get_nodes_ipmi_password(index)
        ipv4_pxe = inv.get_nodes_pxe_ipaddr(0, index)
        mac_pxe = inv.get_nodes_pxe_mac(0, index)
        cobbler_profile = inv.get_nodes_os_profile(index)
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
            if isinstance(disks, basestring):
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
        users = inv.get_nodes_os_users(index)
        if users is not None:
            for user in users:
                if INV_OS_NAME in user and user[INV_OS_NAME] != 'root':
                    ks_meta += 'default_user=%s ' % user[INV_OS_NAME]
                    LOG.debug("%s: Using \'%s\' as default user" %
                              (hostname, user[INV_OS_NAME]))
                    if INV_OS_PASSWORD in user:
                        ks_meta += ('passwd=%s passwdcrypted=true ' %
                                    user[INV_OS_PASSWORD])
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
        if kernel_options is not None:
            cobbler_server.modify_system(
                new_system_create,
                "kernel_options",
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
    logger.create()

    cobbler_add_systems()
