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

import subprocess
import os
import pwd
from shutil import copy2
import re
from random import choice
import fileinput
from netaddr import IPNetwork
from git import Repo

from lib.config import Config
import lib.logger as logger


INSTALL_DIR = '/opt/cobbler'
URL = 'https://github.com/cobbler/cobbler.git'
BRANCH = 'release28'

DHCP_POOL_START = 150
DHCP_POOL_SIZE = 50

PXE = 'pxe'
GEN_VENV = '/opt/cluster-genesis/gen-venv/'

TFTPBOOT = '/tftpboot'
DNSMASQ_TEMPLATE = '/etc/cobbler/dnsmasq.template'
MODULES_CONF = '/etc/cobbler/modules.conf'
COBBLER_CONF_ORIG = '/etc/cobbler/cobbler.conf'
COBBLER_CONF = '/etc/apache2/conf-available/cobbler.conf'
COBBLER_WEB_CONF_ORIG = '/etc/cobbler/cobbler_web.conf'
COBBLER_WEB_CONF = '/etc/apache2/conf-available/cobbler_web.conf'
COBBLER_WEB_SETTINGS = '/usr/local/share/cobbler/web/settings.py'
WEBUI_SESSIONS = '/var/lib/cobbler/webui_sessions'
COBBLER_SETTINGS = '/etc/cobbler/settings'
PXEDEFAULT_TEMPLATE = '/etc/cobbler/pxe/pxedefault.template'
KICKSTART_DONE = '/var/lib/cobbler/snippets/kickstart_done'
ROOT_AUTH_KEYS = '/root/.ssh/authorized_keys'
WWW_AUTH_KEYS = '/var/www/html/authorized_keys'
NTP_CONF = '/etc/ntp.conf'
COBBLER = '/usr/local/bin/cobbler'
LOCAL_PY_DIST_PKGS = '/usr/local/lib/python2.7/dist-packages'
PY_DIST_PKGS = '/usr/lib/python2.7/dist-packages'

A2ENCONF = '/usr/sbin/a2enconf'
A2ENMOD = '/usr/sbin/a2enmod'


def cobbler_install():
    """Install and configure Cobbler in container.

    This function must be called within the container 'gen-venv'
    python virtual environment. Cobbler will be installed within
    this environment.
    """

    cfg = Config()
    log = logger.getlogger()

    # Clone cobbler github repo
    cobbler_url = URL
    cobbler_branch = BRANCH
    log.info(
        "Cloning Cobbler branch \'%s\' from \'%s\'" %
        (cobbler_branch, cobbler_url))
    repo = Repo.clone_from(
        cobbler_url, INSTALL_DIR, branch=cobbler_branch, single_branch=True)
    log.info(
        "Cobbler branch \'%s\' cloned into \'%s\'" %
        (repo.active_branch, repo.working_dir))

    # Run cobbler make install
    _bash_cmd('cd %s; make install' % INSTALL_DIR)

    # Backup original files
    _backup_file(DNSMASQ_TEMPLATE)
    _backup_file(MODULES_CONF)
    _backup_file(COBBLER_WEB_SETTINGS)
    _backup_file(COBBLER_CONF_ORIG)
    _backup_file(COBBLER_WEB_CONF_ORIG)
    _backup_file(COBBLER_SETTINGS)
    _backup_file(PXEDEFAULT_TEMPLATE)
    _backup_file(KICKSTART_DONE)
    _backup_file(NTP_CONF)

    # Create tftp root directory
    mode = 0o755
    os.mkdir(TFTPBOOT, mode)

    # Set IP address range to use for unrecognized DHCP clients
    dhcp_range = 'dhcp-range=%s,%s'
    _remove_line(DNSMASQ_TEMPLATE, 'dhcp-range')
    for index, netw_type in enumerate(cfg.yield_depl_netw_client_type()):
        depl_netw_client_ip = cfg.get_depl_netw_client_cont_ip(index)
        depl_netw_client_netmask = cfg.get_depl_netw_client_netmask(index)

        network = IPNetwork(depl_netw_client_ip + '/' +
                            depl_netw_client_netmask)

        entry = dhcp_range % (
            (str(network.network + DHCP_POOL_START)),
            (str(network.network + DHCP_POOL_START + DHCP_POOL_SIZE)))

        _append_line(DNSMASQ_TEMPLATE, entry)

        # Save PXE client network information for later
        if netw_type == PXE:
            cont_pxe_ipaddr = depl_netw_client_ip
            cont_pxe_netmask = depl_netw_client_netmask
            bridge_pxe_ipaddr = cfg.get_depl_netw_client_brg_ip(index)

    # Configure dnsmasq to enable TFTP server
    _append_line(DNSMASQ_TEMPLATE, 'enable-tftp')
    _append_line(DNSMASQ_TEMPLATE, 'tftp-root=%s' % TFTPBOOT)
    _append_line(DNSMASQ_TEMPLATE, 'user=root')

    # Configure dnsmasq to use deployer as gateway
    if cfg.get_depl_gateway():
        _replace_regex(DNSMASQ_TEMPLATE, '\$next_server', bridge_pxe_ipaddr)

    # Cobbler modules configuration
    _replace_regex(MODULES_CONF, 'module = manage_bind',
                   'module = manage_dnsmasq')
    _replace_regex(MODULES_CONF, 'module = manage_isc',
                   'module = manage_dnsmasq')

    # Copy cobbler.conf into apache2/conf-available
    copy2(COBBLER_CONF_ORIG, COBBLER_CONF)

    # Copy cobbler_web.conf into apache2/conf-available
    copy2(COBBLER_WEB_CONF_ORIG, COBBLER_WEB_CONF)

    # Apache2 configuration
    _bash_cmd('%s cobbler cobbler_web' % A2ENCONF)
    _bash_cmd('%s proxy' % A2ENMOD)
    _bash_cmd('%s proxy_http' % A2ENMOD)

    # Set secret key in web settings
    secret_key = _generate_random_characters()
    _replace_regex(COBBLER_WEB_SETTINGS, '^SECRET_KEY = .*',
                   'SECRET_KEY = "%s"' % secret_key)

    # Remove "Order allow,deny" lines from cobbler configuration
    regex = '.*Order allow,deny'
    _remove_line(COBBLER_CONF, regex)
    _remove_line(COBBLER_WEB_CONF, regex)

    # Replace "Allow from all" with "Require all granted" in
    regex = 'Allow from all'
    replace = 'Require all granted'
    _replace_regex(COBBLER_CONF, regex, replace)
    _replace_regex(COBBLER_WEB_CONF, regex,
                   replace)

    # chown www-data WEBUI_SESSIONS
    uid = pwd.getpwnam("www-data").pw_uid
    gid = -1  # unchanged
    os.chown(WEBUI_SESSIONS, uid, gid)

    # Cobbler settings
    _replace_regex(COBBLER_SETTINGS, '127.0.0.1', cont_pxe_ipaddr)
    _replace_regex(COBBLER_SETTINGS, 'manage_dhcp: 0', 'manage_dhcp: 1')
    _replace_regex(COBBLER_SETTINGS, 'manage_dns: 0', 'manage_dns: 1')
    _replace_regex(COBBLER_SETTINGS, 'pxe_just_once: 0', 'pxe_just_once: 1')
    globals_env_variables = cfg.get_globals_env_variables()
    if globals_env_variables and 'http_proxy' in globals_env_variables:
        _replace_regex(COBBLER_SETTINGS, 'proxy_url_ext: ""',
                       'proxy_url_ext: %s' %
                       globals_env_variables['http_proxy'])

    # Create link to
    _bash_cmd('ln -s %s/cobbler %s' % (LOCAL_PY_DIST_PKGS, PY_DIST_PKGS))

    # Set PXE timeout to maximum
    _replace_regex(PXEDEFAULT_TEMPLATE, r'TIMEOUT \d+',
                   'TIMEOUT 35996')
    _replace_regex(PXEDEFAULT_TEMPLATE, r'TOTALTIMEOUT \d+',
                   'TOTALTIMEOUT 35996')

    # Fix line break escape in kickstart_done snippet
    _replace_regex(KICKSTART_DONE, "\\\\nwget", "wget")
    _replace_regex(KICKSTART_DONE, "\$saveks", "$saveks + \"; \\\\\\\"\n")
    _replace_regex(KICKSTART_DONE, "\$runpost", "$runpost + \"; \\\\\\\"\n")

    # Copy authorized_keys ssh key file to web repo directory
    copy2(ROOT_AUTH_KEYS, WWW_AUTH_KEYS)
    os.chmod(WWW_AUTH_KEYS, 0o444)

    # Add mgmt subnet to NTP service configuration
    cont_pxe_broadcast = str(
        IPNetwork(cont_pxe_ipaddr + '/' + cont_pxe_netmask).broadcast)
    _append_line(NTP_CONF, 'broadcast %s' % cont_pxe_broadcast)

    # Restart services
    _restart_service('ntp')
    _restart_service('cobblerd')
    _restart_service('apache2')

    # Update Cobbler boot-loader files
    _bash_cmd('%s get-loaders' % COBBLER)

    # Update cobbler list of OS signatures
    _bash_cmd('%s signature update' % COBBLER)

    # Run Cobbler sync
    _bash_cmd('%s sync' % COBBLER)

    # Restart services (again)
    _restart_service('apache2')
    _restart_service('cobblerd')
    _restart_service('dnsmasq')

    # Set services to start on boot
    _service_start_on_boot('cobblerd')
    _service_start_on_boot('ntp')


def _bash_cmd(cmd):
    log = logger.getlogger()
    command = ['bash', '-c', cmd]
    log.debug('Run subprocess: %s' % ' '.join(command))
    output = subprocess.check_output(command, universal_newlines=True)
    log.debug(output)


def _restart_service(service):
    _bash_cmd('service %s restart' % service)


def _service_start_on_boot(service):
    _bash_cmd('update-rc.d %s enable' % service)


def _backup_file(path):
    log = logger.getlogger()
    backup_path = path + '.orig'
    log.debug('Make backup copy of orignal file: \'%s\'' % backup_path)
    copy2(path, backup_path)
    os.chmod(backup_path, 0o444)


def _append_line(path, line):
    log = logger.getlogger()
    log.debug('Add line \'%s\' to file \'%s\'' % (line, path))
    if not line.endswith('\n'):
        line += '\n'
    with open(path, 'a') as file_out:
        file_out.write(line)


def _remove_line(path, regex):
    log = logger.getlogger()
    log.debug('Remove lines containing regex \'%s\' from file \'%s\'' %
              (regex, path))
    for line in fileinput.input(path, inplace=1):
        if not re.match(regex, line):
            print(line, end='')


def _replace_regex(path, regex, replace):
    log = logger.getlogger()
    log.debug('Replace regex \'%s\' with \'%s\' in file \'%s\'' %
              (regex, replace, path))
    for line in fileinput.input(path, inplace=1):
        print(re.sub(regex, replace, line), end='')


def _generate_random_characters(length=100):
    characters = "abcdefghijklmnopqrstuvwxyz0123456789^&*(-_=+)"
    return re.escape("".join([choice(characters) for _ in range(length)]))


if __name__ == '__main__':
    logger.create()
    cobbler_install()
