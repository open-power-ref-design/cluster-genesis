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
import glob
import os
import re
import sys
import shutil
import time
import yaml
import code

import lib.logger as logger
from repos import PowerupRepo, PowerupRepoEpel, RemoteNginxRepo, setup_source_file
from software_hosts import get_ansible_inventory
from lib.utilities import sub_proc_display, sub_proc_exec, heading1, \
    get_selection, get_yesno, rlinput
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
                self.sw_vars['init-time'] = time.ctime()
        if 'yum_powerup_repo_files' not in self.sw_vars:
            self.sw_vars['yum_powerup_repo_files'] = []
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
        ana_src = 'Anaconda2-[56].[1-9]*-Linux-ppc64le.sh'
        # root dir is /srv/
        ana_dir = 'anaconda'
        heading1('Set up Anaconda repository')
        setup_source_file(ana_src, ana_dir)

        # Setup EPEL
        heading1('Set up ppc64le EPEL repository')
        baseurl = 'https://mirrors.fedoraproject.org/metalink?repo=epel-7&arch=ppc64le'
        gpgkey = 'file:///etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-7'
        repo_id = 'epel-ppc64le'
        repo_name = 'Extra Packages for Enterprise Linux 7 - ppc64le'
        if 'epel_alt_url' in self.sw_vars:
            alt_url = self.sw_vars['epel_alt_url']
        else:
            alt_url = None

        new = True
        if os.path.isfile(f'/etc/yum.repos.d/{repo_id}.repo'):
            new = False
            print(f'\nDo you want to sync the {repo_name}\nrepository at this time?')
            print('This can take a few minutes.\n')
            items = 'Yes,no,Sync repository and Force recreation of yum ".repo" files'
            ch, item = get_selection(items, 'Y,n,F', sep=',')
        else:
            print('\nDo you want to create the {repo_name} repository at this time?')
            print('This can take a significant amount of time')
            ch = get_yesno(yesno='Y/n')

        if ch in 'YF':
            #url = repo_url if repo_url else baseurl
            repo = PowerupRepo(repo_id, repo_name, baseurl, alt_url, gpgkey)
            if new or ch == 'F':
                alt_url = repo.yum_create_remote(metalink=True)
                self.sw_vars[f'{repo_id}_alt_url'] = alt_url
                repo.create_dirs()

            repo.sync()
            repo.create_meta()

            if new or ch == 'F':
                repo.yum_create_local()
                tmp = repo.get_yum_powerup_client()
                if tmp not in self.sw_vars['yum_powerup_repo_files']:
                    self.sw_vars['yum_powerup_repo_files'].append(tmp)

        sys.exit('Bye from EPEL')


        # Setup CUDA
        heading1('Set up CUDA Toolkit repository')

        baseurl = 'http://developer.download.nvidia.com/compute/cuda/repos/rhel7/ppc64le'
        gpgkey = f'{baseurl}/7fa2af80.pub'
        repo_id = 'cuda'
        repo_name = 'CUDA Toolkit'
        if 'cuda_alt_url' in self.sw_vars:
            alt_url = self.sw_vars['cuda_alt_url']
        else:
            alt_url = None

        new = True
        if os.path.isfile(f'/etc/yum.repos.d/{repo_id}.repo'):
            new = False
            print('\nDo you want to sync the local CUDA repository at this time?')
            print('This can take a few minutes.\n')
            items = 'Yes,no,Sync repository and Force recreation of yum ".repo" files'
            ch, item = get_selection(items, 'Y,n,F', sep=',')
        else:
            print('\nDo you want to create a local CUDA repository at this time?')
            print('This can take a significant amount of time')
            ch = get_yesno(yesno='Y/n')

        if ch in 'YF':
            #url = repo_url if repo_url else baseurl
            repo = PowerupRepo(repo_id, repo_name, baseurl, alt_url, gpgkey)
            if new or ch == 'F':
                alt_url = repo.yum_create_remote()
                self.sw_vars[f'{repo_id}_alt_url'] = alt_url
                repo.create_dirs()

            repo.sync()
            repo.create_meta()

            if new or ch == 'F':
                repo.yum_create_local()
                tmp = repo.get_yum_powerup_client()
                if tmp not in self.sw_vars['yum_powerup_repo_files']:
                    self.sw_vars['yum_powerup_repo_files'].append(tmp)

        sys.exit('Bye from CUDA')

        # Get PowerAI base
        heading1('Setting up the PowerAI base repository')
        pai_src = 'mldl-repo-local-[56].[1-9]*.ppc64le.rpm'
        pai_dir = 'powerai-rpm'
        ver = ''
        src_installed, src_path = setup_source_file(pai_src, pai_dir, 'PowerAI')
        ver = re.search(r'\d+\.\d+\.\d+', src_path).group(0) if src_path else ''
        self.log.debug(f'PowerAI source path: {src_path}')
        cmd = f'rpm -ihv --test --ignorearch {src_path}'
        resp1, err1, rc = sub_proc_exec(cmd)
        cmd = f'diff /opt/DL/repo/rpms/repodata/ /srv/repos/DL-{ver}/repo/rpms/repodata/'
        resp2, err2, rc = sub_proc_exec(cmd)
        if 'is already installed' in err1 and resp2 == '' and rc == 0:
            repo_installed = True
        else:
            repo_installed = False

        # Create the repo and copy it to /srv directory
        if src_path:
            if not ver:
                self.log.error('Unable to find the version in {src_path}')
                ver = rlinput('Enter a version to use (x.y.z): ', '5.1.0')
            # First check if already installed
            if repo_installed:
                print(f'\nRepository for {src_path} already exists')
                print('in the POWER-Up software server.\n')
                r = get_yesno('Do you wish to recreate the repository')

            if not repo_installed or r == 'yes':
                cmd = f'rpm -ihv  --force --ignorearch {src_path}'
                rc = sub_proc_display(cmd)
                if rc != 0:
                    self.log.info('Failed creating PowerAI repository')
                    self.log.info(f'Failing cmd: {cmd}')
                else:
                    shutil.rmtree(f'/srv/repos/DL-{ver}', ignore_errors=True)
                    try:
                        shutil.copytree('/opt/DL', f'/srv/repos/DL-{ver}')
                    except shutil.Error as exc:
                        print(f'Copy error: {exc}')
                    else:
                        self.log.info('Successfully created PowerAI repository')
        else:
            if src_installed:
                self.log.debug('PowerAI source file already in place and no '
                               'update requested')
            else:
                self.log.error('PowerAI base was not installed.')

        if ver:
            dot_repo = {}
            dot_repo['filename'] = f'powerai-{ver}.repo'
            dot_repo['content'] = (f'[powerai-{ver}]\n'
                                   f'name=PowerAI-{ver}-powerup\n'
                                   'baseurl=http://{host}/repos/'
                                   f'DL-{ver}/repo/rpms\n'
                                   'enabled=1\n'
                                   'gpgkey=http://{host}/repos/'
                                   f'DL-{ver}/repo/mldl-public-key.asc\n'
                                   'gpgcheck=0\n')
            if dot_repo not in self.sw_vars['yum_powerup_repo_files']:
                self.sw_vars['yum_powerup_repo_files'].append(dot_repo)

        sys.exit('Bye from powerai')

        # Setup EPEL repo
        heading1('Local EPEL repository')
        if 'epel_repo_url' in self.sw_vars:
            repo_url = self.sw_vars['epel_repo_url']
        else:
            repo_url = None

        r = ' '
        if os.path.isfile('/etc/yum.repos.d/epel-ppc64le.repo'):
            print('\nDo you want to sync the local EPEL repository at this time?')
            print('This can take a few minutes.  (Enter "f" to sync and force\n'
                  'recreation of yum .repo files)\n')
            while r not in 'Ynf':
                r = input('Enter Y/n/f: ')

            if r in 'Yf':
                repo = local_epel_repo()
                if r == 'f':
                    repo_url = repo.yum_create_remote(repo_url)
                    self.sw_vars['epel_repo_url'] = repo_url
                    repo.create_dirs()

                # repo.sync()

                if r == 'f':
                    repo.create_meta()
                    repo.yum_create_local()
                    tmp = repo.get_yum_powerup_client()
                    if tmp not in self.sw_vars['yum_powerup_repo_files']:
                        self.sw_vars['yum_powerup_repo_files'].append(tmp)

        if not os.path.isfile('/etc/yum.repos.d/epel-ppc64le.repo'):
            print('\nDo you want to create a local EPEL repository at this time?')
            print('This can take a significant amount of time')
            while r not in 'Yn':
                r = input('Enter Y/n: ')
            if r == 'Y':
                repo = local_epel_repo()
                repo_url = repo.yum_create_remote(repo_url)
                self.sw_vars['epel_repo_url'] = repo_url
                repo.create_dirs()
                repo.sync()
                # repo.create_meta()
                repo.yum_create_local()
                tmp = repo.get_yum_powerup_client()
                if tmp not in self.sw_vars['yum_powerup_repo_files']:
                    self.sw_vars['yum_powerup_repo_files'].append(tmp)

        # Setup firewall to allow http
        heading1('Setting up firewall')
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

        nginx_repo = RemoteNginxRepo()
        nginx_repo.yum_create_remote()

        # Check if nginx installed. Install if necessary.
        heading1('Set up Nginx')
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
