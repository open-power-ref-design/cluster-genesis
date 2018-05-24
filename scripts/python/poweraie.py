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
from repos import PowerupRepo, PowerupRepoFromDir, PowerupRepoFromRepo, \
    setup_source_file
from software_hosts import get_ansible_inventory
from lib.utilities import sub_proc_display, sub_proc_exec, heading1, \
    get_selection, get_yesno, get_dir, get_file_path, rlinput
from lib.genesis import GEN_SOFTWARE_PATH
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
        r = get_yesno('Would you like to create a custom repository? ')
        if r == 'y':
            ch, item = get_selection('Directory.RPM file', 'dir.rpm', '.',
                                     'Custom repository from a directory or RPM file? ')
            repo_id = input('Enter a repo id (yum short name): ')
            repo_name = input('Enter a repo name (Descriptive name): ')
            if ch == 'rpm':
                fpath = get_file_path('/home/**/*.rpm')
                #print(fpath)
                if fpath:
                    if not os.path.exists(f'/srv/{repo_id}'):
                        os.mkdir(f'/srv/{repo_id}')
                sys.exit('Leaving make repo from rpm')
            elif ch == 'dir':
                repo = PowerupRepoFromDir(repo_id, repo_name)

                if f'{repo_id}_src_dir' in self.sw_vars:
                    src_dir = self.sw_vars[f'{repo_id}_src_dir']
                else:
                    src_dir = None
                src_dir, dest_dir = repo.copy_dirs(src_dir)
                if src_dir:
                    self.sw_vars[f'{repo_id}_src_dir'] = src_dir

                if src_dir:
                    repo.create_meta()
                    content = repo.get_yum_dotrepo_content(gpgcheck=0, local=True)
                    repo.write_yum_dot_repo_file(content)
                    content = repo.get_yum_dotrepo_content(gpgcheck=0, client=True)
                    filename = repo_id + '-powerup.repo'
                    self.sw_vars['yum_powerup_repo_files'][filename] = content

                sys.exit(f'bye setup source dir: {dest_dir}')

#        cwd = os.getcwd()
#        print(f'CWD: {cwd}')
#        fpath = get_file_path()
#        print(f'Path {fpath}')
#        sys.exit('Bye')
#        cmd = 'ls -l | grep scripts'
#        resp, err, rc = sub_proc_exec(cmd, shell=True)
#        cmd = 'repoquery nginx --qf "%{name} %{ver} %{arch} %{repoid}"'
#        resp, err, rc = sub_proc_exec(cmd)
#        print(resp)
#        sys.exit(f'test cpio')

        # Setup EPEL
        repo_id = 'epel-ppc64le'
        repo_name = 'Extra Packages for Enterprise Linux 7 - ppc64le'
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
                    content = repo.get_yum_dotrepo_content(url, gpgkey)
                else:
                    content = repo.get_yum_dotrepo_content(url, gpgkey, metalink=True)
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

        #sys.exit('done with epel - bye')

        # Setup CUDA
        baseurl = 'http://developer.download.nvidia.com/compute/cuda/repos/rhel7/ppc64le'
        gpgkey = f'{baseurl}/7fa2af80.pub'
        repo_id = 'cuda'
        repo_name = 'CUDA Toolkit'
        heading1(f'Set up {repo_name} repository')
        if f'{repo_id}_alt_url' in self.sw_vars:
            alt_url = self.sw_vars[f'{repo_id}_alt_url']
        else:
            alt_url = None

        repo = PowerupRepoFromRepo(repo_id, repo_name)

        ch, new = repo.get_action()
        if ch in 'YF':
            if new or ch == 'F':
                url = repo.get_repo_url(baseurl)
                if not url == baseurl:
                    self.sw_vars[f'{repo_id}_alt_url'] = url
                content = repo.get_yum_dotrepo_content(url, gpgkey)
                repo.write_yum_dot_repo_file(content)

            while True:
                try:
                    repo.sync()
                    r = 'S'
                except UserException as exc:
                    r, item = get_selection('Retry cuda repository sync\n'
                                            'Skip cuda repository sync\n'
                                            'Exit POWER-Up software installer',
                                            'R\nS\nE')
                    if r == 'S':
                        break
                    elif r == 'E':
                        self.log.info('Leaving POWER-Up at user request')
                        sys.exit()

                if r == 'S':
                    break
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

        #sys.exit('bye cuda')

        # Get Anaconda
        ana_src = 'Anaconda2-[56].[1-9]*-Linux-ppc64le.sh'
        # root dir is /srv/
        ana_dir = 'anaconda'
        heading1('Set up Anaconda repository')
        setup_source_file(ana_src, ana_dir)

        #sys.exit('Bye Anaconda')

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
        cmd = f'diff /opt/DL/ /srv/repos/DL-{ver}/'
        resp2, err2, rc = sub_proc_exec(cmd)
        if 'is already installed' in err1 and 'Common subdirectories:' in resp2 \
                and rc == 0:
            repo_installed = True
        else:
            repo_installed = False

        # Create the repo and copy it to /srv directory
        if src_path:
            if not ver:
                self.log.error('Unable to find the version in {src_path}')
                ver = rlinput('Enter a version to use (x.y.z): ', '5.1.0')
            repo_id = f'DL-{ver}'
            repo_name = f'PowerAI-{ver}'
            repo = PowerupRepo(repo_id, repo_name)
            repo_path = repo.get_repo_dir()
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
                    shutil.rmtree(repo_path, ignore_errors=True)
                    try:
                        shutil.copytree('/opt/DL', repo_path + '/' + repo_id)
                    except shutil.Error as exc:
                        print(f'Copy error: {exc}')
                    else:
                        content = repo.get_yum_dotrepo_content(gpgcheck=0, local=True)
                        repo.write_yum_dot_repo_file(content)
                        self.log.info('Successfully created PowerAI repository')
                        content = repo.get_yum_dotrepo_content(gpgcheck=0, client=True)
                        filename = repo_id + '-powerup.repo'
                        self.sw_vars['yum_powerup_repo_files'][filename] = content
        else:
            if src_installed:
                self.log.debug('PowerAI source file already in place and no '
                               'update requested')
            else:
                self.log.error('PowerAI base was not installed.')

        #sys.exit('Bye from powerai')

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

#        nginx_repo = RemoteNginxRepo()
#        nginx_repo.yum_create_remote()
        baseurl = 'http://nginx.org/packages/mainline/rhel/7/ppc64le'
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
            print('nginx is installed:\n{}'.format(resp))
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

        print('Good to go')

    def install(self):
        ansible_inventory = get_ansible_inventory()
        cmd = ('ansible -i {} -m ping all'.format(ansible_inventory))
        resp, err, rc = sub_proc_exec(cmd)
        if str(rc) != "0":
            self.log.error('Ansible ping failed!')
            self.log.error(resp)
            sys.exit(1)
        else:
            print('Ansible ping passed!')
        cmd = ('ansible-playbook -i {} '
               '/home/user/power-up/playbooks/install_software.yml'
               .format(ansible_inventory))
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
