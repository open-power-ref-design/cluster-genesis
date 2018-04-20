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

import os
import xmlrpclib

import lib.logger as logger
import lib.utilities as util
import lib.genesis as gen

OS_IMAGES_DIR = gen.get_container_os_images_path() + '/'
OS_CONFIG_DIR = OS_IMAGES_DIR + 'config/'

HTML_DIR = '/var/www/html/'
KICKSTARTS_DIR = '/var/lib/cobbler/kickstarts/'
SNIPPETS_DIR = '/var/lib/cobbler/snippets/'
COBBLER_USER = gen.get_cobbler_user()
COBBLER_PASS = gen.get_cobbler_pass()


def extract_iso_images(path):
    """Extract ISO images into webserver directory
    Args:
        path (str): Directory path containing ISOs

    Returns:
        list: Paths to extracted ISO images
    """

    return_list = []

    if not path.endswith('/'):
        path += '/'

    # Extract ISO into web directory for access over http
    for _file in os.listdir(path):
        if _file.endswith('.iso'):
            name = os.path.splitext(_file)[0]
            dest_dir = HTML_DIR + name

            # If dest dir already exists continue to next file
            if not os.path.isdir(dest_dir):
                os.mkdir(dest_dir)
                util.bash_cmd('xorriso -osirrox on -indev %s -extract / %s' %
                              ((path + _file), dest_dir))
                util.bash_cmd('chmod 755 $(find %s -type d)' % dest_dir)

            # Do not return paths to "mini" isos
            if not _file.endswith('mini.iso'):
                return_list.append(dest_dir)

    # Ubuntu ppc64el before 16.04.2 requires files from netboot mini iso
    for _file in os.listdir(path):
        if _file.endswith('mini.iso'):
            src_dir = (HTML_DIR + _file[:-4] +
                       '/install/')
            dest_dir = (HTML_DIR + _file[:-9] +
                        '/install/netboot/ubuntu-installer/ppc64el/')
            if not os.path.isdir(dest_dir):
                os.makedirs(dest_dir)
            for netboot_file in os.listdir(src_dir):
                util.copy_file(src_dir + netboot_file, dest_dir)

    return return_list


def setup_image_config_files(path):
    """Setup image config files
    Args:
        path (str): Directory path image config files
    """

    if not path.endswith('/'):
        path += '/'

    # Update preseed configurations with default user id

    # Copy preseed & kickstart files to cobbler kickstart directory
    for _file in os.listdir(path):
        if _file.endswith('.ks') or _file.endswith('.seed'):
            util.copy_file(path + _file, KICKSTARTS_DIR)

    # Copy custom snippets to cobbler snippets directory
    snippets_src_dir = path + 'snippets/'
    for _file in os.listdir(snippets_src_dir):
        util.copy_file(snippets_src_dir + _file, SNIPPETS_DIR)

    # Copy apt source lists to web repo directory
    if not os.path.isdir(HTML_DIR + 'ubuntu_sources'):
        os.makedirs(HTML_DIR + 'ubuntu_sources')
    for _file in os.listdir(path):
        if _file.endswith('.list'):
            util.copy_file(path + _file, HTML_DIR + 'ubuntu_sources')


def cobbler_add_distro(path, name):
    """Add distro and profile to Cobbler
    Args:
        path (str): Path to OS image files
        name (str): Name of distro/profile
    """

    log = logger.getlogger()
    name_list = [item.lower() for item in name.split('-')]

    if 'ubuntu' in name_list:
        breed = 'ubuntu'
        for item in name_list:
            if item == 'amd64':
                arch = 'x86_64'
                kernel = (
                    "%s/install/netboot/ubuntu-installer/amd64/linux" %
                    path)
                initrd = (
                    "%s/install/netboot/ubuntu-installer/amd64/initrd.gz" %
                    path)
            elif item == 'ppc64el':
                arch = 'ppc64le'
                kernel = (
                    "%s/install/netboot/ubuntu-installer/ppc64el/vmlinux"
                    % path)
                initrd = (
                    "%s/install/netboot/ubuntu-installer/ppc64el/initrd.gz"
                    % path)
            elif item.startswith('14.04'):
                os_version = 'trusty'
            elif item.startswith('16.04'):
                os_version = 'xenial'
        kernel_options = (
            "netcfg/dhcp_timeout=1024 "
            "netcfg/choose_interface=auto "
            "ipv6.disable=1")
        if os.path.isfile('%s%s.seed' % (KICKSTARTS_DIR, name)):
            kickstart = '%s%s.seed' % (KICKSTARTS_DIR, name)
        else:
            kickstart = '%subuntu-default.seed' % KICKSTARTS_DIR

    elif ('centos' in name_list) or ('rhel' in name_list):
        breed = 'redhat'
        for item in name_list:
            if item == 'x86_64':
                arch = 'x86_64'
                kernel = "%s/images/pxeboot/vmlinuz" % path
                initrd = "%s/images/pxeboot/initrd.img" % path
            elif item == 'ppc64le':
                arch = 'ppc64le'
                kernel = "%s/ppc/ppc64/vmlinuz" % path
                initrd = "%s/ppc/ppc64/initrd.img" % path
            elif item.startswith('7'):
                os_version = 'rhel7'
        kernel_options = "text"
        if os.path.isfile('%s%s.ks' % (KICKSTARTS_DIR, name)):
            kickstart = '%s%s.ks' % (KICKSTARTS_DIR, name)
        else:
            kickstart = '%sRHEL-7-default.ks' % KICKSTARTS_DIR

    elif 'introspection' in name_list:
        breed = 'redhat'  # use default since there is no "buildroot" breed
        os_version = ''
        arch = 'ppc64le'
        kernel = "%s/vmlinux" % path
        initrd = "%s/rootfs.cpio.gz" % path
        kernel_options = ''
        kickstart = ''

    cobbler_server = xmlrpclib.Server("http://127.0.0.1/cobbler_api")
    token = cobbler_server.login(COBBLER_USER, COBBLER_PASS)

    new_distro_create = cobbler_server.new_distro(token)
    cobbler_server.modify_distro(
        new_distro_create,
        "name",
        name,
        token)
    cobbler_server.modify_distro(
        new_distro_create,
        "arch",
        arch,
        token)
    cobbler_server.modify_distro(
        new_distro_create,
        "kernel",
        kernel,
        token)
    cobbler_server.modify_distro(
        new_distro_create,
        "initrd",
        initrd,
        token)
    cobbler_server.modify_distro(
        new_distro_create,
        "breed",
        breed,
        token)
    cobbler_server.modify_distro(
        new_distro_create,
        "os_version",
        os_version,
        token)
    cobbler_server.modify_distro(
        new_distro_create,
        "kernel_options",
        kernel_options,
        token)
    cobbler_server.save_distro(new_distro_create, token)

    log.info(
        "Cobbler Add Distro: name=%s, path=%s" %
        (name, path))

    new_profile_create = cobbler_server.new_profile(token)
    cobbler_server.modify_profile(
        new_profile_create,
        "name",
        name,
        token)
    cobbler_server.modify_profile(
        new_profile_create,
        "distro",
        name,
        token)
    cobbler_server.modify_profile(
        new_profile_create,
        "enable_menu",
        "True",
        token)
    cobbler_server.modify_profile(
        new_profile_create,
        "kickstart",
        kickstart,
        token)
    cobbler_server.save_profile(new_profile_create, token)

    log.info(
        "Cobbler Add Profile: name=%s, distro=%s" %
        (name, name))

    cobbler_server.sync(token)
    log.info("Running Cobbler sync")


def cobbler_add_profile(distro, name):
    log = logger.getlogger()
    cobbler_server = xmlrpclib.Server("http://127.0.0.1/cobbler_api")
    token = cobbler_server.login(COBBLER_USER, COBBLER_PASS)

    distro_list = cobbler_server.get_distros()
    existing_distro_list = []
    for existing_distro in distro_list:
        existing_distro_list.append(existing_distro['name'])

    if distro not in existing_distro_list:
        log.warning(
            "Cobbler Skipping Profile - Distro Unavailable: "
            "name=%s, distro=%s" %
            (name, distro))
        return

    new_profile_create = cobbler_server.new_profile(token)
    cobbler_server.modify_profile(
        new_profile_create,
        "name",
        name,
        token)
    cobbler_server.modify_profile(
        new_profile_create,
        "distro",
        distro,
        token)
    cobbler_server.modify_profile(
        new_profile_create,
        "enable_menu",
        "True",
        token)
    cobbler_server.modify_profile(
        new_profile_create,
        "kickstart",
        "/var/lib/cobbler/kickstarts/%s.seed" % name,
        token)
    cobbler_server.save_profile(new_profile_create, token)

    log.info(
        "Cobbler Add Profile: name=%s, distro=%s" %
        (name, distro))

    cobbler_server.sync(token)
    log.info("Running Cobbler sync")


if __name__ == '__main__':
    logger.create()

    distros = extract_iso_images(OS_IMAGES_DIR)

    setup_image_config_files(OS_CONFIG_DIR)

    for distro in distros:
        cobbler_add_distro(distro, os.path.basename(distro))

    for _file in os.listdir(OS_CONFIG_DIR):
        if _file.endswith('.seed') or _file.endswith('.ks'):
            profile = _file[:-5]
            distro = _file.rsplit('.', 2)[0]
            if profile != distro and os.path.isdir(HTML_DIR + distro):
                cobbler_add_profile(distro, profile)
