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

import os
import xmlrpc.client

import lib.logger as logger
import lib.utilities as util
import lib.genesis as gen

OS_IMAGES_DIR = gen.get_container_os_images_path() + '/'
OS_CONFIG_DIR = OS_IMAGES_DIR + 'config/'

APACHE2_HTML_DIR = '/var/www/html/'
KICKSTARTS_DIR = '/var/lib/cobbler/kickstarts/'
SNIPPETS_DIR = '/var/lib/cobbler/snippets/'
COBBLER_USER = gen.get_cobbler_user()
COBBLER_PASS = gen.get_cobbler_pass()


def extract_iso_images(path, html_dir):
    """Extract ISO images into webserver directory

    Args:
        path (str): Directory path containing ISOs or path to single
                    ISO file
        html_dir (str): Path to root http directory

    Returns:
        list: List of tuples ('str: Extracted image directory name',
                              'str: Relative path to kernel',
                              'str: Relative path to initrd')
    """

    return_list = []

    if os.path.isdir(path):
        if not path.endswith('/'):
            path += '/'
        file_list = os.listdir(path)
    elif os.path.isfile(path):
        file_list = [os.path.basename(path)]
        path = os.path.dirname(path) + '/'

    # Extract ISO into web directory for access over http
    for _file in file_list:
        if _file.endswith('.iso'):
            kernel, initrd = util.extract_iso_image(path + _file, html_dir)
            name = _file[:-4]
            return_list.append((name, kernel, initrd))

    return return_list


def setup_image_config_files(path, html_dir):
    """Setup image config files

    Args:
        path (str): Directory path image config files
        html_dir (str): Path to root http directory
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
    if not os.path.isdir(html_dir + 'ubuntu_sources'):
        os.makedirs(html_dir + 'ubuntu_sources')
    for _file in os.listdir(path):
        if _file.endswith('.list'):
            util.copy_file(path + _file, html_dir + 'ubuntu_sources')


def cobbler_add_distro(name, kernel, initrd):
    """Add distro and profile to Cobbler

    Args:
        name (str): Name of distro/profile
        kernel (str): Path to kernel
        initrd (str): Path to initrd
    """

    log = logger.getlogger()
    name_list = [item.lower() for item in name.split('-')]
    if 'ubuntu' in name_list:
        breed = 'ubuntu'
        for item in name_list:
            if item == 'amd64':
                arch = 'x86_64'
            elif item == 'ppc64el':
                arch = 'ppc64le'
            elif item.startswith('14.04'):
                os_version = 'trusty'
            elif item.startswith('16.04'):
                os_version = 'xenial'
            elif item.startswith('18.04'):
                os_version = 'bionic'
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
            elif item == 'ppc64le':
                arch = 'ppc64le'
            elif item.startswith('7'):
                os_version = 'rhel7'
        kernel_options = "text"
        if os.path.isfile('%s%s.ks' % (KICKSTARTS_DIR, name)):
            kickstart = '%s%s.ks' % (KICKSTARTS_DIR, name)
        else:
            kickstart = '%sRHEL-7-default.ks' % KICKSTARTS_DIR
    else:
        log.info(f'Cobbler distro {name} unrecognized and not added')
        return

    cobbler_server = xmlrpc.client.Server("http://127.0.0.1/cobbler_api")
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

    log.info(f"Cobbler Add Distro: name={name}")
    log.debug(f"name={name} kernel={kernel} initrd{initrd}")

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
    cobbler_server = xmlrpc.client.Server("http://127.0.0.1/cobbler_api")
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

    distros = extract_iso_images(OS_IMAGES_DIR, APACHE2_HTML_DIR)

    setup_image_config_files(OS_CONFIG_DIR, APACHE2_HTML_DIR)

    for distro in distros:
        name = distro[0]
        kernel = os.path.join(APACHE2_HTML_DIR, distro[1])
        initrd = os.path.join(APACHE2_HTML_DIR, distro[2])
        cobbler_add_distro(name, kernel, initrd)

    for _file in os.listdir(OS_CONFIG_DIR):
        if _file.endswith('.seed') or _file.endswith('.ks'):
            profile = _file[:-5]
            distro = _file.rsplit('.', 2)[0]
            if profile != distro and os.path.isdir(APACHE2_HTML_DIR + distro):
                cobbler_add_profile(distro, profile)
