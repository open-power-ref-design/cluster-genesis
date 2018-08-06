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
import json
from getpass import getpass

import lib.logger as logger
from repos import PowerupRepo, PowerupRepoFromDir, PowerupYumRepoFromRepo, \
    PowerupAnaRepoFromRepo, PowerupRepoFromRpm, setup_source_file, \
    PowerupPypiRepoFromRepo, powerup_file_from_disk, get_name_dir
from software_hosts import get_ansible_inventory, validate_software_inventory
from lib.utilities import sub_proc_display, sub_proc_exec, heading1, get_url, Color, \
    get_selection, get_yesno, get_dir, get_file_path, get_src_path, rlinput, bold
from lib.genesis import GEN_SOFTWARE_PATH, get_ansible_playbook_path, \
    get_playbooks_path, get_ansible_vault_path
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
        yaml.add_constructor(YAMLVault.yaml_tag, YAMLVault.from_yaml)
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
        if 'ana_powerup_repo_channels' not in self.sw_vars:
            self.sw_vars['ana_powerup_repo_channels'] = []
        if 'yum_powerup_repo_files' not in self.sw_vars:
            self.sw_vars['yum_powerup_repo_files'] = {}
        if 'content_files' not in self.sw_vars:
            self.sw_vars['content_files'] = {}
        self.epel_repo_name = 'epel-ppc64le'
        self.sw_vars['epel_repo_name'] = self.epel_repo_name
        self.rhel_ver = '7'
        self.sw_vars['rhel_ver'] = self.rhel_ver
        self.arch = 'ppc64le'
        self.sw_vars['arch'] = self.arch
        self.root_dir = '/srv/'
        self.repo_dir = self.root_dir + 'repos/{repo_id}/rhel' + self.rhel_ver + \
            '/{repo_id}'
        self.state = {'EPEL Repository': '-',
                      'CUDA Toolkit Repository': '-',
                      'PowerAI Base Repository': '-',
                      'Dependent Packages Repository': '-',
                      'Python Package Repository': '-',
                      'CUDA dnn content': '-',
                      'CUDA nccl2 content': '-',
                      'Anaconda content': '-',
                      'Anaconda Free Repository': '-',
                      'Anaconda Main Repository': '-',
                      'Spectrum conductor content': '-',
                      'Spectrum DLI content': '-',
                      'Nginx Web Server': '-',
                      'Firewall': '-'}
        self.repo_id = {'EPEL Repository': 'epel-ppc64le',
                        'CUDA Toolkit Repository': 'cuda',
                        'PowerAI Base Repository': 'power-ai',
                        'Dependent Packages Repository': 'dependencies',
                        'Python Package Repository': 'pypi'}
        # When searching for files in other web servers, the fileglobs are converted to
        # regular expressions. An asterisk (*) after a bracket is converted to a
        # regular extression of [0-9]{0,3} Other asterisks are converted to regular
        # expression of .+
        self.files = {'Anaconda content': 'Anaconda2-[56].[1-9]*.[0-9]*-Linux-ppc64le.sh',
                      'CUDA dnn content': 'cudnn-9.[1-9]*-linux-ppc64le-v7.1.tgz',
                      'CUDA nccl2 content': 'nccl_2.2.1[2-9]-1+cuda9.[2-9]_ppc64le.tgz',
                      'PowerAI content': 'mldl-repo-local-[5-9]*.[1-9]*.[0-9]**.ppc64le.rpm',
                      'Spectrum conductor content': 'cws-[2-9]*.[2-9]*.[0-9]*.[0-9]*_ppc64le.bin',
                      'Spectrum DLI content': 'dli-[1-9]*.[1-9]*.[0-9]*.[0-9]*_ppc64le.bin'}
        if 'ansible_inventory' not in self.sw_vars:
            self.sw_vars['ansible_inventory'] = None
        if 'ansible_become_pass' not in self.sw_vars:
            self.sw_vars['ansible_become_pass'] = None
        self.vault_pass = None
        self.vault_pass_file = f'{GEN_SOFTWARE_PATH}.vault'

        self.log.debug(f'software variables: {self.sw_vars}')

    def __del__(self):
        if not os.path.exists(GEN_SOFTWARE_PATH):
            os.mkdir(GEN_SOFTWARE_PATH)
        with open(GEN_SOFTWARE_PATH + 'software-vars.yml', 'w') as f:
            yaml.dump(self.sw_vars, f, default_flow_style=False)
        if os.path.isfile(self.vault_pass_file):
            os.remove(self.vault_pass_file)

    def README(self):
        print(bold('\nPowerAI 5.2 software installer module'))
        text = ('\nThis module installs the PowerAI Enterprise software '
                'to a cluster of OpenPOWER nodes.\n\n'
                'PowerAI Enterprise installation involves three steps;\n'
                '\n  1 - Preparation. Prepares the installer node software server.\n'
                '       The preparation phase may be run multiple times if needed.\n'
                '       usage: pup software --prep paie52\n'
                '\n  2 - Initialization of client nodes\n'
                '       usage: pup software --init-clients paie52\n'
                '\n  3 - Installation. Install software on the client nodes\n'
                '       usage: pup software --install paie52\n\n'
                'Before beginning, the following files should be present\n'
                'on this node;\n'
                '- mldl-repo-local-5.2.0-201806060629.714fa9e.ppc64le.rpm\n'
                '- cudnn-9.2-linux-ppc64le-v7.1.tgz\n'
                '- nccl_2.2.12-1+cuda9.2_ppc64le.tgz\n'
                '- cws-2.2.1.0_ppc64le.bin\n'
                '- dli-1.1.0.0_ppc64le.bin\n\n'
                'For installation status: pup software --status paie52\n'
                'To redisplay this README: pup software --README paie52\n\n'
                'Note: The \'pup\' cli supports tab autocompletion.\n\n')
        print(text)

    def status(self, which='all'):
        self.status_prep(which)

    def status_prep(self, which='all'):
        for item in self.state:
            self.state[item] = '-'
            # Firewall status
            if item == 'Firewall':
                cmd = 'firewall-cmd --list-all'
                resp, err, rc = sub_proc_exec(cmd)
                if re.search(r'services:\s+.+http', resp):
                    self.state[item] = 'Firewall is running and configured for http'

            # Nginx web server status
            if item == 'Nginx Web Server':
                cmd = 'curl -I 127.0.0.1'
                resp, err, rc = sub_proc_exec(cmd)
                if 'HTTP/1.1 200 OK' in resp:
                    self.state[item] = 'Nginx is configured and running'

            # Anaconda content status
            if item == 'Anaconda content':
                item_dir = get_name_dir(item)
                exists = glob.glob(f'/srv/{item_dir}/**/{self.files[item]}',
                                   recursive=True)
                if exists:
                    self.state['Anaconda content'] = ('Anaconda is present in the '
                                                      'POWER-Up server')

            # Anaconda Repo Free status
            if item == 'Anaconda Free Repository':
                repodata_noarch = glob.glob(f'/srv/repos/anaconda/pkgs/free'
                                            '/noarch/repodata.json', recursive=True)
                repodata = glob.glob(f'/srv/repos/anaconda/pkgs/free'
                                     '/linux-ppc64le/repodata.json', recursive=True)
                if repodata and repodata_noarch:
                    self.state[item] = f'{item} is setup'

            # Anaconda Main repo status
            if item == 'Anaconda Main Repository':
                repodata_noarch = glob.glob(f'/srv/repos/anaconda/pkgs/main'
                                            '/noarch/repodata.json', recursive=True)
                repodata = glob.glob(f'/srv/repos/anaconda/pkgs/main'
                                     '/linux-ppc64le/repodata.json', recursive=True)
                if repodata and repodata_noarch:
                    self.state[item] = f'{item} is setup'

            # cudnn status
            if item == 'CUDA dnn content':
                item_dir = get_name_dir(item)
                exists = glob.glob(f'/srv/{item_dir}/**/{self.files[item]}', recursive=True)
                if exists:
                    self.state['CUDA dnn content'] = ('CUDA DNN is present in the '
                                                      'POWER-Up server')

            # cuda nccl2 status
            if item == 'CUDA nccl2 content':
                item_dir = get_name_dir(item)
                exists = glob.glob(f'/srv/{item_dir}/**/{self.files[item]}', recursive=True)
                if exists:
                    self.state[item] = ('CUDA nccl2 is present in the '
                                        'POWER-Up server')

            # Spectrum conductor status
            if item == 'Spectrum conductor content':
                item_dir = get_name_dir(item)
                exists = glob.glob(f'/srv/{item_dir}/**/'
                                   f'{self.files[item]}', recursive=True)
                if exists:
                    self.state[item] = \
                        'Spectrum Conductor is present in the POWER-Up server'

            # Spectrum DLI status
            if item == 'Spectrum DLI content':
                item_dir = get_name_dir(item)
                exists = glob.glob(f'/srv/{item_dir}/**/{self.files[item]}',
                                   recursive=True)
                if exists:
                    self.state[item] = ('Spectrum DLI is present in the '
                                        'POWER-Up server')
            # PowerAI status
            if item == 'PowerAI Base Repository':
                content = glob.glob(os.path.join(self.root_dir, self.repo_id[item],
                                    self.files['PowerAI content']))
                repodata = glob.glob(self.repo_dir.format(repo_id=self.repo_id[item]) +
                                     '/**/repodata', recursive=True)
                if os.path.isfile(f'/etc/yum.repos.d/{self.repo_id[item]}-local.repo') \
                        and repodata and content:
                    self.state[item] = f'{item} is setup'

            # CUDA status
            if item == 'CUDA Toolkit Repository':
                repodata = glob.glob(self.repo_dir.format(repo_id=self.repo_id[item]) +
                                     '/**/repodata', recursive=True)
                if os.path.isfile(f'/etc/yum.repos.d/{self.repo_id[item]}-local.repo') \
                        and repodata:
                    self.state[item] = f'{item} is setup'

            # EPEL status
            if item == 'EPEL Repository':
                repodata = glob.glob(self.repo_dir.format(repo_id=self.repo_id[item]) +
                                     '/**/repodata', recursive=True)
                if os.path.isfile(f'/etc/yum.repos.d/{self.repo_id[item]}-local.repo') \
                        and repodata:
                    self.state[item] = f'{item} is setup'

            # Dependent Packages status
            s = 'Dependent Packages Repository'
            if item == 'Dependent Packages Repository':
                repodata = glob.glob(self.repo_dir.format(repo_id=self.repo_id[item]) +
                                     '/**/repodata', recursive=True)
                if os.path.isfile(f'/etc/yum.repos.d/{self.repo_id[item]}-local.repo') \
                        and repodata:
                    self.state[item] = f'{item} is setup'

            # Python Packages status
            s = 'Python Packages Repository'
            if item == 'Python Package Repository':
                if os.path.isfile(f'/srv/repos/{self.repo_id[item]}/simple/index.html'):
                    self.state[item] = f'{item} is setup'

        exists = True
        if which == 'all':
            heading1('Preparation Summary')
            for item in self.state:
                print(f'  {item:<30} : ' + self.state[item])
                exists = exists and self.state[item] != '-'

            gtg = 'Preparation complete'
            for item in self.state.values():
                if item == '-':
                    gtg = f'{Color.red}Preparation incomplete{Color.endc}'
            print(f'\n{bold(gtg)}\n')

        else:
            exists = self.state[which] != '-'
        return exists

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
            self.log.info('Cleaning yum caches')
            cmd = 'yum clean all'
            resp, err, rc = sub_proc_exec(cmd)
            if rc != 0:
                self.log.error('An error occurred while cleaning the yum repositories\n'
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
        name = 'PowerAI content'
        heading1('Setting up the PowerAI base repository\n')
        pai_src = self.files['PowerAI content']
        pai_url = ''
        repo_id = 'power-ai'
        repo_name = 'IBM PowerAI Base'

        if f'{name}_alt_url' in self.sw_vars:
            alt_url = self.sw_vars[f'{name}_alt_url']
        else:
            alt_url = 'http://'

        exists = self.status_prep(which='PowerAI Base Repository')
        if exists:
            self.log.info(f'The {name} and {repo_id} repository exists already '
                          'in the POWER-Up server.')

        if not exists or get_yesno(f'Recopy {name} and Recreate the {repo_id} '
                                   'repository '):
            repo = PowerupRepoFromRpm(repo_id, repo_name)
            src_path, dest_path, state = setup_source_file(repo_id, pai_src, pai_url,
                                                           alt_url=alt_url)

            if src_path:
                print(f'Creating {repo_id} repository.')
                if 'http' in src_path:
                    self.sw_vars[f'{name}_alt_url'] = os.path.dirname(src_path) + '/'
                self.sw_vars['content_files'][get_name_dir(repo_id)] = dest_path
                repodata_dir = repo.extract_rpm(dest_path)
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

        # Get Spectrum Conductor with Spark
        name = 'Spectrum conductor content'
        heading1(f'Set up {name.title()} \n')
        spc_src = self.files[name]
        exists = self.status_prep(name)
        spc_url = ''

        if f'{name}_alt_url' in self.sw_vars:
            alt_url = self.sw_vars[f'{name}_alt_url']
        else:
            alt_url = 'http://'

        if exists:
            self.log.info('Spectrum conductor content exists already in the POWER-Up server')

        if not exists or get_yesno(f'Copy a new {name.title()} file '):
            src_path, dest_path, state = setup_source_file(name, spc_src, pai_url,
                                                           alt_url=alt_url)
            if 'http' in src_path:
                self.sw_vars[f'{name}_alt_url'] = os.path.dirname(src_path) + '/'
            if dest_path:
                self.sw_vars['content_files'][get_name_dir(name)] = dest_path

        # Get Spectrum DLI
        name = 'Spectrum DLI content'
        heading1(f'Set up {name.title()} \n')
        spdli_src = self.files[name]
        exists = self.status_prep(name)
        spdli_url = ''

        if f'{name}_alt_url' in self.sw_vars:
            alt_url = self.sw_vars[f'{name}_alt_url']
        else:
            alt_url = 'http://'

        if exists:
            self.log.info('Spectrum DLI content exists already in the POWER-Up server')

        if not exists or get_yesno(f'Copy a new {name.title()} file '):
            src_path, dest_path, state = setup_source_file(name, spdli_src, spdli_url,
                                                           alt_url=alt_url)
            if 'http' in src_path:
                self.sw_vars[f'{name}_alt_url'] = os.path.dirname(src_path) + '/'
            if dest_path:
                self.sw_vars['content_files'][get_name_dir(name)] = dest_path

        # Setup repository for dependent packages. Dependent packages can come from
        # any YUM repository enabled on the POWER-Up Installer node.
        dep_list = ('kernel kernel-tools kernel-tools-libs dejavu-serif-fonts '
                    'bzip2 opencv opencv-devel opencv-python snappy-devel '
                    'kernel-bootwrapper kernel-devel kernel-headers gcc gcc-c++ '
                    'libXdmcp elfutils-libelf-devel java-1.8.0-openjdk libmpc '
                    'libatomic glibc-devel glibc-headers mpfr kernel-headers '
                    'zlib-devel boost-system libgfortran boost-python boost-thread '
                    'boost-filesystem java-1.8.0-openjdk-devel scipy PyYAML '
                    'pyparsing python-pillow python-matplotlib pciutils libgcc '
                    'libgomp libstdc++ libstdc++-devel cpp gcc-c++ gcc-gfortran')
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
        exists = self.status_prep(which='Dependent Packages Repository')
        if exists:
            self.log.info('The Dependent Packages Repository exists already'
                          ' in the POWER-Up server.')
            resp = get_yesno('Do you wish to recreate the dependent '
                             'packages repository ')
        if not exists or resp:
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

        # Get Anaconda
        ana_name = 'Anaconda content'
        ana_src = self.files[ana_name]
        ana_url = 'https://repo.continuum.io/archive/Anaconda2-5.1.0-Linux-ppc64le.sh'
        if f'{ana_name}_alt_url' in self.sw_vars:
            alt_url = self.sw_vars[f'{ana_name}_alt_url']
        else:
            alt_url = 'http://'

        exists = self.status_prep(which=ana_name)

        heading1('Set up Anaconda and Anaconda repositories\n')

        if exists:
            self.log.info(f'The {ana_name} exists already '
                          'in the POWER-Up server.')

        if not exists or get_yesno(f'Recopy {ana_name} '):

            src_path, dest_path, state = setup_source_file(ana_name, ana_src, ana_url,
                                                           alt_url=alt_url)
            if dest_path:
                self.sw_vars['content_files'][get_name_dir(ana_name)] = dest_path
            if src_path is not None and src_path != ana_src and 'http' in src_path:
                self.sw_vars[f'{ana_name}_alt_url'] = os.path.dirname(src_path) + '/'

        # Setup Anaconda Free Repo.  (not a YUM repo)
        repo_id = 'anaconda'
        repo_name = 'Anaconda Free Repository'
        baseurl = 'https://repo.continuum.io/pkgs/free/linux-ppc64le/'
        heading1(f'Set up {repo_name}\n')

        vars_key = get_name_dir(repo_name)  # format the name
        if f'{vars_key}-alt-url' in self.sw_vars:
            alt_url = self.sw_vars[f'{vars_key}-alt-url']
        else:
            alt_url = None

        exists = self.status_prep(which='Anaconda Free Repository')
        if exists:
            self.log.info('The Anaconda Repository exists already'
                          ' in the POWER-Up server\n')

        repo = PowerupAnaRepoFromRepo(repo_id, repo_name)

        ch = repo.get_action(exists)
        if ch in 'YF':
            # if not exists or ch == 'F':
            url = repo.get_repo_url(baseurl, alt_url)
            if not url == baseurl:
                self.sw_vars[f'{vars_key}-alt-url'] = url
            dest_dir = repo.sync_ana(url)
            dest_dir = dest_dir[4 + dest_dir.find('/srv'):5 + dest_dir.find('free')]
            # form .condarc channel entry. Note that conda adds
            # the corresponding 'noarch' channel automatically.
            channel = f'  - http://{{{{ host_ip.stdout }}}}{dest_dir}'
            if channel not in self.sw_vars['ana_powerup_repo_channels']:
                self.sw_vars['ana_powerup_repo_channels'].append(channel)
            noarch_url = os.path.split(url.rstrip('/'))[0] + '/noarch/'
            rejlist = ('continuum-docs-*,cudatoolkit-*,'
                       'cudnn-*,tensorflow-*,caffe-*,'
                       'anaconda-oss-docs-*,anaconda-docs-*')

            repo.sync_ana(noarch_url, rejlist=rejlist)

        # Setup Anaconda Main Repo.  (not a YUM repo)
        repo_id = 'anaconda'
        repo_name = 'Anaconda Main Repository'
        baseurl = 'https://repo.continuum.io/pkgs/main/linux-ppc64le/'
        heading1(f'Set up {repo_name}\n')

        vars_key = get_name_dir(repo_name)  # format the name
        if f'{vars_key}-alt-url' in self.sw_vars:
            alt_url = self.sw_vars[f'{vars_key}-alt-url']
        else:
            alt_url = None

        exists = self.status_prep(which='Anaconda Main Repository')
        if exists:
            self.log.info('The Anaconda Repository exists already'
                          ' in the POWER-Up server\n')

        repo = PowerupAnaRepoFromRepo(repo_id, repo_name)

        ch = repo.get_action(exists)
        if ch in 'YF':
            # if not exists or ch == 'F':
            url = repo.get_repo_url(baseurl, alt_url)
            if not url == baseurl:
                self.sw_vars[f'{vars_key}-alt-url'] = url

            al = ('libgcc-ng-*,libstdcxx-ng-*,python-2.7.1*,ncurses-*,'
                  'openssl-1.*,ca-certificates-*,tk-*,sqlite-3.*,'
                  'wheel-*,readline-*,zlib-*,setuptools-*,libffi-*,'
                  'pip-1*,certifi-*,libedit-*')
            al += ('backports.shutil_get_terminal_size*,blas*,cairo*,chardet*,'
                   'cycler*,cython*,decorator*,enum34*,fontconfig*,freetype*,'
                   'functools32*,get_terminal_size*,h5py*,hdf5*,icu*,ipython*,'
                   'ipython_genutils*,jpeg*,leveldb*,libgfortran-ng*,libiconv*,'
                   'libopenblas*,libpng*,libtiff*,libxml2*,matplotlib*,networkx*,'
                   'nose*,numpy*,olefile*,pandas*,pathlib2*,pexpect*,pickleshare*,'
                   'pillow*,pixman*,prompt_toolkit*,ptyprocess*,pycairo*,pygments*,'
                   'pyparsing*,python-dateutil*,python-leveldb*,python-lmdb*,pytz*,'
                   'pywavelets*,pyyaml*,redis*,redis-py*,requests*,scandir*,'
                   'scikit-image*,scipy*,simplegeneric*,six*,snappy*,subprocess32*,'
                   'traitlets*,wcwidth*,xz*,yaml*')

            dest_dir = repo.sync_ana(url, acclist=al)
            # dest_dir = repo.sync_ana(url)
            dest_dir = dest_dir[4 + dest_dir.find('/srv'):5 + dest_dir.find('main')]
            # form .condarc channel entry. Note that conda adds
            # the corresponding 'noarch' channel automatically.
            channel = f'  - http://{{{{ host_ip.stdout }}}}{dest_dir}'
            if channel not in self.sw_vars['ana_powerup_repo_channels']:
                self.sw_vars['ana_powerup_repo_channels'].append(channel)
            noarch_url = os.path.split(url.rstrip('/'))[0] + '/noarch/'
            repo.sync_ana(noarch_url)

        # Setup Python package repository. (pypi)
        repo_id = 'pypi'
        repo_name = 'Python Package'
        baseurl = 'https://pypi.org'
        heading1(f'Set up {repo_name} repository\n')
        if f'{repo_id}_alt_url' in self.sw_vars:
            alt_url = self.sw_vars[f'{repo_id}_alt_url']
        else:
            alt_url = None

        exists = self.status_prep(which='Python Package Repository')
        if exists:
            self.log.info('The Python Package Repository exists already'
                          ' in the POWER-Up server')

        repo = PowerupPypiRepoFromRepo(repo_id, repo_name)
        ch = repo.get_action(exists, exists_prompt_yn=True)
        pkg_list = ('easydict==1.6 python-gflags==2.0 alembic==0.8.2 Keras==2.0.5 '
                    'elasticsearch==5.2.0 Flask-Script==2.0.5 Flask-HTTPAuth==3.2.2 '
                    'mongoengine==0.11.0 pathlib==1.0.1 python-heatclient==1.2.0 '
                    'python-keystoneclient==3.1.0 cmd2==0.8.8 unicodecsv>=0.8.0 '
                    'protobuf>=3.5.0.post1')
        # Conda prereqs for downloading the Python packages. These are installed
        # in the pkgdl venv on the installer node so that pypi packages can be downloaded
        pkg_list_conda = ('cython==0.25.2 h5py==2.7.0 ipython==5.3.0 '
                          'python-leveldb==0.194 python-lmdb==0.92 matplotlib==2.0.2 '
                          'networkx==1.11 nose==1.3.7 pandas==0.20.3 pillow==4.1.1 '
                          'python-dateutil==2.6.1 pyyaml==3.12 requests==2.13.0 '
                          'scipy==1.1.0 six==1.11.0 scikit-image==0.13.0 '
                          'redis-py==2.10.5 chardet==3.0.4')

        if not exists or ch == 'Y':
            if self._setup_anaconda_venv():
                cmd = ('source ' + os.path.expanduser('~/anaconda2/bin/activate') +
                       f' pkgdl && conda list')
                conda_list, err, rc = sub_proc_exec(cmd, shell=True)
                for pkg in pkg_list_conda.split():
                    name = pkg[:pkg.find('==')]
                    ver = pkg[pkg.find('==') + 2:]
                    installed = re.search(f'^{name}\s+{ver}', conda_list, re.MULTILINE)
                    if not installed:
                        print(f'Conda installing: {pkg}')
                        cmd = ('source ' + os.path.expanduser('~/anaconda2/bin/activate') +
                               f' pkgdl && conda install -y {pkg}')
                        resp, err, rc = sub_proc_exec(cmd, shell=True)
                        if rc != 0:
                            self.log.error('Error occured while installing conda package: '
                                           f'{pkg}. \nResp: {resp} \nRet code: {rc} '
                                           f'\nerr: {err}')
                url = repo.get_repo_url(baseurl, alt_url, name=repo_name)
                if url == baseurl:
                    repo.sync(pkg_list)
                else:
                    self.sw_vars[f'{repo_id}_alt_url'] = url
                    repo.sync(pkg_list, url + 'simple')
            else:
                self.log.error('Failed to setup the Anaconda environment')
                code.interact(banner='pypi', local=dict(globals(), **locals()))

        # Get cudnn tar file
        name = 'CUDA dnn content'
        heading1(f'Set up {name.title()} \n')
        cudnn_src = self.files[name]
        cudnn_url = ''

        if f'{name}_alt_url' in self.sw_vars:
            alt_url = self.sw_vars[f'{name}_alt_url']
        else:
            alt_url = None

        exists = self.status_prep(name)

        if exists:
            self.log.info('CUDA dnn content exists already in the POWER-Up server')

        if not exists or get_yesno(f'Copy a new {name.title()} file '):
            src_path, dest_path, state = setup_source_file(name, cudnn_src, cudnn_url,
                                                           alt_url=alt_url)
            if dest_path:
                self.sw_vars['content_files'][get_name_dir(name)] = dest_path
            if 'http' in src_path:
                self.sw_vars[f'{name}_alt_url'] = os.path.dirname(src_path) + '/'

        # Get cuda nccl2 tar file
        name = 'CUDA nccl2 content'
        heading1(f'Set up {name.title()} \n')
        nccl2_src = self.files[name]
        nccl2_url = ''
        exists = self.status_prep(name)

        if exists:
            self.log.info('CUDA nccl2 content exists already in the POWER-Up server')

        if not exists or get_yesno(f'Copy a new {name.title()} file '):
            src_path, dest_path, state = setup_source_file(name, nccl2_src, nccl2_url,
                                                           alt_url=alt_url)

            if dest_path:
                self.sw_vars['content_files'][get_name_dir(name)] = dest_path
            if 'http' in src_path:
                self.sw_vars[f'{name}_alt_url'] = os.path.dirname(src_path) + '/'

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

        exists = self.status_prep(which='CUDA Toolkit Repository')
        if exists:
            self.log.info('The CUDA Toolkit Repository exists already'
                          ' in the POWER-Up server')

        repo = PowerupYumRepoFromRepo(repo_id, repo_name)

        ch = repo.get_action(exists)
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

            if not exists:
                repo.create_meta()
            else:
                repo.create_meta(update=True)

            if not exists or ch == 'F':
                content = repo.get_yum_dotrepo_content(gpgcheck=0, local=True)
                repo.write_yum_dot_repo_file(content)
                content = repo.get_yum_dotrepo_content(gpgcheck=0, client=True)
                filename = repo_id + '-powerup.repo'
                self.sw_vars['yum_powerup_repo_files'][filename] = content

        # Setup EPEL Repo
        repo_id = 'epel-ppc64le'
        repo_name = 'Extra Packages for Enterprise Linux 7 (EPEL) - ppc64le'
        baseurl = 'https://mirrors.fedoraproject.org/metalink?repo=epel-7&arch=ppc64le'
        gpgkey = 'file:///etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-7'
        heading1(f'Set up {repo_name} repository')
        if f'{repo_id}_alt_url' in self.sw_vars:
            alt_url = self.sw_vars[f'{repo_id}_alt_url']
        else:
            alt_url = None

        exists = self.status_prep(which='EPEL Repository')
        if exists:
            self.log.info('The EPEL Repository exists already'
                          ' in the POWER-Up server')

        repo = PowerupYumRepoFromRepo(repo_id, repo_name)

        ch = repo.get_action(exists)
        if ch in 'YF':
            if not exists or ch == 'F':
                url = repo.get_repo_url(baseurl, alt_url)
                if not url == baseurl:
                    self.sw_vars[f'{repo_id}_alt_url'] = url
                    content = repo.get_yum_dotrepo_content(url, gpgkey=gpgkey)
                else:
                    content = repo.get_yum_dotrepo_content(url, gpgkey=gpgkey, metalink=True)
                repo.write_yum_dot_repo_file(content)

            repo.sync()
            if not exists:
                repo.create_meta()
            else:
                repo.create_meta(update=True)

            if not exists or ch == 'F':
                content = repo.get_yum_dotrepo_content(gpgcheck=0, local=True)
                repo.write_yum_dot_repo_file(content)
                content = repo.get_yum_dotrepo_content(gpgcheck=0, client=True)
                filename = repo_id + '-powerup.repo'
                self.sw_vars['yum_powerup_repo_files'][filename] = content

        # Create custom repositories
        heading1('Create custom repositories')
        if get_yesno('Would you like to create a custom repository '):
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

    def _setup_anaconda_venv(self):

        ret = False
        if not os.path.isdir(os.path.expanduser('~/anaconda2/envs/pkgdl')):
            if self.status_prep('Anaconda content'):
                if not os.path.isdir(os.path.expanduser('~/anaconda2')):
                    print('Anaconda needs to be installed on the installer node.')
                    print('Please accept the license and respond "no" when asked')
                    print('if you want to update the $PATH environment variable')
                    print('in your .bashrc file.\n')
                    input('Press enter to continue')
                    cmd = f"bash {self.sw_vars['content_files']['anaconda']}"
                    rc = sub_proc_display(cmd, shell=True)
                    if rc != 0:
                        self.log.error(f'Error installing Anaconda. {rc}')
                if not os.path.isdir(os.path.expanduser('~/anaconda2/envs/pkgdl')):
                    cmd = os.path.join(os.path.expanduser("~/anaconda2/bin"), 'conda')
                    cmd += ' create --name pkgdl --yes pip python=2.7'
                    rc = sub_proc_display(cmd)
                    if rc != 0:
                        self.log.error('Error creating package download virtual '
                                       f'environment. resp: {resp}, err: {err}')
                    else:
                        ret = True
                else:
                    ret = True
            else:
                self.log.info('Ananconda must be installed on the POWER-Up '
                              'installer node before setting up the Python '
                              'package index repository')
        else:
            ret = True
        return ret

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

    def init_clients(self):
        log = logger.getlogger()

        self.sw_vars['ansible_inventory'] = get_ansible_inventory()

        sudo_password = None
        if self.sw_vars['ansible_become_pass'] is None:
            sudo_password = self._cache_sudo_pass()
        else:
            self._unlock_vault()

        cmd = ('{} -i {} {}init_clients.yml --extra-vars "@{}" '
               .format(get_ansible_playbook_path(),
                       self.sw_vars['ansible_inventory'],
                       GEN_SOFTWARE_PATH,
                       GEN_SOFTWARE_PATH + "software-vars.yml"))
        prompt_msg = ""
        if sudo_password is not None:
            cmd += f'--extra-vars "ansible_become_pass={sudo_password}" '
        elif os.path.isfile(self.vault_pass_file):
            cmd += '--vault-password-file ' + self.vault_pass_file
        elif self.sw_vars['ansible_become_pass'] is None:
            cmd += '--ask-become-pass '
            prompt_msg = "\nClient password required for privilege escalation"

        run = True
        while run:
            log.info(f"Running Ansible playbook 'init_clients.yml' ...")
            print(prompt_msg)
            resp, err, rc = sub_proc_exec(cmd, shell=True)
            log.debug(f"cmd: {cmd}\nresp: {resp}\nerr: {err}\nrc: {rc}")
            if rc != 0:
                log.warning("Ansible playbook failed!")
                if resp != '':
                    print(f"stdout:\n{resp}\n")
                if err != '':
                    print(f"stderr:\n{err}\n")
                choice, item = get_selection(['Retry', 'Continue', 'Exit'])
                if choice == "1":
                    pass
                elif choice == "2":
                    run = False
                elif choice == "3":
                    log.debug('User chooses to exit.')
                    sys.exit('Exiting')
            else:
                log.info("Ansible playbook ran successfully")
                run = False
            print('All done')

    def _cache_sudo_pass(self):
        from ansible_vault import Vault
        log = logger.getlogger()

        print("\nPlease provide the client sudo password below. Note: All "
              "client nodes must use the same password!")
        client_sudo_pass_validated = False

        ansible_become_pass = getpass(prompt="Client sudo password: ")

        while not self._validate_ansible_become_pass(ansible_become_pass):
            choice, item = get_selection(['Re-enter password',
                                          'Continue without caching password',
                                          'Exit'])
            if choice == "1":
                ansible_become_pass = getpass(prompt="Client sudo password: ")
            elif choice == "2":
                ansible_become_pass = None
                break
            elif choice == "3":
                log.debug('User chooses to exit.')
                sys.exit('Exiting')

        self.vault_pass = ansible_become_pass

        if ansible_become_pass is not None:
            vault = Vault(self.vault_pass)
            data = vault.dump(ansible_become_pass).decode(encoding='UTF-8')
            self.sw_vars['ansible_become_pass'] = YAMLVault(data)

        return ansible_become_pass

    def _validate_ansible_become_pass(self, ansible_become_pass):
        log = logger.getlogger()

        print("\nValidating sudo password on all clients...")

        sudo_test = f'{GEN_SOFTWARE_PATH}paie52_ansible/sudo_test.yml'
        cmd = (f'{get_ansible_playbook_path()} '
               f'-i {self.sw_vars["ansible_inventory"]} '
               f'{GEN_SOFTWARE_PATH}paie52_ansible/run.yml '
               f'--extra-vars "task_file={sudo_test}" ')
        if ansible_become_pass is not None:
            cmd += f'--extra-vars "ansible_become_pass={ansible_become_pass}" '
        elif os.path.isfile(self.vault_pass_file):
            cmd += f' --vault-password-file {self.vault_pass_file} '
            cmd += f'--extra-vars "@{GEN_SOFTWARE_PATH}software-vars.yml" '
        else:
            cmd += ' --ask-become-pass '
        resp, err, rc = sub_proc_exec(cmd, shell=True)
        log.debug(f"cmd: {cmd}\nresp: {resp}\nerr: {err}\nrc: {rc}")
        if rc == 0:
            print(bold("Validation passed!\n"))
            return True
        else:
            print(bold("Validation failed!"))
            if resp != '':
                print(f"stdout:\n{resp}\n")
            if err != '':
                print(f"stderr:\n{err}\n")
            return False

    def _unlock_vault(self):
        while True:
            if self.sw_vars['ansible_become_pass'] is None:
                return False
            elif self.vault_pass is None:
                self.vault_pass = getpass(prompt="\nClient sudo password: ")
            with open(self.vault_pass_file, 'w') as vault_pass_file_out:
                vault_pass_file_out.write(self.vault_pass)
            os.chmod(self.vault_pass_file, 0o600)

            if self._validate_ansible_become_pass(None):
                return True
            else:
                print(bold("Cached sudo password decryption/validation fail!"))
                choice, item = get_selection(['Retry Password', 'Exit'])
                if choice == "1":
                    self.vault_pass = None
                elif choice == "2":
                    log.debug('User chooses to exit.')
                    sys.exit('Exiting')
                    sys.exit(1)

    def install(self):
        log = logger.getlogger()
        if self.sw_vars['ansible_inventory'] is None:
            self.sw_vars['ansible_inventory'] = get_ansible_inventory()
        else:
            print("Validating software inventory '{}'..."
                  .format(self.sw_vars['ansible_inventory']))
            if validate_software_inventory(self.sw_vars['ansible_inventory']):
                print(bold("Validation passed!"))
            else:
                print(bold("Validation FAILED!"))
                self.sw_vars['ansible_inventory'] = get_ansible_inventory()

        self._unlock_vault()

        install_tasks = yaml.load(open(GEN_SOFTWARE_PATH +
                                       'paie52_install_procedure.yml'))
        for task in install_tasks:
            heading1(f"Client Node Action: {task['description']}")
            if task['description'] == "Install Anaconda installer":
                _interactive_anaconda_license_accept(
                    self.sw_vars['ansible_inventory'])
            _run_ansible_tasks(task['tasks'],
                               self.sw_vars['ansible_inventory'],
                               self.vault_pass_file)
        print('Done')


def _run_ansible_tasks(tasks_path, ansible_inventory, vault_pass_file,
                       extra_args=''):
    log = logger.getlogger()
    tasks_path = 'paie52_ansible/' + tasks_path
    if os.path.isfile(vault_pass_file):
        extra_args += ' --vault-password-file ' + vault_pass_file
    elif 'become:' in open(f'{GEN_SOFTWARE_PATH}{tasks_path}').read():
        extra_args += ' --ask-become-pass'
    cmd = ('{0} -i {1} {2}paie52_ansible/run.yml '
           '--extra-vars "task_file={2}{3}" '
           '--extra-vars "@{2}{4}" {5}'
           .format(get_ansible_playbook_path(), ansible_inventory,
                   GEN_SOFTWARE_PATH, tasks_path, 'software-vars.yml',
                   extra_args))
    run = True
    while run:
        log.info(f'Running Ansible tasks found in \'{tasks_path}\' ...')
        if 'notify: Reboot' in open(f'{GEN_SOFTWARE_PATH}{tasks_path}').read():
            print(bold('\nThis step requires changed systems to reboot! '
                       '(16 minute timeout)'))
        if '--ask-become-pass' in cmd:
            print('\nClient password required for privilege escalation')
        resp, err, rc = sub_proc_exec(cmd, shell=True)
        log.debug(f"cmd: {cmd}\nresp: {resp}\nerr: {err}\nrc: {rc}")
        print("")  # line break
        if rc != 0:
            log.warning("Ansible tasks failed!")
            if resp != '':
                print(f"stdout:\n{resp}\n")
            if err != '':
                print(f"stderr:\n{err}\n")
            choice, item = get_selection(['Retry', 'Continue', 'Exit'])
            if choice == "1":
                pass
            elif choice == "2":
                run = False
            elif choice == "3":
                log.debug('User chooses to exit.')
                sys.exit('Exiting')
        else:
            log.info("Ansible tasks ran successfully")
            run = False
    return rc


def _interactive_anaconda_license_accept(ansible_inventory):
    log = logger.getlogger()
    cmd = (f'ansible-inventory --inventory {ansible_inventory} --list')
    resp, err, rc = sub_proc_exec(cmd, shell=True)
    inv = json.loads(resp)
    hostname, hostvars = inv['_meta']['hostvars'].popitem()

    base_cmd = f'ssh -t {hostvars["ansible_user"]}@{hostname} '
    if "ansible_ssh_private_key_file" in hostvars:
        base_cmd += f'-i {hostvars["ansible_ssh_private_key_file"]} '
    if "ansible_ssh_common_args" in hostvars:
        base_cmd += f'{hostvars["ansible_ssh_common_args"]} '

    cmd = base_cmd + 'ls /opt/anaconda2/'
    resp, err, rc = sub_proc_exec(cmd)

    # If install directory already exists assume license has been accepted
    if rc == 0:
        print(f'Anaconda license already accepted on {hostname}')
    else:
        print(bold('Manual Anaconda license acceptance required on at least '
                   'one client!'))
        rlinput(f'Press Enter to run interactively on {hostname}')
        cmd = (base_cmd + 'sudo ~/Anaconda2-5.1.0-Linux-ppc64le.sh '
               '-p /opt/anaconda2')
        rc = sub_proc_display(cmd)
        if rc == 0:
            print('\nLicense accepted. Acceptance script will be run quietly '
                  'on remaining servers.')
        else:
            log.error("Anaconda license acceptance required to continue!")
            sys.exit('Exiting')
    return rc


class YAMLVault(yaml.YAMLObject):
    yaml_tag = u'!vault'

    def __init__(self, ansible_become_pass):
        self.ansible_become_pass = ansible_become_pass

    @classmethod
    def from_yaml(cls, loader, node):
        return YAMLVault(node.value)

    @classmethod
    def to_yaml(cls, dumper, data):
        return dumper.represent_scalar(cls.yaml_tag, data.ansible_become_pass)


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
