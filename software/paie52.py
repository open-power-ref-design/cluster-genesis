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
import platform
import re
import sys
from shutil import copy2, Error
import time
import yaml
import code

import lib.logger as logger
from repos import PowerupRepo, PowerupRepoFromDir, PowerupRepoFromRepo, \
    PowerupRepoFromRpm, setup_source_file, PowerupFileFromDisk
from software_hosts import get_ansible_inventory
from lib.utilities import sub_proc_display, sub_proc_exec, heading1, get_url, \
    get_selection, get_yesno, get_dir, get_file_path, get_src_path, rlinput
from lib.genesis import GEN_SOFTWARE_PATH, get_ansible_playbook_path, \
    get_playbooks_path
from lib.exception import UserException


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
            self.sw_vars['yum_powerup_repo_files'] = {}
        self.epel_repo_name = 'epel-ppc64le'
        self.sw_vars['epel_repo_name'] = self.epel_repo_name
        self.rhel_ver = '7'
        self.sw_vars['rhel_ver'] = self.rhel_ver
        self.arch = 'ppc64le'
        self.sw_vars['arch'] = self.arch

        self.log.debug(f'software variables: {self.sw_vars}')

    def __del__(self):
        if not os.path.exists(GEN_SOFTWARE_PATH):
            os.mkdir(GEN_SOFTWARE_PATH)
        with open(GEN_SOFTWARE_PATH + 'software-vars.yml', 'w') as f:
            yaml.dump(self.sw_vars, f, default_flow_style=False)

    def setup(self):
        # Basic check of the state of yum repos
        print()
        self.log.info('Performing basic check of yum repositories')
        cmd = 'yum repolist --noplugins'
        resp, err, rc = sub_proc_exec(cmd)
        yum_err = re.search(r'\[Errno\s+\d+\]', err)
        if rc:
            self.log.error(f'Failure running "yum repolist" :{rc}')
        elif yum_err:
            self.log.error(err)
            self.log.error(f'yum error: {yum_err.group(0)}')
        if rc or yum_err:
            self.log.error('There is a problem with yum or one or more of the yum '
                           'repositories. \n')
            self.log.info('Trying clean of yum caches')
            cmd = 'yum clean all'
            resp, err, rc = sub_proc_exec(cmd)
            if rc != 0:
                sys.log.error('An error occurred while cleaning the yum repositories\n'
                              'POWER-Up is unable to continue.')
                sys.exit('Exiting')

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

        baseurl = 'http://nginx.org/packages/mainline/rhel/7/' + \
                  platform.machine()
        repo_id = 'nginx'
        repo_name = 'nginx.org public'
        heading1(f'Set up {repo_name} repository')
        repo = PowerupRepo(repo_id, repo_name)
        content = repo.get_yum_dotrepo_content(baseurl, gpgcheck=0)
        repo.write_yum_dot_repo_file(content)

        # Check if nginx installed. Install if necessary.
        heading1('Set up Nginx')
        cmd = 'nginx -v'
        try:
            resp, err, rc = sub_proc_exec(cmd)
        except OSError:
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

        if os.path.isfile('/etc/nginx/conf.d/default.conf'):
            try:
                os.rename('/etc/nginx/conf.d/default.conf',
                          '/etc/nginx/conf.d/default.conf.bak')
            except OSError:
                self.log.warning('Failed renaming /etc/nginx/conf.d/default.conf')
        with open('/etc/nginx/conf.d/server1.conf', 'w') as f:
            f.write('server {\n')
            f.write('    listen       80;\n')
            f.write('    server_name  powerup;\n\n')
            f.write('    location / {\n')
            f.write('        root   /srv;\n')
            f.write('        autoindex on;\n')
            f.write('    }\n')
            f.write('}\n')

        cmd = 'nginx -s reload'
        _, _, rc = sub_proc_exec(cmd)
        if rc != 0:
            self.log.warning('Failed reloading nginx configuration')

        # Get PowerAI base
        heading1('Setting up the PowerAI base repository\n')
        pai_src = 'mldl-repo-local-5.[1-9]*.ppc64le.rpm'
        repo_id = 'power-ai'
        repo_name = 'IBM PowerAI Base'
        exists = glob.glob(f'/srv/repos/{repo_id}/**/repodata', recursive=True)
        if exists:
            self.log.info(f'The {repo_id} repository exists already in the POWER-Up server')
            r = get_yesno(f'Recreate the {repo_id} repository? ')
        if not exists or r:
            repo = PowerupRepoFromRpm(repo_id, repo_name)
            src_path = get_src_path(pai_src)
            if src_path:
                repo.copy_rpm(src_path)
                repodata_dir = repo.extract_rpm()
                if repodata_dir:
                    content = repo.get_yum_dotrepo_content(repo_dir=repodata_dir,
                                                           gpgcheck=0, local=True)
                else:
                    content = repo.get_yum_dotrepo_content(gpgcheck=0, local=True)
                    repo.create_meta()
                repo.write_yum_dot_repo_file(content)
                content = repo.get_yum_dotrepo_content(repo_dir=repodata_dir,
                                                       gpgcheck=0, client=True)
                filename = repo_id + '-powerup.repo'
                self.sw_vars['yum_powerup_repo_files'][filename] = content
            else:
                self.log.info('No source selected. Skipping PowerAI repository creation.')

        # Get Anaconda
        ana_src = 'Anaconda2-[56].[1-9]*-Linux-ppc64le.sh'
        # root dir is /srv/
        ana_name = 'anaconda'
        ana_url = 'https://repo.continuum.io/archive/Anaconda2-5.1.0-Linux-ppc64le.sh'
        if f'{ana_name}_alt_url' in self.sw_vars:
            alt_url = self.sw_vars[f'{ana_name}_alt_url']
        else:
            alt_url = 'http://'

        heading1('Set up Anaconda \n')
        src, state = setup_source_file(ana_name, ana_src, ana_url, alt_url=alt_url)

        if src is not None and src != ana_src and 'http' in src:
            self.sw_vars[f'{ana_name}_alt_url'] = src

        # Get Spectrum Conductor
        spc_src = 'conductor2.[3-9].[0-9].[0-9]_ppc64le.bin'
        name = 'spectrum-conductor'
        src_path, status = PowerupFileFromDisk(name, spc_src)

        # Get Spectrum DLI
        spdli_src = 'dli-1.[1-9].[0-9].[0-9]_ppc64le.bin'
        name = 'spectrum-dli'
        src_path, status = PowerupFileFromDisk(name, spdli_src)



        # Get cudnn tar file
        cudnn_src = 'cudnn-9.[1-9]-linux-ppc64le-v7.1.tgz'
        name = 'cudnn'
        src_path, status = PowerupFileFromDisk(name, cudnn_src)

        # Setup CUDA
        repo_id = 'cuda'
        repo_name = 'CUDA Toolkit'
        baseurl = 'http://developer.download.nvidia.com/compute/cuda/repos/rhel7/ppc64le'
        gpgkey = f'{baseurl}/7fa2af80.pub'
        heading1(f'Set up {repo_name} repository\n')
        if f'{repo_id}_alt_url' in self.sw_vars:
            alt_url = self.sw_vars[f'{repo_id}_alt_url']
        else:
            alt_url = None

        repo = PowerupRepoFromRepo(repo_id, repo_name)

        ch, new = repo.get_action()

        if new or ch in 'YF':
            url = repo.get_repo_url(baseurl, alt_url)
            if not url == baseurl:
                self.sw_vars[f'{repo_id}_alt_url'] = url
                content = repo.get_yum_dotrepo_content(url, gpgcheck=0)
            else:
                content = repo.get_yum_dotrepo_content(url, gpgkey=gpgkey)
            repo.write_yum_dot_repo_file(content)

            try:
                repo.sync()
            except UserException as exc:
                self.log.error(f'Repo sync error: {exc}')
            if new:
                repo.create_meta()
            else:
                repo.create_meta(update=True)

            if new or ch == 'F':
                content = repo.get_yum_dotrepo_content(gpgcheck=0, local=True)
                repo.write_yum_dot_repo_file(content)
                content = repo.get_yum_dotrepo_content(gpgcheck=0, client=True)
                filename = repo_id + '-powerup.repo'
                self.sw_vars['yum_powerup_repo_files'][filename] = content

        # Setup EPEL
        repo_id = 'epel-ppc64le'
        repo_name = 'Extra Packages for Enterprise Linux 7 (EPEL) - ppc64le'
        baseurl = 'https://mirrors.fedoraproject.org/metalink?repo=epel-7&arch=ppc64le'
        gpgkey = 'file:///etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-7'
        heading1(f'Set up {repo_name} repository')
        if f'{repo_id}_alt_url' in self.sw_vars:
            alt_url = self.sw_vars[f'{repo_id}_alt_url']
        else:
            alt_url = None

        repo = PowerupRepoFromRepo(repo_id, repo_name)

        ch, new = repo.get_action()
        if ch in 'YF':
            if new or ch == 'F':
                url = repo.get_repo_url(baseurl, alt_url)
                if not url == baseurl:
                    self.sw_vars[f'{repo_id}_alt_url'] = url
                    content = repo.get_yum_dotrepo_content(url, gpgkey=gpgkey)
                else:
                    content = repo.get_yum_dotrepo_content(url, gpgkey=gpgkey, metalink=True)
                repo.write_yum_dot_repo_file(content)

            repo.sync()
            if new:
                repo.create_meta()
            else:
                repo.create_meta(update=True)

            if new or ch == 'F':
                content = repo.get_yum_dotrepo_content(gpgcheck=0, local=True)
                repo.write_yum_dot_repo_file(content)
                content = repo.get_yum_dotrepo_content(gpgcheck=0, client=True)
                filename = repo_id + '-powerup.repo'
                self.sw_vars['yum_powerup_repo_files'][filename] = content

        # Create custom repositories
        heading1('Create custom repositories')
        if get_yesno('Would you like to create a custom repository? '):
            repo_id = input('Enter a repo id (yum short name): ')
            repo_name = input('Enter a repo name (Descriptive name): ')

            ch, item = get_selection('Create from files in a directory\n'
                                     'Create from an RPM file\n'
                                     'Create from an existing repository',
                                     'dir\nrpm\nrepo',
                                     'Repository source? ')
            if ch == 'rpm':

                repo = PowerupRepoFromRpm(repo_id, repo_name)

                if f'{repo_id}_src_rpm_dir' in self.sw_vars:
                    src_path = self.sw_vars[f'{repo_id}_src_rpm_dir']
                else:
                    # default is to search recursively under all /home/ directories
                    src_path = '/home/**/*.rpm'
                rpm_path = repo.get_rpm_path(src_path)
                if rpm_path:
                    self.sw_vars[f'{repo_id}_src_rpm_dir'] = rpm_path
                    repo.copy_rpm()
                    repodata_dir = repo.extract_rpm()
                    if repodata_dir:
                        content = repo.get_yum_dotrepo_content(repo_dir=repodata_dir,
                                                               gpgcheck=0, local=True)
                    else:
                        content = repo.get_yum_dotrepo_content(gpgcheck=0, local=True)
                        repo.create_meta()
                    repo.write_yum_dot_repo_file(content)
                    content = repo.get_yum_dotrepo_content(repo_dir=repodata_dir,
                                                           gpgcheck=0, client=True)
                    filename = repo_id + '-powerup.repo'
                    self.sw_vars['yum_powerup_repo_files'][filename] = content
                else:
                    self.log.info('No path chosen. Skipping create custom repository.')

            elif ch == 'dir':
                repo = PowerupRepoFromDir(repo_id, repo_name)

                if f'{repo_id}_src_dir' in self.sw_vars:
                    src_dir = self.sw_vars[f'{repo_id}_src_dir']
                else:
                    src_dir = None
                src_dir, dest_dir = repo.copy_dirs(src_dir)
                if src_dir:
                    self.sw_vars[f'{repo_id}_src_dir'] = src_dir
                    repo.create_meta()
                    content = repo.get_yum_dotrepo_content(gpgcheck=0, local=True)
                    repo.write_yum_dot_repo_file(content)
                    content = repo.get_yum_dotrepo_content(gpgcheck=0, client=True)
                    filename = repo_id + '-powerup.repo'
                    self.sw_vars['yum_powerup_repo_files'][filename] = content
            elif ch == 'repo':
                baseurl = 'http://'

                if f'{repo_id}_alt_url' in self.sw_vars:
                    alt_url = self.sw_vars[f'{repo_id}_alt_url']
                else:
                    alt_url = None

                repo = PowerupRepoFromRepo(repo_id, repo_name)

                new = True
                if os.path.isfile(f'/etc/yum.repos.d/{repo_id}.repo') and \
                        os.path.exists(repo.get_repo_dir()):
                    new = False

                url = repo.get_repo_url(baseurl)
                if not url == baseurl:
                    self.sw_vars[f'{repo_id}_alt_url'] = url
                # Set up access to the repo
                content = repo.get_yum_dotrepo_content(url, gpgcheck=0)
                repo.write_yum_dot_repo_file(content)

                repo.sync()

                if new:
                    repo.create_meta()
                else:
                    repo.create_meta(update=True)

                # Setup local access to the new repo copy in /srv/repo/
                content = repo.get_yum_dotrepo_content(gpgcheck=0, local=True)
                repo.write_yum_dot_repo_file(content)
                # Prep setup of POWER-Up client access to the repo copy
                content = repo.get_yum_dotrepo_content(gpgcheck=0, client=True)
                filename = repo_id + '-powerup.repo'
                self.sw_vars['yum_powerup_repo_files'][filename] = content
            self.log.info('Repository setup complete')

        print('Good to go')

    def install(self):
        ansible_inventory = get_ansible_inventory()
        cmd = ('{} -i {} '
               '{}/install_software.yml'
               .format(get_ansible_playbook_path(), ansible_inventory,
                       get_playbooks_path()))
        resp, err, rc = sub_proc_exec(cmd)
        print(resp)
        cmd = ('ssh -t -i ~/.ssh/gen root@10.0.20.22 '
               '/opt/DL/license/bin/accept-powerai-license.sh')
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
