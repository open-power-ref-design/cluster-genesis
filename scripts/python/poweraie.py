#! /usr/bin/env python
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

import argparse
import os
import sys
import time
import yaml
import code
import lib.logger as logger
from repos import local_epel_repo, remote_nginx_repo
from software_hosts import get_ansible_inventory
from lib.utilities import sub_proc_display, sub_proc_exec
from lib.genesis import GEN_SOFTWARE_PATH


class software(object):
    """ Software installation class. The setup method is used to setup
    repositories, download files to the installer node or perform other
    initialization activities. The install method implements the actual
    installation.
    """
    def __init__(self):
        self.log = logger.getlogger()
        self.yum_powerup_repo_files = []
        try:
            self.sw_vars = yaml.load(open(GEN_SOFTWARE_PATH + 'software-vars.yml'))
        except IOError:
            self.log.info('Creating software vars yaml file')
            self.sw_vars = {}
            self.sw_vars['init-time'] = time.ctime()
        else:
            if not isinstance(self.sw_vars, dict):
                self.sw_vars = {}
        self.epel_repo_name = 'epel-ppc64le'
        self.sw_vars['epel_repo_name'] = self.epel_repo_name
        self.rhel_ver = '7'
        self.sw_vars['rhel_ver'] = self.rhel_ver
        self.arch = 'ppc64le'
        self.sw_vars['arch'] = self.arch

        self.log.debug(f'software variables: {self.sw_vars}')

    def __del__(self):
        with open(GEN_SOFTWARE_PATH + 'software-vars.yml', 'w') as f:
            yaml.dump(self.sw_vars, f, default_flow_style=False)

    def setup(self):
        # Get Anaconda
        if not os.path.exists('/srv/anaconda'):
            os.mkdir('/srv/anaconda')
        if not os.path.isfile('/srv/anaconda/Anaconda2-5.1.0-Linux-ppc64le.sh'):
            self.log.info('Downloading Anaconda')
            cmd = ('wget https://repo.continuum.io/archive/Anaconda2-5.1.0-Linux-'
                   'ppc64le.sh --directory-prefix=/srv/anaconda/')
            stat = sub_proc_display(cmd)
            if stat == 0:
                self.log.info('Anaconda downloaded succesfully')
            else:
                self.log.error('Failed to download Anaconda')
        else:
            self.log.info('Anaconda already downloaded')

        # Get PowerAI base
        if not os.path.exists('/srv/powerai-rpm'):
            os.mkdir('/srv/powerai-rpm')
        if not os.path.isfile('/srv/powerai-rpm/mldl-repo-local-5.1.0-201804110899'
                              '.fd91856.ppc64le.rpm'):
            self.log.info('Downloading PowerAI base')
            cmd = ('wget --directory-prefix=/srv/powerai-rpm http://ausgsa.ibm.com'
                   '/projects/m/mldl-repo/releases/v1r5m1/rhel/mldl-repo-local-5.1.'
                   '0-201804110899.fd91856.ppc64le.rpm')
            stat = sub_proc_display(cmd)
            if stat == 0:
                self.log.info('PowerAI base downloaded succesfully')
            else:
                self.log.error('Failed to download PowerAI base')
        else:
            self.log.info('PowerAI base already downloaded')

        r = ' '
        if os.path.isfile('/etc/yum.repos.d/epel-ppc64le.repo'):
            print('\nDo you want to sync the local EPEL repository at this time')
            print('This can take a few minutes.  (Enter "f" to sync and force'
                  'recreation of yum .repo files)')
            while r not in 'Ynf':
                r = input('Enter Y/n/f: ')

            if r in 'Yf':
                repo = local_epel_repo()
                if r == 'f':
                    repo_url = repo.yum_create_remote()
                    self.sw_vars['epel_repo_url'] = repo_url
                    repo.create_dirs()

                repo.sync()

                if r == 'f':
                    repo.create_meta()
                    repo.yum_create_local()
                    self.yum_powerup_repo_files.append(repo.get_yum_client_powerup())

        if not os.path.isfile('/etc/yum.repos.d/epel-ppc64le.repo'):
            print('\nDo you want to create a local EPEL repsoitory at this time?')
            print('This can take a significant amount of time')
            while r not in 'Yn':
                r = input('Enter Y/n: ')
            if r == 'Y':
                repo = local_epel_repo()
                repo.yum_create_remote()
                repo.create_dirs()
                repo.sync()
                repo.create_meta()
                repo.yum_create_local()
                self.yum_powerup_repo_files.append(repo.get_yum_client_powerup())

        # self.log.debug(self.yum_powerup_repo_files[0]['filename'])
        # self.log.debug(self.yum_powerup_repo_files[0]['content'])

        # Setup firewall to allow http
        fw_err = 0
        cmd = 'systemctl status firewalld.service'
        resp, err, rc = sub_proc_exec(cmd)
        if 'Active: active (running)' in resp.splitlines()[2]:
            self.log.debug('Firewall is running')
        else:
            cmd = 'systemctl enable firewalld.service'
            resp, err, rc = sub_proc_exec(cmd)
            if rc != 0:
                fw_err += 1
                self.log.error('Failed to enable firewall')

            cmd = 'systemctl start firewalld.service'
            resp, err, rc = sub_proc_exec(cmd)
            if rc != 0:
                fw_err += 10
                self.log.error('Failed to start firewall')
        cmd = 'firewall-cmd --permanent --add-service=http'
        resp, err, rc = sub_proc_exec(cmd)
        if rc != 0:
            fw_err += 100
            self.log.error('Failed to enable http service on firewall')

        cmd = 'firewall-cmd --reload'
        resp, err, rc = sub_proc_exec(cmd)
        if 'success' not in resp:
            fw_err += 1000
            self.log.error('Error attempting to restart firewall')
        if fw_err == 0:
            self.log.info('Firewall is running and configured for http')

        nginx_repo = remote_nginx_repo()
        nginx_repo.yum_create_remote()

        # Check if nginx installed. Install if necessary.
        cmd = 'nginx -v'
        try:
            resp, err, rc = sub_proc_exec(cmd)
            print('nginx is installed:\n{}'.format(resp))
        except OSError:
            # if 'nginx version' in err:
            cmd = 'yum -y install nginx'
            resp, err, rc = sub_proc_exec(cmd)
            if rc != 0:
                self.log.error('Failed installing nginx')
                self.log.error(resp)
                sys.exit(1)
            else:
                # Fire it up
                cmd = 'nginx'
                resp, err, rc = sub_proc_exec(cmd)
                if rc != 0:
                    self.log.error('Failed starting nginx')
                    self.log.error('resp: {}'.format(resp))
                    self.log.error('err: {}'.format(err))

        cmd = 'curl -I 127.0.0.1'
        resp, err, rc = sub_proc_exec(cmd)
        if 'HTTP/1.1 200 OK' in resp:
            self.log.info('nginx is running:\n')

        print('Good to go')

    def install(self):
        cmd = 'ansible-playbook -i {} /home/user/power-up/playbooks/install_software.yml'.format(get_ansible_inventory())
        resp, err, rc = sub_proc_exec(cmd)
        print(resp)
        cmd = 'ssh -t -i ~/.ssh/gen root@10.0.20.22 /opt/DL/license/bin/accept-powerai-license.sh'
        resp = sub_proc_display(cmd)
        print(resp)
        print('All done')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['setup', 'install'],
                        help='Action to take: setup or install')

    parser.add_argument('--print', '-p', dest='log_lvl_print',
                        help='print log level', default='info')

    parser.add_argument('--file', '-f', dest='log_lvl_file',
                        help='file log level', default='info')

    args = parser.parse_args()

    logger.create(args.log_lvl_print, args.log_lvl_file)

    soft = software()

    if args.action == 'setup':
        soft.setup()
    elif args.action == 'install':
        soft.install()
