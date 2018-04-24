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
import sys
import pwd
from shutil import copy2
import re
from random import choice
from netaddr import IPNetwork
from git import Repo

from lib.config import Config
import lib.genesis as gen
import lib.utilities as util
import lib.logger as logger


URL = 'https://github.com/cobbler/cobbler.git'
BRANCH = 'release28'

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
INITD = '/etc/init.d/'
APACHE2_CONF = '/etc/apache2/apache2.conf'
MANAGE_DNSMASQ = '/opt/cobbler/cobbler/modules/manage_dnsmasq.py'
COBBLER_DLCONTENT = '/opt/cobbler/cobbler/action_dlcontent.py'
COBBLER_SETTINGS_PY = '/opt/cobbler/cobbler/settings.py'

A2ENCONF = '/usr/sbin/a2enconf'
A2ENMOD = '/usr/sbin/a2enmod'


def cobbler_install():
    """Install and configure Cobbler in container.

    This function must be called within the container 'pup-venv'
    python virtual environment. Cobbler will be installed within
    this environment.
    """

    cfg = Config()
    log = logger.getlogger()

    # Check to see if cobbler is already installed
    try:
        util.bash_cmd('cobbler check')
        log.info("Cobbler is already installed")
        return
    except util.CalledProcessError as error:
        if error.returncode == 127:
            log.debug("'cobbler' command not found, continuing with "
                      "installation")
        else:
            log.warning("Cobbler is installed but not working:")
            log.warning(error.output)
            print("\nPress enter to remove Cobbler and attempt to ")
            print("re-install, or 'T' to terminate.")
            resp = raw_input("\nEnter or 'T': ")
            log.debug("User response = \'{}\'".format(resp))
            if resp == 'T':
                sys.exit('POWER-Up stopped at user request')

    # Clone cobbler github repo
    cobbler_url = URL
    cobbler_branch = BRANCH
    install_dir = gen.get_cobbler_install_dir()
    if os.path.exists(install_dir):
        log.info(
            "Removing Cobbler source directory \'{}\'".format(install_dir))
        util.bash_cmd('rm -rf %s' % install_dir)
    log.info(
        "Cloning Cobbler branch \'%s\' from \'%s\'" %
        (cobbler_branch, cobbler_url))
    repo = Repo.clone_from(
        cobbler_url, install_dir, branch=cobbler_branch, single_branch=True)
    log.info(
        "Cobbler branch \'%s\' cloned into \'%s\'" %
        (repo.active_branch, repo.working_dir))

    # Modify Cobbler scrpit that write DHCP reservations so that the
    #   lease time is included.
    dhcp_lease_time = cfg.get_globals_dhcp_lease_time()
    util.replace_regex(MANAGE_DNSMASQ, 'systxt \= systxt \+ \"\\\\n\"',
                       "systxt = systxt + \",{}\\\\n\"".
                       format(dhcp_lease_time))

    # Use non-secure http to download network boot-loaders
    util.replace_regex(COBBLER_DLCONTENT,
                       'https://cobbler.github.io',
                       'http://cobbler.github.io')

    # Use non-secure http to download signatures
    util.replace_regex(COBBLER_SETTINGS_PY,
                       'https://cobbler.github.io',
                       'http://cobbler.github.io')

    # Run cobbler make install
    util.bash_cmd('cd %s; make install' % install_dir)

    # Backup original files
    util.backup_file(DNSMASQ_TEMPLATE)
    util.backup_file(MODULES_CONF)
    util.backup_file(COBBLER_WEB_SETTINGS)
    util.backup_file(COBBLER_CONF_ORIG)
    util.backup_file(COBBLER_WEB_CONF_ORIG)
    util.backup_file(COBBLER_SETTINGS)
    util.backup_file(PXEDEFAULT_TEMPLATE)
    util.backup_file(KICKSTART_DONE)
    util.backup_file(NTP_CONF)
    util.backup_file(APACHE2_CONF)

    # Create tftp root directory
    if not os.path.exists(TFTPBOOT):
        mode = 0o755
        os.mkdir(TFTPBOOT, mode)

    # Set IP address range to use for unrecognized DHCP clients
    dhcp_range = 'dhcp-range=%s,%s,%s  # %s'
    util.remove_line(DNSMASQ_TEMPLATE, 'dhcp-range')
    dhcp_pool_start = gen.get_dhcp_pool_start()
    for index, netw_type in enumerate(cfg.yield_depl_netw_client_type()):
        depl_netw_client_ip = cfg.get_depl_netw_client_cont_ip(index)
        depl_netw_client_netmask = cfg.get_depl_netw_client_netmask(index)

        network = IPNetwork(depl_netw_client_ip + '/' +
                            depl_netw_client_netmask)

        entry = dhcp_range % (str(network.network + dhcp_pool_start),
                              str(network.network + network.size - 1),
                              str(dhcp_lease_time),
                              str(network.cidr))

        util.append_line(DNSMASQ_TEMPLATE, entry)

        # Save PXE client network information for later
        if netw_type == 'pxe':
            cont_pxe_ipaddr = depl_netw_client_ip
            cont_pxe_netmask = depl_netw_client_netmask
            bridge_pxe_ipaddr = cfg.get_depl_netw_client_brg_ip(index)

    # Configure dnsmasq to enable TFTP server
    util.append_line(DNSMASQ_TEMPLATE, 'enable-tftp')
    util.append_line(DNSMASQ_TEMPLATE, 'tftp-root=%s' % TFTPBOOT)
    util.append_line(DNSMASQ_TEMPLATE, 'user=root')

    # Configure dnsmasq to use deployer as gateway
    if cfg.get_depl_gateway():
        util.remove_line(DNSMASQ_TEMPLATE, 'dhcp-option')
        util.append_line(DNSMASQ_TEMPLATE, 'dhcp-option=3,%s' % bridge_pxe_ipaddr)

    # Cobbler modules configuration
    util.replace_regex(MODULES_CONF, 'module = manage_bind',
                       'module = manage_dnsmasq')
    util.replace_regex(MODULES_CONF, 'module = manage_isc',
                       'module = manage_dnsmasq')

    # Copy cobbler.conf into apache2/conf-available
    copy2(COBBLER_CONF_ORIG, COBBLER_CONF)

    # Copy cobbler_web.conf into apache2/conf-available
    copy2(COBBLER_WEB_CONF_ORIG, COBBLER_WEB_CONF)

    # Apache2 configuration
    util.bash_cmd('%s cobbler cobbler_web' % A2ENCONF)
    util.bash_cmd('%s proxy' % A2ENMOD)
    util.bash_cmd('%s proxy_http' % A2ENMOD)

    # Set secret key in web settings
    secret_key = _generate_random_characters()
    util.replace_regex(COBBLER_WEB_SETTINGS, '^SECRET_KEY = .*',
                       'SECRET_KEY = "%s"' % secret_key)

    # Remove "Order allow,deny" lines from cobbler configuration
    regex = '.*Order allow,deny'
    util.remove_line(COBBLER_CONF, regex)
    util.remove_line(COBBLER_WEB_CONF, regex)

    # Replace "Allow from all" with "Require all granted" in
    regex = 'Allow from all'
    replace = 'Require all granted'
    util.replace_regex(COBBLER_CONF, regex, replace)
    util.replace_regex(COBBLER_WEB_CONF, regex, replace)

    # chown www-data WEBUI_SESSIONS
    uid = pwd.getpwnam("www-data").pw_uid
    gid = -1  # unchanged
    os.chown(WEBUI_SESSIONS, uid, gid)

    # Cobbler settings
    util.replace_regex(COBBLER_SETTINGS, '127.0.0.1', cont_pxe_ipaddr)
    util.replace_regex(COBBLER_SETTINGS, 'manage_dhcp: 0', 'manage_dhcp: 1')
    util.replace_regex(COBBLER_SETTINGS, 'manage_dns: 0', 'manage_dns: 1')
    util.replace_regex(COBBLER_SETTINGS, 'pxe_just_once: 0', 'pxe_just_once: 1')
    globals_env_variables = cfg.get_globals_env_variables()
    if globals_env_variables and 'http_proxy' in globals_env_variables:
        util.replace_regex(COBBLER_SETTINGS, 'proxy_url_ext: ""',
                           'proxy_url_ext: %s' %
                           globals_env_variables['http_proxy'])
    util.replace_regex(COBBLER_SETTINGS, 'default_password_crypted:',
                       'default_password_crypted: '
                       '$1$clusterp$/gd3ep3.36A2808GGdHUz.')

    # Create link to
    if not os.path.exists(PY_DIST_PKGS):
        util.bash_cmd('ln -s %s/cobbler %s' %
                      (LOCAL_PY_DIST_PKGS, PY_DIST_PKGS))

    # Set PXE timeout to maximum
    util.replace_regex(PXEDEFAULT_TEMPLATE, r'TIMEOUT \d+',
                       'TIMEOUT 35996')
    util.replace_regex(PXEDEFAULT_TEMPLATE, r'TOTALTIMEOUT \d+',
                       'TOTALTIMEOUT 35996')

    # Fix line break escape in kickstart_done snippet
    util.replace_regex(KICKSTART_DONE, "\\\\nwget", "wget")
    util.replace_regex(KICKSTART_DONE, "\$saveks", "$saveks + \"; \\\\\\\"\n")
    util.replace_regex(KICKSTART_DONE, "\$runpost", "$runpost + \"; \\\\\\\"\n")

    # Copy authorized_keys ssh key file to web repo directory
    copy2(ROOT_AUTH_KEYS, WWW_AUTH_KEYS)
    os.chmod(WWW_AUTH_KEYS, 0o444)

    # Add mgmt subnet to NTP service configuration
    cont_pxe_broadcast = str(
        IPNetwork(cont_pxe_ipaddr + '/' + cont_pxe_netmask).broadcast)
    util.append_line(NTP_CONF, 'broadcast %s' % cont_pxe_broadcast)

    # Add 'required-stop' line to cobblerd init.d to avoid warning
    util.replace_regex(INITD + 'cobblerd', '### END INIT INFO',
                       '# Required-Stop:\n### END INIT INFO')

    # Set Apache2 'ServerName'
    util.append_line(APACHE2_CONF, "ServerName localhost")

    # Restart services
    _restart_service('ntp')
    _restart_service('cobblerd')
    _restart_service('apache2')

    # Update Cobbler boot-loader files
    util.bash_cmd('%s get-loaders' % COBBLER)

    # Update cobbler list of OS signatures
    util.bash_cmd('%s signature update' % COBBLER)

    # Run Cobbler sync
    util.bash_cmd('%s sync' % COBBLER)

    # Restart services (again)
    _restart_service('apache2')
    _restart_service('cobblerd')
    _restart_service('dnsmasq')

    # Set services to start on boot
    _service_start_on_boot('cobblerd')
    _service_start_on_boot('ntp')


def _restart_service(service):
    util.bash_cmd('service %s restart' % service)


def _service_start_on_boot(service):
    util.replace_regex(INITD + service,
                       '# Default-Start:.*',
                       '# Default-Start: 2 3 4 5')
    util.replace_regex(INITD + service,
                       '# Default-Stop:.*',
                       '# Default-Stop: 0 1 6')
    util.bash_cmd('update-rc.d %s defaults' % service)


def _generate_random_characters(length=100):
    characters = "abcdefghijklmnopqrstuvwxyz0123456789^&*(-_=+)"
    return re.escape("".join([choice(characters) for _ in range(length)]))


if __name__ == '__main__':
    logger.create()
    cobbler_install()
