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
from lib.utilities import sub_proc_display, sub_proc_exec, heading1, get_url, Color, \
    get_selection, get_yesno, get_dir, get_file_path, get_src_path, rlinput, bold
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
            self.README()
            _ = input('\nPress enter to continue')
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
        self.repo_dir = '/srv/repos/{repo_id}/rhel' + self.rhel_ver + '/{repo_id}'
        self.state = {'EPEL Repository': '-',
                      'CUDA Toolkit Repository': '-',
                      'PowerAI Base Repository': '-',
                      'Dependent Packages Repository': '-',
                      'CUDA dnn content': '-',
                      'Anaconda content': '-',
                      'Spectrum conductor content': '-',
                      'Spectrum DLI content': '-',
                      'Nginx Web Server': '-',
                      'Firewall': '-'}
        self.repo_id = {'EPEL Repository': 'epel-ppc64le',
                        'CUDA Toolkit Repository': 'cuda',
                        'PowerAI Base Repository': 'power-ai',
                        'Dependent Packages Repository': 'dependencies'}
        self.files = {'anaconda': 'Anaconda2-[56].[1-9]*-Linux-ppc64le.sh',
                      'cudnn': 'cudnn-9.[1-9]-linux-ppc64le-v7.1.tgz',
                      'spectrum-conductor': 'cws-2.[2-9].[0-9].[0-9]_ppc64le.bin',
                      'spectrum-dli': 'dli-1.[1-9].[0-9].[0-9]_ppc64le.bin'}

        self.log.debug(f'software variables: {self.sw_vars}')

    def __del__(self):
        if not os.path.exists(GEN_SOFTWARE_PATH):
            os.mkdir(GEN_SOFTWARE_PATH)
        with open(GEN_SOFTWARE_PATH + 'software-vars.yml', 'w') as f:
            yaml.dump(self.sw_vars, f, default_flow_style=False)

    def README(self):
        print(bold('\nPowerAI 5.2 software installer module'))
        text = ('\nThis module installs the PowerAI Enterprise software '
                'to a cluster of OpenPOWER nodes.\n\n'
                'PowerAI Enterprise installation involves three steps;\n'
                '   1 - Preparation. Prepares the installer node software server.\n'
                '       The preparation phase may be run multiple times if needed.\n'
                '       usage: pup software --prep paie52\n'
                '   2 - Installation. Install software on the client nodes\n'
                '       usage: pup software --install paie52\n\n'
                'Before beiginning, the following files should be copied\n'
                'onto this node;\n'
                '- mldl-repo-local-5.2.0-201804110899.fd91856.ppc64le.rpm\n'
                '- cudnn-9.1-linux-ppc64le-v7.1.tgz\n'
                '- cws-2.2.0.0_ppc64le.bin\n'
                '- dli-1.1.0.0_ppc64le.bin\n\n'
                'For installation status: pup software --status paie52\n'
                'To redisplay this README: pup software --README paie52\n\n')
        print(text)

    def status(self, which='all'):
        self.status_prep(which)

    def status_prep(self, which='all'):
        # Firewall status
        if which == 'all' or which == 'Firewall':
            cmd = 'firewall-cmd --list-all'
            resp, err, rc = sub_proc_exec(cmd)
            _status = re.search(r'services:\s+.+http', resp)
            if _status:
                self.state['Firewall'] = 'Firewall is running and configured for http'
        # Nginx web server status
        if which == 'all' or which == 'Nginx Web Server':
            cmd = 'curl -I 127.0.0.1'
            resp, err, rc = sub_proc_exec(cmd)
            if 'HTTP/1.1 200 OK' in resp:
                self.state['Nginx Web Server'] = 'Nginx is configured and running'

        # Anaconda status
        if which == 'all' or which == 'anaconda':
            exists = glob.glob(f'/srv/anaconda/**/{self.files["anaconda"]}',
                               recursive=True)
            if exists:
                self.state['Anaconda content'] = ('Anaconda is present in the '
                                                  'POWER-Up server')
        # cudnn status
        if which == 'all' or which == 'cudnn':
            exists = glob.glob(f'/srv/cudnn/**/{self.files["cudnn"]}', recursive=True)
            if exists:
                self.state['CUDA dnn content'] = ('CUDA DNN is present in the '
                                                  'POWER-Up server')
        # Spectrum conductor status
        if which == 'all' or which == 'spectrum-conductor':
            exists = glob.glob(f'/srv/spectrum-conductor/**/'
                               f'{self.files["spectrum-conductor"]}', recursive=True)
            if exists:
                self.state['Spectrum conductor content'] = \
                    'Spectrum Conductor is present in the POWER-Up server'

        # Spectrum DLI status
        if which == 'all' or which == 'spectrum-dli':
            exists = glob.glob(f'/srv/spectrum-dli/**/{self.files["spectrum-dli"]}',
                               recursive=True)
            if exists:
                self.state['Spectrum DLI content'] = ('Spectrum DLI is present in the '
                                                      'POWER-Up server')
        # PowerAI status
        s = 'PowerAI Base Repository'
        if which == 'all' or which == s:
            exists_repodata = glob.glob(self.repo_dir.format(repo_id=self.repo_id[s]) +
                                        '/**/repodata', recursive=True)
            if os.path.isfile(f'/etc/yum.repos.d/{self.repo_id[s]}-local.repo') \
                    and exists_repodata:
                self.state[s] = s + ' is setup'

        # CUDA status
        s = 'CUDA Toolkit Repository'
        if which == 'all' or which == s:
            exists_repodata = glob.glob(self.repo_dir.format(repo_id=self.repo_id[s]) +
                                        '/**/repodata', recursive=True)
            if os.path.isfile(f'/etc/yum.repos.d/{self.repo_id[s]}-local.repo') \
                    and exists_repodata:
                self.state[s] = s + ' is setup'

        # EPEL status
        s = 'EPEL Repository'
        if which == 'all' or which == s:
            exists_repodata = glob.glob(self.repo_dir.format(repo_id=self.repo_id[s]) +
                                        '/**/repodata', recursive=True)
            if os.path.isfile(f'/etc/yum.repos.d/{self.repo_id[s]}-local.repo') \
                    and exists_repodata:
                self.state[s] = s + ' is setup'

        # Dependent Packages status
        s = 'Dependent Packages Repository'
        if which == 'all' or which == s:
            exists_repodata = glob.glob(self.repo_dir.format(repo_id=self.repo_id[s]) +
                                        '/**/repodata', recursive=True)
            if os.path.isfile(f'/etc/yum.repos.d/{self.repo_id[s]}-local.repo') \
                    and exists_repodata:
                self.status[s] = s + ' is setup'

        if which == 'all':
            heading1('Preparation Summary')
            for item in self.state:
                print(f'  {item:<30} : ' + self.state[item])

            gtg = 'Preparation complete'
            for item in self.state.values():
                if item == '-':
                    gtg = f'{Color.red}Preparation incomplete{Color.endc}'
            print(f'\n{bold(gtg)}\n')

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

        self.status_prep(which='Firewall')
        if self.state['Firewall'] == '-':
            self.log.info('Failed to configure firewall')
        else:
            self.log.info(self.state['Firewall'])

        # nginx setup
        heading1('Set up Nginx')
        baseurl = 'http://nginx.org/packages/mainline/rhel/7/' + \
                  platform.machine()
        repo_id = 'nginx'
        repo_name = 'nginx.org public'
        repo = PowerupRepo(repo_id, repo_name)
        content = repo.get_yum_dotrepo_content(baseurl, gpgcheck=0)
        repo.write_yum_dot_repo_file(content)

        # Check if nginx installed. Install if necessary.
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

        self.status_prep(which='Nginx Web Server')
        if self.state['Nginx Web Server'] == '-':
            self.log.info('nginx web server is not running')
        else:
            self.log.info(self.state['Nginx Web Server'])

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

        self.status_prep(which='PowerAI Base Repository')
        if self.state['PowerAI Base Repository'] != '-':
            self.log.info(f'The {repo_id} repository exists already in the POWER-Up server')
            r = get_yesno(f'Recreate the {repo_id} repository? ')
        if self.state['PowerAI Base Repository'] == '-' or r:
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
                self.status_prep(which='PowerAI Base Repository')
            else:
                self.log.info('No source selected. Skipping PowerAI repository creation.')

        # Get Anaconda
        ana_name = 'anaconda'
        ana_src = self.files[ana_name]
        ana_url = 'https://repo.continuum.io/archive/Anaconda2-5.1.0-Linux-ppc64le.sh'
        if f'{ana_name}_alt_url' in self.sw_vars:
            alt_url = self.sw_vars[f'{ana_name}_alt_url']
        else:
            alt_url = 'http://'

        self.status_prep(ana_name)

        heading1('Set up Anaconda \n')
        src, state = setup_source_file(ana_name, ana_src, ana_url, alt_url=alt_url)

        if src is not None and src != ana_src and 'http' in src:
            self.sw_vars[f'{ana_name}_alt_url'] = src

        # Get Spectrum Conductor with Spark
        name = 'spectrum-conductor'
        heading1(f'Set up {name.title()} \n')
        spc_src = self.files[name]
        self.status_prep(name)
        exists = False if self.state['Spectrum conductor content'] == '-' else True

        if exists:
            self.log.info('Spectrum conductor content exists already in the POWER-Up server')

        if not exists or (exists and get_yesno(f'Copy a new {name.title()} file? ')):
            src_path = PowerupFileFromDisk(name, spc_src)

        # Get Spectrum DLI
        name = 'spectrum-dli'
        heading1(f'Set up {name.title()} \n')
        spdli_src = self.files[name]
        self.status_prep(name)
        exists = False if self.state['Spectrum DLI content'] == '-' else True

        if exists:
            self.log.info('Spectrum DLI content exists already in the POWER-Up server')

        if not exists or (exists and get_yesno(f'Copy a new {name.title()} file? ')):
            src_path = PowerupFileFromDisk(name, spdli_src)

        # Setup repository for dependent packages
        dep_list = ('bzip2 opencv kernel kernel-tools kernel-tools-libs '
                    'kernel-bootwrapper kernel-devel kernel-headers gcc gcc-c++ '
                    'libXdmcp elfutils-libelf-devel java-1.8.0-openjdk libmpc '
                    'libatomic glibc-devel glibc-headers mpfr kernel-headers '
                    'zlib-devel boost-system libgfortran boost-python boost-thread '
                    'boost-filesystem java-1.8.0-openjdk-devel')
        file_more = GEN_SOFTWARE_PATH + 'dependent-packages.list'
        if os.path.isfile(file_more):
            try:
                with open(file_more, 'r') as f:
                    more = f.read()
            except:
                self.log.error('Error reading {file_more}')
                more = ''
            else:
                more.replace(',', ' ')
                more.replace('\n', ' ')
        else:
            more = ''
        heading1('Setup repository for dependent packages\n')
        self.status_prep(which='Dependent Packages Repository')
        new = self.status['Dependent Packages Repository'] == '-'
        if not new:
            self.log.info('The Dependent Packages Repository exists already'
                          ' in the POWER-Up server.')
            resp = get_yesno('Do you wish to recreate the dependent '
                             'packages repository?')
        if new or resp:
            repo_id = 'dependencies'
            repo_name = 'Dependencies'
            repo = PowerupRepo(repo_id, repo_name)
            repo_dir = repo.get_repo_dir()
            self._add_dependent_packages(repo_dir, dep_list)
            self._add_dependent_packages(repo_dir, more)
            repo.create_meta()
            content = repo.get_yum_dotrepo_content(gpgcheck=0, local=True)
            repo.write_yum_dot_repo_file(content)
            content = repo.get_yum_dotrepo_content(gpgcheck=0, client=True)
            filename = repo_id + '-powerup.repo'
            self.sw_vars['yum_powerup_repo_files'][filename] = content

        # Get cudnn tar file
        name = 'cudnn'
        heading1(f'Set up {name.title()} \n')
        cudnn_src = self.files[name]
        self.status_prep(name)
        exists = False if self.state['CUDA dnn content'] == '-' else True

        if exists:
            self.log.info('CUDA dnn content exists already in the POWER-Up server')

        if not exists or (exists and get_yesno(f'Copy a new {name.title()} file? ')):
            src_path = PowerupFileFromDisk(name, cudnn_src)

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

        self.status_prep(which='CUDA Toolkit Repository')
        new = self.state['CUDA Toolkit Repository'] == '-'
        if not new:
            self.log.info('The CUDA Toolkit Repository exists already'
                          ' in the POWER-Up server')

        repo = PowerupRepoFromRepo(repo_id, repo_name)

        ch = repo.get_action(new)
        if ch in 'YF':
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

        self.status_prep(which='EPEL Repository')
        new = self.state['EPEL Repository'] == '-'
        if not new:
            self.log.info('The EPEL Repository exists already'
                          ' in the POWER-Up server')

        repo = PowerupRepoFromRepo(repo_id, repo_name)

        ch = repo.get_action(new)
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
        # Display status
        self.status_prep()

    def _add_dependent_packages(self, repo_dir, dep_list):
        cmd = (f'yumdownloader --resolve --archlist={self.arch} --destdir '
               f'{repo_dir} {dep_list}')
        resp, err, rc = sub_proc_exec(cmd)
        if rc != 0:
            self.log.error('An error occurred while downloading dependent packages\n'
                           f'rc: {rc} err: {err}')
        resp = resp.splitlines()
        for item in resp:
            if 'No Match' in item:
                self.log.error(f'Dependent packages download error. {item}')

        cmd = 'yum clean packages expire-cache'
        resp, err, rc = sub_proc_exec(cmd)
        if rc != 0:
            self.log.error('An error occurred while cleaning the yum cache\n'
                           f'rc: {rc} err: {err}')

        cmd = 'yum makecache fast'
        resp, err, rc = sub_proc_exec(cmd)
        if rc != 0:
            self.log.error('An error occurred while making the yum cache\n'
                           f'rc: {rc} err: {err}')

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
