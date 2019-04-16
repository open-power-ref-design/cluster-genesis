#! /usr/bin/env python
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

from __future__ import nested_scopes, generators, division, absolute_import, \
    with_statement, print_function, unicode_literals

import argparse
import glob
import os
import platform
import re
import sys
from shutil import copy2
import calendar
import time
import yaml
import json
from getpass import getpass
import pwd
import grp
import click

import lib.logger as logger
from repos import PowerupRepo, PowerupRepoFromDir, PowerupYumRepoFromRepo, \
    PowerupAnaRepoFromRepo, PowerupRepoFromRpm, setup_source_file, \
    PowerupPypiRepoFromRepo, get_name_dir
from software_hosts import get_ansible_inventory, validate_software_inventory
from lib.utilities import sub_proc_display, sub_proc_exec, heading1, Color, \
    get_selection, get_yesno, rlinput, bold, ansible_pprint, replace_regex, \
    firewall_add_services
from lib.genesis import GEN_SOFTWARE_PATH, get_ansible_playbook_path
from nginx_setup import nginx_setup


class software(object):
    """ Software installation class. The prep method is used to setup
    repositories, download files to the installer node or perform other
    initialization activities. The install method implements the actual
    installation.
    """
    def __init__(self, eval_ver=False, non_int=False):
        self.log = logger.getlogger()
        self.my_name = sys.modules[__name__].__name__
        self.yum_powerup_repo_files = []
        self.eval_ver = eval_ver
        self.non_int = non_int
        yaml.add_constructor(YAMLVault.yaml_tag, YAMLVault.from_yaml)

        self.state = {'EPEL Repository': '-',
                      'CUDA Toolkit Repository': '-',
                      'PowerAI content': '-',
                      'PowerAI Base Repository': '-',
                      'PowerAIE license content': '-',
                      'Dependent Packages Repository': '-',
                      'Python Package Repository': '-',
                      'CUDA dnn content': '-',
                      'CUDA nccl2 content': '-',
                      'Anaconda content': '-',
                      'Anaconda Free Repository': '-',
                      'Anaconda Main Repository': '-',
                      'Conda-forge Repository': '-',
                      'Spectrum conductor content': '-',
                      'Spectrum conductor content entitlement': '-',
                      'Spectrum DLI content': '-',
                      'Spectrum DLI content entitlement': '-',
                      'Nginx Web Server': '-',
                      'Firewall': '-'}
        self.repo_id = {'EPEL Repository': 'epel-ppc64le',
                        'CUDA Toolkit Repository': 'cuda',
                        'PowerAI Base Repository': 'powerai',
                        'Dependent Packages Repository': 'dependencies',
                        'Python Package Repository': 'pypi'}

        try:
            self.pkgs = yaml.full_load(open(GEN_SOFTWARE_PATH +
                                            'pkg-lists112.yml'))
        except IOError:
            self.log.error('Error opening the pkg lists file (pkg-lists112.yml)')
            sys.exit('Exit due to critical error')

        if self.eval_ver:
            try:
                self.sw_vars = yaml.full_load(open(GEN_SOFTWARE_PATH +
                                                   'software-vars-eval.yml'))
            except IOError:
                # if no eval vars file exist, see if the license var file exists
                # and start with that
                try:
                    self.sw_vars = yaml.full_load(open(GEN_SOFTWARE_PATH +
                                                       'software-vars.yml'))
                except IOError:
                    self.log.info('Creating software vars yaml file')
                    self.sw_vars = {}
                    self.sw_vars['init-time'] = time.ctime()
                    self.README()
                    input('\nPress enter to continue')
                # clear out any licensed version of PowerAI files
                else:
                    self.sw_vars['content_files']['powerai-enterprise-license'] = ''
                    self.sw_vars['content_files']['spectrum-conductor'] = ''
                    self.sw_vars['content_files']['spectrum-conductor-entitlement'] = ''
                    self.sw_vars['content_files']['spectrum-dli'] = ''
                    self.sw_vars['content_files']['spectrum-dli-entitlement'] = ''
                    self.sw_vars['prep-timestamp'] = calendar.timegm(time.gmtime())
        else:
            try:
                self.sw_vars = yaml.full_load(open(GEN_SOFTWARE_PATH +
                                                   'software-vars.yml'))
            except IOError:
                # if no licensed vars file exist, see if the eval var file exists
                # and start with that
                try:
                    self.sw_vars = yaml.full_load(
                        open(GEN_SOFTWARE_PATH + 'software-vars-eval.yml'))
                except IOError:
                    self.log.info('Creating software vars yaml file')
                    self.sw_vars = {}
                    self.sw_vars['init-time'] = time.ctime()
                    self.README()
                    input('\nPress enter to continue')
                # clear out any eval version of PowerAI Enterprise files
                else:
                    self.sw_vars['content_files']['powerai-enterprise-license'] = ''
                    self.sw_vars['content_files']['spectrum-conductor'] = ''
                    self.sw_vars['content_files']['spectrum-conductor-entitlement'] = ''
                    self.sw_vars['content_files']['spectrum-dli'] = ''
                    self.sw_vars['content_files']['spectrum-dli-entitlement'] = ''
                    self.sw_vars['prep-timestamp'] = calendar.timegm(time.gmtime())

        if not isinstance(self.sw_vars, dict):
            self.sw_vars = {}
            self.sw_vars['init-time'] = time.ctime()

        if 'prep-timestamp' not in self.sw_vars:
            self.sw_vars['prep-timestamp'] = 0

        if self.eval_ver:
            self.eval_prep_timestamp = self.sw_vars['prep-timestamp']
            try:
                temp = yaml.full_load(open(GEN_SOFTWARE_PATH +
                                           'software-vars.yml'))
                self.lic_prep_timestamp = temp['prep-timestamp']
            except (IOError, KeyError):
                self.lic_prep_timestamp = 0
        else:
            self.lic_prep_timestamp = self.sw_vars['prep-timestamp']
            try:
                temp = yaml.full_load(open(GEN_SOFTWARE_PATH +
                                           'software-vars-eval.yml'))
                self.eval_prep_timestamp = temp['prep-timestamp']
            except (IOError, KeyError):
                self.eval_prep_timestamp = 0

        if ('ana_powerup_repo_channels' not in self.sw_vars or not
                isinstance(self.sw_vars['ana_powerup_repo_channels'], list)):
            self.sw_vars['ana_powerup_repo_channels'] = []
        if ('yum_powerup_repo_files' not in self.sw_vars or not
                isinstance(self.sw_vars['yum_powerup_repo_files'], dict)):
            self.sw_vars['yum_powerup_repo_files'] = {}
        if ('content_files' not in self.sw_vars or not
                isinstance(self.sw_vars['content_files'], dict)):
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

        # When searching for files in other web servers, the fileglobs are converted to
        # regular expressions. An asterisk (*) after a bracket is converted to a
        # regular extression of [0-9]{0,3} Other asterisks are converted to regular
        # expression of .*
        try:
            file_lists = yaml.full_load(open(GEN_SOFTWARE_PATH +
                                             'file-lists112.yml'))
        except IOError:
            self.log.info('Error while reading installation file lists for PowerAI Enterprise')
            sys.exit('exiting')
            input('\nPress enter to continue')
        else:
            if self.eval_ver:
                self.globs = file_lists['globs_eval']
                self.files = file_lists['files_eval']
            else:
                self.globs = file_lists['globs']
                self.files = file_lists['files']

        # If empty, initialize software_vars content and repo info
        # from software server directory
        update = False
        for item in self.state:
            if 'content' in item:
                item_key = get_name_dir(item)
                item_dir = item_key
                if item_dir.endswith('-entitlement'):
                    item_dir = item_dir[:-12]
                exists = glob.glob(f'/srv/{item_dir}/**/{self.files[item]}',
                                   recursive=True)
                if not exists:
                    exists = glob.glob(f'/srv/{item_dir}/**/{self.globs[item]}',
                                       recursive=True)
                    if exists:
                        self.sw_vars['content_files'][item_key] = exists[0]

                if item_key not in self.sw_vars['content_files']:
                    update = True
                    if exists:
                        self.sw_vars['content_files'][item_key] = exists[0]
                    else:
                        self.sw_vars['content_files'][item_key] = ''
        if update:
            self.log.info('Content installation pointers were updated.\n'
                          'To insure content levels are correct, run \n'
                          'pup software --prep <module name>\n')

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
        if self.eval_ver:
            with open(GEN_SOFTWARE_PATH + 'software-vars-eval.yml', 'w') as f:
                f.write('# Do not edit this file. This file is autogenerated.\n')
            with open(GEN_SOFTWARE_PATH + 'software-vars-eval.yml', 'a') as f:
                yaml.dump(self.sw_vars, f, default_flow_style=False)
        else:
            with open(GEN_SOFTWARE_PATH + 'software-vars.yml', 'w') as f:
                f.write('# Do not edit this file. This file is autogenerated.\n')
            with open(GEN_SOFTWARE_PATH + 'software-vars.yml', 'a') as f:
                yaml.dump(self.sw_vars, f, default_flow_style=False)
        if os.path.isfile(self.vault_pass_file):
            os.remove(self.vault_pass_file)

    def README(self):
        print(bold('\nPowerAI Enterprise software installer module'))
        text = ('\nThis module installs the PowerAI Enterprise software '
                'to a cluster of OpenPOWER nodes.\n\n'
                'PowerAI Enterprise installation involves three steps;\n'
                '\n  1 - Preparation. Prepares the installer node software server.\n'
                '       The preparation phase may be run multiple times if needed.\n'
                '       usage: pup software --prep paie112\n'
                '\n  2 - Initialization of client nodes\n'
                '       usage: pup software --init-clients paie112\n'
                '\n  3 - Installation. Install software on the client nodes\n'
                '       usage: pup software --install paie112\n\n'
                'Before beginning, the following files should be extracted from the\n'
                'PowerAI Enterprise binary file and present on this node;\n'
                '- mldl-repo-local-5.4.0-*.ppc64le.rpm\n'
                '- powerai-enterprise-license-1.1.2-*.ppc64le.rpm\n'
                '- conductor2.3.0.0_ppc64le.bin\n'
                '- conductor_entitlement.dat\n'
                '- dli-1.2.1.0_ppc64le.bin\n'
                '- dli_entitlement.dat\n\n'
                'The following files must also be downloaded to this node;\n'
                '- cudnn-10.0-linux-ppc64le-v7.3.1.20.tgz\n'
                '- nccl_2.3.4-1+cuda10.0_ppc64le.txz\n'
                'For installation status: pup software --status paie112\n'
                'To redisplay this README: pup software --README paie112\n\n'
                'Note: The \'pup\' cli supports tab autocompletion.\n\n')
        print(text)

    def status(self, which='all'):
        self.status_prep(which)

    def status_prep(self, which='all'):

        def yum_repo_status(item):
            repodata = glob.glob(self.repo_dir.format(repo_id=self.repo_id[item]) +
                                 '/**/repodata', recursive=True)
            sw_vars_data = (f'{self.repo_id[item]}-powerup.repo' in
                            self.sw_vars['yum_powerup_repo_files'])
            if repodata and sw_vars_data:
                self.state[item] = f'{item} is setup'

        def content_status(item):
            ver_mis = False
            item_key = get_name_dir(item)
            item_dir = item_key
            if item_dir.endswith('-entitlement'):
                item_dir = item_dir[:-12]
            exists = glob.glob(f'/srv/{item_dir}/**/{self.globs[item]}',
                               recursive=True)

            sw_vars_data = item_key in self.sw_vars['content_files']

            if exists and sw_vars_data:
                if self.files[item] in self.sw_vars['content_files'][item_key]:
                    self.state[item] = ('Present in the POWER-Up server')
                else:
                    ver_mis = True
                    self.state[item] = (Color.yellow +
                                        'Present but not at release level' +
                                        Color.endc)
            return ver_mis

        ver_mis = False
        for item in self.state:
            self.state[item] = '-'

            # Content files status
            if 'content' in item:
                ret = content_status(item)
                ver_mis = ver_mis or ret
                continue

            # yum repos status
            if item in self.repo_id:
                if 'Python' in item:
                    if os.path.exists(f'/srv/repos/{self.repo_id[item]}/simple/') and \
                            len(os.listdir(f'/srv/repos/{self.repo_id[item]}/simple/')) >= 1:
                        self.state[item] = f'{item} is setup'
                else:
                    yum_repo_status(item)
                continue

            # Firewall status
            if item == 'Firewall':
                cmd = 'firewall-cmd --list-all'
                resp, err, rc = sub_proc_exec(cmd)
                if re.search(r'services:\s+.+http', resp):
                    self.state[item] = "Running and configured for http"
                continue

            # Nginx web server status
            if item == 'Nginx Web Server':
                cmd = 'curl -I 127.0.0.1'
                resp, err, rc = sub_proc_exec(cmd)
                if 'HTTP/1.1 200 OK' in resp:
                    self.state[item] = 'Nginx is configured and running'
                continue

            # Anaconda Repo Free status
            if item == 'Anaconda Free Repository':
                repodata_noarch = glob.glob(f'/srv/repos/anaconda/pkgs/free'
                                            '/noarch/repodata.json', recursive=True)
                repodata = glob.glob(f'/srv/repos/anaconda/pkgs/free'
                                     '/linux-ppc64le/repodata.json', recursive=True)
                if repodata and repodata_noarch:
                    self.state[item] = f'{item} is setup'
                continue

            # Anaconda Main repo status
            if item == 'Anaconda Main Repository':
                repodata_noarch = glob.glob(f'/srv/repos/anaconda/pkgs/main'
                                            '/noarch/repodata.json', recursive=True)
                repodata = glob.glob(f'/srv/repos/anaconda/pkgs/main'
                                     '/linux-ppc64le/repodata.json', recursive=True)
                if repodata and repodata_noarch:
                    self.state[item] = f'{item} is setup'
                continue

            # Anaconda Conda-forge repo status
            if item == 'Conda-forge Repository':
                repodata = glob.glob(f'/srv/repos/anaconda/conda-forge'
                                     '/noarch/repodata.json', recursive=True)
                if repodata:
                    self.state[item] = f'{item} is setup'
                continue

        exists = True
        if which == 'all':
            heading1('Preparation Summary')
            for item in self.state:
                status = self.state[item]
                it = (item + '                              ')[:38]
                print(f'  {it:<39} : ' + status)
                exists = exists and self.state[item] != '-'

            gtg = 'Preparation complete. '
            if ver_mis:
                gtg += 'Some content is not at release level.'
            for item in self.state.values():
                if item == '-':
                    gtg = f'{Color.red}Preparation incomplete{Color.endc}'
            print(f'\n{bold(gtg)}\n')
        else:
            exists = self.state[which] != '-'

        return exists

    def prep(self, eval_ver=False, non_int=False):
        # Invoked with --prep flag
        # Basic check of the state of yum repos
        print()
        self.sw_vars['prep-timestamp'] = calendar.timegm(time.gmtime())
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
        firewall_add_services('http')

        self.status_prep(which='Firewall')
        if self.state['Firewall'] == '-':
            self.log.info('Failed to configure firewall')
        else:
            self.log.info(self.state['Firewall'])

        # nginx setup
        heading1('Set up Nginx')
        nginx_setup()
        self.status_prep(which='Nginx Web Server')
        if self.state['Nginx Web Server'] == '-':
            self.log.info('nginx web server is not running')
        else:
            self.log.info(self.state['Nginx Web Server'])

        # Get PowerAI base
        name = 'PowerAI content'
        heading1('Setting up the PowerAI base repository\n')
        pai_src = self.globs['PowerAI content']
        pai_url = ''  # No default public url exists
        repo_id = 'powerai'
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

        # Get PowerAI Enterprise license file
        name = 'PowerAIE license content'
        heading1(f'Set up {name.title()} \n')
        lic_src = self.globs[name]
        exists = self.status_prep(name)
        lic_url = ''

        if f'{name}_alt_url' in self.sw_vars:
            alt_url = self.sw_vars[f'{name}_alt_url']
        else:
            alt_url = 'http://'

        if exists:
            self.log.info('PowerAI Enterprise license exists already in the POWER-Up server')

        if not exists or get_yesno(f'Copy a new {name.title()} file '):
            src_path, dest_path, state = setup_source_file(name, lic_src, lic_url,
                                                           alt_url=alt_url)
            if src_path and 'http' in src_path:
                self.sw_vars[f'{name}_alt_url'] = os.path.dirname(src_path) + '/'
            if dest_path:
                self.sw_vars['content_files'][get_name_dir(name)] = dest_path

        # Get Spectrum Conductor
        name = 'Spectrum conductor content'
        heading1(f'Set up {name.title()} \n')
        spc_src = self.globs[name]
        entitlement = self.globs[name + ' entitlement']
        exists = self.status_prep(name)
        spc_url = ''

        if f'{name}_alt_url' in self.sw_vars:
            alt_url = self.sw_vars[f'{name}_alt_url']
        else:
            alt_url = 'http://'

        if exists:
            self.log.info('Spectrum conductor content exists already in the POWER-Up server')

        if not exists or get_yesno(f'Copy a new {name.title()} file '):
            src_path, dest_path, state = setup_source_file(name, spc_src, spc_url,
                                                           alt_url=alt_url, src2=entitlement)
            if src_path and 'http' in src_path:
                self.sw_vars[f'{name}_alt_url'] = os.path.dirname(src_path) + '/'
            if dest_path:
                self.sw_vars['content_files'][get_name_dir(name)] = dest_path
            if state:
                self.sw_vars['content_files'][get_name_dir(name) + '-entitlement'] = (
                    os.path.dirname(dest_path) + '/' + entitlement)

        # Get Spectrum DLI
        name = 'Spectrum DLI content'
        heading1(f'Set up {name.title()} \n')
        spdli_src = self.globs[name]
        entitlement = self.globs[name + ' entitlement']
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
                                                           alt_url=alt_url, src2=entitlement)
            if src_path and 'http' in src_path:
                self.sw_vars[f'{name}_alt_url'] = os.path.dirname(src_path) + '/'
            if dest_path:
                self.sw_vars['content_files'][get_name_dir(name)] = dest_path
            if state:
                self.sw_vars['content_files'][get_name_dir(name) + '-entitlement'] = (
                    os.path.dirname(dest_path) + '/' + entitlement)

        # Setup repository for cuda packages. The Cuda public repo is enabled
        # and the package list can be downloaded from there or alternately the
        # cuda packages repo can be created from a local directory or an
        # existing repository on another node.
        repo_id = 'cuda'
        repo_name = 'Cuda toolkit'
        baseurl = 'http://developer.download.nvidia.com/compute/cuda/repos/rhel7/ppc64le'
        gpgkey = f'{baseurl}/7fa2af80.pub'
        heading1(f'Set up {repo_name} repository')
        # list to str
        pkg_list = ' '.join(self.pkgs['cuda_pkgs'])

        if f'{repo_id}_alt_url' in self.sw_vars:
            alt_url = self.sw_vars[f'{repo_id}_alt_url']
        else:
            alt_url = None
        # Enable the public repo
        repo_cuda = PowerupRepo(repo_id, repo_name)
        dot_repo_content = repo_cuda.get_yum_dotrepo_content(url=baseurl, gpgkey=gpgkey)
        repo_cuda.write_yum_dot_repo_file(dot_repo_content)

        exists = self.status_prep(which='CUDA Toolkit Repository')
        if exists:
            self.log.info(f'The {repo_name} repository exists already'
                          ' in the POWER-Up server')
            pr_str = (f'\nDo you want to resync the {repo_name} repository'
                      ' at this time\n')
        else:
            pr_str = (f'\nDo you want to create the {repo_name} repository'
                      ' at this time\n')

        ch = 'S'
        if get_yesno(prompt=pr_str, yesno='Y/n'):
            if platform.machine() == self.arch:
                ch, item = get_selection('Sync required packages from public repo\n'
                                         'Create from package files in a local Directory\n'
                                         'Sync from an alternate Repository\n'
                                         'Skip',
                                         'E\nD\nR\nS',
                                         'Repository source? ')
            else:
                ch, item = get_selection('Create from package files in a local Directory\n'
                                         'Sync from an alternate Repository\n'
                                         'Skip',
                                         'D\nR\nS',
                                         'Repository source? ')

        if ch == 'E':
            repo = PowerupRepo(repo_id, repo_name)
            repo_dir = repo.get_repo_dir()
            self._add_dependent_packages(repo_dir, pkg_list)
            repo.create_meta()
            content = repo.get_yum_dotrepo_content(gpgcheck=0, client=True)
            filename = repo_id + '-powerup.repo'
            self.sw_vars['yum_powerup_repo_files'][filename] = content

        elif ch == 'D':
            repo = PowerupRepoFromDir(repo_id, repo_name)
            repo_dir = repo.get_repo_dir()
            if f'{repo_id}_src_dir' in self.sw_vars:
                src_dir = self.sw_vars[f'{repo_id}_src_dir']
            else:
                src_dir = None
            src_dir, dest_dir = repo.copy_dirs(src_dir)
            if src_dir:
                self.sw_vars[f'{repo_id}_src_dir'] = src_dir
                repo.create_meta()
                content = repo.get_yum_dotrepo_content(gpgcheck=0, client=True)
                filename = repo_id + '-powerup.repo'
                self.sw_vars['yum_powerup_repo_files'][filename] = content

        elif ch == 'R':
            if f'{repo_id}_alt_url' in self.sw_vars:
                alt_url = self.sw_vars[f'{repo_id}_alt_url']
            else:
                alt_url = None

            repo = PowerupYumRepoFromRepo(repo_id, repo_name)
            repo_dir = repo.get_repo_dir()
            url = repo.get_repo_url(baseurl, alt_url, contains=[repo_id],
                                    filelist=['cuda-10-*-*'])
            if url:
                if not url == baseurl:
                    self.sw_vars[f'{repo_id}_alt_url'] = url
                # Set up access to the repo
                content = repo.get_yum_dotrepo_content(url, gpgcheck=0)
                repo.write_yum_dot_repo_file(content)

                repo.sync()
                repo.create_meta()

                # Prep setup of POWER-Up client access to the repo copy
                content = repo.get_yum_dotrepo_content(gpgcheck=0, client=True)
                filename = repo_id + '-powerup.repo'
                self.sw_vars['yum_powerup_repo_files'][filename] = content
                self.log.info('Repository setup complete')

        else:
            print(f'{repo_name} repository not updated')
        if ch != 'S':
            repo_dir += '/cuda-[1-9][0-9].[0-9]*.[0-9]*'
            files = glob.glob(repo_dir, recursive=True)
            if files:
                self.sw_vars['cuda'] = re.search(r'cuda-\d+\.\d+\.\d+',
                                                 ' '.join(files)).group(0)
            else:
                self.log.error('No cuda toolkit file found in cuda repository')

        # Get cudnn tar file
        name = 'CUDA dnn content'
        heading1(f'Set up {name.title()} \n')
        cudnn_src = self.globs[name]
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
            if src_path and 'http' in src_path:
                self.sw_vars[f'{name}_alt_url'] = os.path.dirname(src_path) + '/'

        # Get cuda nccl2 tar file
        name = 'CUDA nccl2 content'
        heading1(f'Set up {name.title()} \n')
        nccl2_src = self.globs[name]
        nccl2_url = ''

        if f'{name}_alt_url' in self.sw_vars:
            alt_url = self.sw_vars[f'{name}_alt_url']
        else:
            alt_url = None

        exists = self.status_prep(name)

        if exists:
            self.log.info('CUDA nccl2 content exists already in the POWER-Up server')

        if not exists or get_yesno(f'Copy a new {name.title()} file '):
            src_path, dest_path, state = setup_source_file(name, nccl2_src, nccl2_url,
                                                           alt_url=alt_url)

            if dest_path:
                self.sw_vars['content_files'][get_name_dir(name)] = dest_path
            if src_path and 'http' in src_path:
                self.sw_vars[f'{name}_alt_url'] = os.path.dirname(src_path) + '/'

        # Setup repository for redhat dependent packages. This is intended to deal
        # specifically with redhat packages requiring red hat subscription for access,
        # however dependent packages can come from any YUM repository enabled on the
        # POWER-Up Installer node. Alternately the dependent packages repo can be
        # Created from a local directory or an existing repository on another node.
        repo_id = 'dependencies'
        repo_name = 'Dependencies'
        baseurl = ''
        heading1(f'Set up {repo_name} repository')
        # list to str
        dep_list = ' '.join(self.pkgs['yum_pkgs'])

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

        if f'{repo_id}_alt_url' in self.sw_vars:
            alt_url = self.sw_vars[f'{repo_id}_alt_url']
        else:
            alt_url = None

        exists = self.status_prep(which='Dependent Packages Repository')
        if exists:
            self.log.info(f'The {repo_name} repository exists already'
                          ' in the POWER-Up server')
            pr_str = (f'\nDo you want to resync the {repo_name} repository'
                      ' at this time\n')
        else:
            pr_str = (f'\nDo you want to create the {repo_name} repository'
                      ' at this time\n')

        ch = 'S'
        if get_yesno(prompt=pr_str, yesno='Y/n'):
            if platform.machine() == self.arch:
                ch, item = get_selection('Sync required dependent packages from Enabled YUM repos\n'
                                         'Create from package files in a local Directory\n'
                                         'Sync from an alternate Repository\n'
                                         'Skip',
                                         'E\nD\nR\nS',
                                         'Repository source? ')
            else:
                ch, item = get_selection('Create from package files in a local Directory\n'
                                         'Sync from an alternate Repository\n'
                                         'Skip',
                                         'D\nR\nS',
                                         'Repository source? ')

        if ch == 'E':
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

        elif ch == 'D':
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

        elif ch == 'R':
            if f'{repo_id}_alt_url' in self.sw_vars:
                alt_url = self.sw_vars[f'{repo_id}_alt_url']
            else:
                alt_url = None

            repo = PowerupYumRepoFromRepo(repo_id, repo_name)

            url = repo.get_repo_url(baseurl, alt_url, contains=[repo_id],
                                    filelist=['bzip2-*'])
            if url:
                if not url == baseurl:
                    self.sw_vars[f'{repo_id}_alt_url'] = url
                # Set up access to the repo
                content = repo.get_yum_dotrepo_content(url, gpgcheck=0)
                repo.write_yum_dot_repo_file(content)

                repo.sync()
                repo.create_meta()

                # Setup local access to the new repo copy in /srv/repo/
                if platform.machine() == self.arch:
                    content = repo.get_yum_dotrepo_content(gpgcheck=0, local=True)
                    repo.write_yum_dot_repo_file(content)
                # Prep setup of POWER-Up client access to the repo copy
                content = repo.get_yum_dotrepo_content(gpgcheck=0, client=True)
                filename = repo_id + '-powerup.repo'
                self.sw_vars['yum_powerup_repo_files'][filename] = content
                self.log.info('Repository setup complete')

        else:
            print(f'{repo_name} repository not updated')

        # Get Anaconda
        ana_name = 'Anaconda content'
        ana_src = self.globs[ana_name]
        ana_url = 'https://repo.continuum.io/archive/'
        if f'{ana_name}_alt_url' in self.sw_vars:
            alt_url = self.sw_vars[f'{ana_name}_alt_url']
        else:
            alt_url = 'http://'

        exists = self.status_prep(which=ana_name)

        heading1('Set up Anaconda\n')

        if exists:
            self.log.info(f'The {ana_name} exists already '
                          'in the POWER-Up server.')

        if not exists or get_yesno(f'Recopy {ana_name} '):

            src_path, dest_path, state = setup_source_file(ana_name, ana_src, ana_url,
                                                           alt_url=alt_url)
            if dest_path:
                self.sw_vars['content_files'][get_name_dir(ana_name)] = dest_path
            if src_path and 'http' in src_path:
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
        if ch in 'Y':
            # if not exists or ch == 'F':
            url = repo.get_repo_url(baseurl, alt_url, contains=['free', 'linux',
                                    'ppc64le'], excludes=['noarch', 'main'],
                                    filelist=['conda-4.3*'])
            if url:
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
                rejlist = ','.join(self.pkgs['anaconda_free_pkgs']['reject_list'])

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
        if ch in 'Y':
            url = repo.get_repo_url(baseurl, alt_url, contains=['main', 'linux',
                                    'ppc64le'], excludes=['noarch', 'free'],
                                    filelist=['numpy-1.15*'])
            if url:
                if not url == baseurl:
                    self.sw_vars[f'{vars_key}-alt-url'] = url

                al = ','.join(self.pkgs['anaconda_main_pkgs']['accept_list'])
                rl = ','.join(self.pkgs['anaconda_main_pkgs']['reject_list'])

                dest_dir = repo.sync_ana(url, acclist=al)
                # dest_dir = repo.sync_ana(url)
                dest_dir = dest_dir[4 + dest_dir.find('/srv'):5 + dest_dir.find('main')]
                # form .condarc channel entry. Note that conda adds
                # the corresponding 'noarch' channel automatically.
                channel = f'  - http://{{{{ host_ip.stdout }}}}{dest_dir}'
                if channel not in self.sw_vars['ana_powerup_repo_channels']:
                    self.sw_vars['ana_powerup_repo_channels'].insert(0, channel)
                noarch_url = os.path.split(url.rstrip('/'))[0] + '/noarch/'
                repo.sync_ana(noarch_url, rejlist=rl)

        # Setup Anaconda conda-forge Repo.  (not a YUM repo)
        repo_id = 'anaconda'
        repo_name = 'Conda-forge noarch Repository'
        baseurl = 'https://conda.anaconda.org/conda-forge/noarch/'
        heading1(f'Set up {repo_name}\n')

        vars_key = get_name_dir(repo_name)  # format the name
        if f'{vars_key}-alt-url' in self.sw_vars:
            alt_url = self.sw_vars[f'{vars_key}-alt-url']
        else:
            alt_url = None

        exists = self.status_prep(which='Conda-forge Repository')
        if exists:
            self.log.info('The Conda-forge Repository exists already'
                          ' in the POWER-Up server\n')

        repo = PowerupAnaRepoFromRepo(repo_id, repo_name)

        ch = repo.get_action(exists)
        if ch in 'Y':
            url = repo.get_repo_url(baseurl, alt_url, contains=['noarch'],
                                    excludes=['main'],
                                    filelist=['configparser-3.5*'])
            if url:
                if not url == baseurl:
                    self.sw_vars[f'{vars_key}-alt-url'] = url

                al = ','.join(self.pkgs['conda_forge_noarch_pkgs']['accept_list'])

                dest_dir = repo.sync_ana(url, acclist=al)
                dest_dir = dest_dir[4 + dest_dir.find('/srv'):7 + dest_dir.find('noarch')]
                # form .condarc channel entry. Note that conda adds
                # the corresponding 'noarch' channel automatically.
                channel = f'  - http://{{{{ host_ip.stdout }}}}{dest_dir}'
                if channel not in self.sw_vars['ana_powerup_repo_channels']:
                    self.sw_vars['ana_powerup_repo_channels'].insert(0, channel)

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

        pkg_list = ' '.join(self.pkgs['python_pkgs'])
        if not exists or ch == 'Y':
            pkg_list = ' '.join(self.pkgs['python_pkgs'])
            pkg3_list = ' '.join(self.pkgs['python3_specific_pkgs'])
            url = repo.get_repo_url(baseurl, alt_url, name=repo_name,
                                    contains=repo_id, filelist=['Flask-*'])
            if url == baseurl:
                repo.sync(pkg_list)
                repo.sync(pkg3_list, py_ver=36)
            elif url:
                self.sw_vars[f'{repo_id}_alt_url'] = url
                repo.sync(pkg_list, url + 'simple')
                repo.sync(pkg3_list, url + 'simple', py_ver=36)

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
        if ch in 'Y':
            url = repo.get_repo_url(baseurl, alt_url, contains=[repo_id],
                                    filelist=['epel-release-*'])
            if url:
                if not url == baseurl:
                    self.sw_vars[f'{repo_id}_alt_url'] = url
                    content = repo.get_yum_dotrepo_content(url, gpgkey=gpgkey)
                else:
                    content = repo.get_yum_dotrepo_content(url, gpgkey=gpgkey,
                                                           metalink=True)
                repo.write_yum_dot_repo_file(content)

            if url:
                repo.sync()
                # recheck status after sync.
                exists = self.status_prep(which='EPEL Repository')
                if not exists:
                    repo.create_meta()
                else:
                    repo.create_meta(update=True)

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
                                     'Repository source? ', allow_none=True)
            if ch != 'N':
                if ch == 'rpm':
                    repo = PowerupRepoFromRpm(repo_id, repo_name)

                    if f'{repo_id}_src_rpm_dir' in self.sw_vars:
                        src_path = self.sw_vars[f'{repo_id}_src_rpm_dir']
                    else:
                        # default is to search recursively under all /home/
                        # directories
                        src_path = '/home/**/*.rpm'
                    rpm_path = repo.get_rpm_path(src_path)
                    if rpm_path:
                        self.sw_vars[f'{repo_id}_src_rpm_dir'] = rpm_path
                        repo.copy_rpm()
                        repodata_dir = repo.extract_rpm()
                        if repodata_dir:
                            content = repo.get_yum_dotrepo_content(
                                repo_dir=repodata_dir, gpgcheck=0, local=True)
                        else:
                            content = repo.get_yum_dotrepo_content(gpgcheck=0,
                                                                   local=True)
                            repo.create_meta()
                        repo.write_yum_dot_repo_file(content)
                        content = repo.get_yum_dotrepo_content(
                            repo_dir=repodata_dir, gpgcheck=0, client=True)
                        filename = repo_id + '-powerup.repo'
                        self.sw_vars['yum_powerup_repo_files'][filename] = content
                    else:
                        self.log.info('No path chosen. Skipping create custom '
                                      'repository.')

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
                        content = repo.get_yum_dotrepo_content(gpgcheck=0,
                                                               local=True)
                        repo.write_yum_dot_repo_file(content)
                        content = repo.get_yum_dotrepo_content(gpgcheck=0,
                                                               client=True)
                        filename = repo_id + '-powerup.repo'
                        self.sw_vars['yum_powerup_repo_files'][filename] = content
                elif ch == 'repo':
                    baseurl = 'http://'

                    if f'{repo_id}_alt_url' in self.sw_vars:
                        alt_url = self.sw_vars[f'{repo_id}_alt_url']
                    else:
                        alt_url = None

                    repo = PowerupYumRepoFromRepo(repo_id, repo_name)

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
        # write software-vars file. Although also done in __del__, the software
        # vars files are written here in case the user is running all phases of
        # install
        if not os.path.exists(GEN_SOFTWARE_PATH):
            os.mkdir(GEN_SOFTWARE_PATH)
        if self.eval_ver:
            with open(GEN_SOFTWARE_PATH + 'software-vars-eval.yml', 'w') as f:
                f.write('# Do not edit this file. This file is autogenerated.\n')
            with open(GEN_SOFTWARE_PATH + 'software-vars-eval.yml', 'a') as f:
                yaml.dump(self.sw_vars, f, default_flow_style=False)
        else:
            with open(GEN_SOFTWARE_PATH + 'software-vars.yml', 'w') as f:
                f.write('# Do not edit this file. This file is autogenerated.\n')
            with open(GEN_SOFTWARE_PATH + 'software-vars.yml', 'a') as f:
                yaml.dump(self.sw_vars, f, default_flow_style=False)

    def _add_dependent_packages(self, repo_dir, dep_list):
        cmd = (f'yumdownloader --archlist={self.arch} --destdir '
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
        if self.eval_ver:
            cmd = ('{} -i {} {}init_clients.yml --extra-vars "@{}" '
                   .format(get_ansible_playbook_path(),
                           self.sw_vars['ansible_inventory'],
                           GEN_SOFTWARE_PATH,
                           GEN_SOFTWARE_PATH + "software-vars-eval.yml"))
        else:
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
                    print(f"stdout:\n{ansible_pprint(resp)}\n")
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
        # client_sudo_pass_validated = False

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

        sudo_test = f'{GEN_SOFTWARE_PATH}{self.my_name}_ansible/sudo_test.yml'
        cmd = (f'{get_ansible_playbook_path()} '
               f'-i {self.sw_vars["ansible_inventory"]} '
               f'{GEN_SOFTWARE_PATH}{self.my_name}_ansible/run.yml '
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
                print(f"stdout:\n{ansible_pprint(resp)}\n")
            if err != '':
                print(f"stderr:\n{err}\n")
            return False

    def _unlock_vault(self, validate=True):
        log = logger.getlogger()
        while True:
            if self.sw_vars['ansible_become_pass'] is None:
                return False
            elif self.vault_pass is None:
                self.vault_pass = getpass(prompt="\nClient sudo password: ")
            with open(self.vault_pass_file, 'w') as vault_pass_file_out:
                vault_pass_file_out.write(self.vault_pass)
            os.chmod(self.vault_pass_file, 0o600)

            if not validate or self._validate_ansible_become_pass(None):
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
        print()
        if self.eval_ver:
            if self.lic_prep_timestamp > self.eval_prep_timestamp:
                print(bold('You have requested to install the evaluation version'))
                print('of PowerAI Enterprise but last ran preparation for ')
                print('licensed version.')
                resp = get_yesno('Continue with evaluation installation ')
                if not resp:
                    sys.exit('Installation ended by user')
        else:
            if self.eval_prep_timestamp > self.lic_prep_timestamp:
                print(bold('You have requested to install the licensed version'))
                print('of PowerAI Enterprise but last ran preparation for ')
                print('evaluation version.')
                resp = get_yesno('Continue with licensed installation ')
                if not resp:
                    sys.exit('Installation ended by user')

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

        ana_ver = re.search(r'(anaconda\d)-\d', self.sw_vars['content_files']
                            ['anaconda'], re.IGNORECASE).group(1).lower()
        _set_spectrum_conductor_install_env(self.sw_vars['ansible_inventory'],
                                            'spark')
        _set_spectrum_conductor_install_env(self.sw_vars['ansible_inventory'],
                                            'dli', ana_ver)

        install_tasks = yaml.full_load(
            open(GEN_SOFTWARE_PATH + f'{self.my_name}_install_procedure.yml'))
        for task in install_tasks:
            heading1(f"Client Node Action: {task['description']}")
            if task['description'] == "Install Anaconda installer":
                _interactive_anaconda_license_accept(
                    self.sw_vars['ansible_inventory'],
                    self.sw_vars['content_files']['anaconda'])
            elif (task['description'] ==
                    "Check PowerAI Enterprise License acceptance"):
                _interactive_paie_license_accept(
                    self.sw_vars['ansible_inventory'])
            extra_args = ''
            if 'hosts' in task:
                extra_args = f"--limit \'{task['hosts']},localhost\'"
            self._run_ansible_tasks(task['tasks'], extra_args)
        print('Done')

    def _run_ansible_tasks(self, tasks_path, extra_args=''):
        log = logger.getlogger()
        tasks_path = f'{self.my_name}_ansible/' + tasks_path
        if self.sw_vars['ansible_become_pass'] is not None:
            extra_args += ' --vault-password-file ' + self.vault_pass_file
        elif 'become:' in open(f'{GEN_SOFTWARE_PATH}{tasks_path}').read():
            extra_args += ' --ask-become-pass'
        if self.eval_ver:
            cmd = (f'{get_ansible_playbook_path()} -i '
                   f'{self.sw_vars["ansible_inventory"]} '
                   f'{GEN_SOFTWARE_PATH}{self.my_name}_ansible/run.yml '
                   f'--extra-vars "task_file={GEN_SOFTWARE_PATH}{tasks_path}" '
                   f'--extra-vars "@{GEN_SOFTWARE_PATH}software-vars-eval.yml" '
                   f'{extra_args}')
        else:
            cmd = (f'{get_ansible_playbook_path()} -i '
                   f'{self.sw_vars["ansible_inventory"]} '
                   f'{GEN_SOFTWARE_PATH}{self.my_name}_ansible/run.yml '
                   f'--extra-vars "task_file={GEN_SOFTWARE_PATH}{tasks_path}" '
                   f'--extra-vars "@{GEN_SOFTWARE_PATH}software-vars.yml" '
                   f'{extra_args}')
        run = True
        while run:
            log.info(f'Running Ansible tasks found in \'{tasks_path}\' ...')
            if ('notify: Reboot' in
                    open(f'{GEN_SOFTWARE_PATH}{tasks_path}').read()):
                print(bold('\nThis step requires changed systems to reboot! '
                           '(16 minute timeout)'))
            if '--ask-become-pass' in cmd:
                print('\nClient password required for privilege escalation')
            elif '--vault-password-file' in cmd:
                self._unlock_vault(validate=False)
            resp, err, rc = sub_proc_exec(cmd, shell=True)
            log.debug(f"cmd: {cmd}\nresp: {resp}\nerr: {err}\nrc: {rc}")
            print("")  # line break

            # If .vault file is missing a retry should work
            if rc != 0 and '.vault was not found' in err:
                log.warning("Vault file missing, retrying...")
            elif rc != 0:
                log.warning("Ansible tasks failed!")
                if resp != '':
                    print(f"stdout:\n{ansible_pprint(resp)}\n")
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


def _interactive_anaconda_license_accept(ansible_inventory, ana_path):
    log = logger.getlogger()
    cmd = (f'ansible-inventory --inventory {ansible_inventory} --list')
    resp, err, rc = sub_proc_exec(cmd, shell=True)
    inv = json.loads(resp)
    hostname, hostvars = inv['_meta']['hostvars'].popitem()
    ip = re.search(r'(Anaconda\d)-\d+.\d+.\d+', ana_path, re.IGNORECASE).group(1)
    ip = f'/opt/{ip}/'.lower()
    base_cmd = f'ssh -t {hostvars["ansible_user"]}@{hostname} '
    if "ansible_ssh_private_key_file" in hostvars:
        base_cmd += f'-i {hostvars["ansible_ssh_private_key_file"]} '
    if "ansible_ssh_common_args" in hostvars:
        base_cmd += f'{hostvars["ansible_ssh_common_args"]} '

    cmd = base_cmd + f' ls {ip}'
    resp, err, rc = sub_proc_exec(cmd)

    # If install directory already exists assume license has been accepted
    if rc == 0:
        print(f'Anaconda license already accepted on {hostname}')
    else:
        print(bold('Manual Anaconda license acceptance required on at least '
                   'one client!'))
        rlinput(f'Press Enter to run interactively on {hostname}')
        fn = os.path.basename(ana_path)
        cmd = f'{base_cmd} sudo ~/{fn} -p {ip}'
        rc = sub_proc_display(cmd)
        if rc == 0:
            print('\nLicense accepted. Acceptance script will be run quietly '
                  'on remaining servers.')
        else:
            log.error("Anaconda license acceptance required to continue!")
            sys.exit('Exiting')
    return rc


def _interactive_paie_license_accept(ansible_inventory):
    log = logger.getlogger()

    cmd = (f'ansible-inventory --inventory {ansible_inventory} --list')
    resp, err, rc = sub_proc_exec(cmd, shell=True)
    inv = json.loads(resp)

    accept_cmd = ('sudo /opt/DL/powerai-enterprise/license/bin/'
                  'accept-powerai-enterprise-license.sh ')
    check_cmd = ('/opt/DL/powerai-enterprise/license/bin/'
                 'check-powerai-enterprise-license.sh ')

    print(bold('Acceptance of the PowerAI Enterprise license is required on '
               'all nodes in the cluster.'))
    rlinput(f'Press Enter to run interactively on each hosts')

    for hostname, hostvars in inv['_meta']['hostvars'].items():
        base_cmd = f'ssh -t {hostvars["ansible_user"]}@{hostname} '
        if "ansible_ssh_common_args" in hostvars:
            base_cmd += f'{hostvars["ansible_ssh_common_args"]} '
        if "ansible_ssh_private_key_file" in hostvars:
            base_cmd += f'-i {hostvars["ansible_ssh_private_key_file"]} '

        cmd = base_cmd + check_cmd
        resp, err, rc = sub_proc_exec(cmd)
        if rc == 0:
            print(bold('PowerAI Enterprise license already accepted on '
                       f'{hostname}'))
        else:
            run = True
            while run:
                print(bold('\nRunning PowerAI Enterprise license script on '
                           f'{hostname}'))
                cmd = base_cmd + accept_cmd
                rc = sub_proc_display(cmd)
                if rc == 0:
                    print(f'\nLicense accepted on {hostname}.')
                    run = False
                else:
                    print(f'\nWARNING: License not accepted on {hostname}!')
                    choice, item = get_selection(['Retry', 'Continue', 'Exit'])
                    if choice == "1":
                        pass
                    elif choice == "2":
                        run = False
                    elif choice == "3":
                        log.debug('User chooses to exit.')
                        sys.exit('Exiting')


def _set_spectrum_conductor_install_env(ansible_inventory, package, ana_ver=None):
    mod_name = sys.modules[__name__].__name__
    cmd = (f'ansible-inventory --inventory {ansible_inventory} --list')
    resp, err, rc = sub_proc_exec(cmd, shell=True)
    inv = json.loads(resp)
    hostname, hostvars = inv['_meta']['hostvars'].popitem()

    if package == 'spark':
        envs_path = (f'{GEN_SOFTWARE_PATH}/{mod_name}_ansible/'
                     'envs_spectrum_conductor.yml')
        if not os.path.isfile(envs_path):
            copy2(f'{GEN_SOFTWARE_PATH}/{mod_name}_ansible/'
                  'envs_spectrum_conductor_template.yml',
                  f'{GEN_SOFTWARE_PATH}/{mod_name}_ansible/'
                  'envs_spectrum_conductor.yml')

        replace_regex(envs_path, r'^CLUSTERADMIN:\s*$',
                      f'CLUSTERADMIN: {hostvars["ansible_user"]}\n')
    elif package == 'dli':
        envs_path = (f'{GEN_SOFTWARE_PATH}/{mod_name}_ansible/'
                     'envs_spectrum_conductor_dli.yml')
        if not os.path.isfile(envs_path):
            copy2(f'{GEN_SOFTWARE_PATH}/{mod_name}_ansible/'
                  'envs_spectrum_conductor_dli_template.yml',
                  f'{GEN_SOFTWARE_PATH}/{mod_name}_ansible/'
                  'envs_spectrum_conductor_dli.yml')

        replace_regex(envs_path, r'^CLUSTERADMIN:\s*$',
                      f'CLUSTERADMIN: {hostvars["ansible_user"]}\n')
        replace_regex(envs_path, r'^DLI_CONDA_HOME:\s*$',
                      f'DLI_CONDA_HOME: /opt/{ana_ver}\n')

    env_validated = False
    init = True
    while not env_validated:
        try:
            for key, value in yaml.full_load(open(envs_path)).items():
                if value is None:
                    break
            else:
                env_validated = True
        except IOError:
            print(f'Failed to load Spectrum Conductor {package} configuration')

        if not env_validated:
            print(f'\nSpectrum Conductor {package} configuration variables '
                  'incomplete!')
            input(f'Press enter to edit {package} configuration file')
            click.edit(filename=envs_path)
        elif init and get_yesno(f'Edit Spectrum Conductor {package} '
                                'configuration? '):
            click.edit(filename=envs_path)
        init = False

    user_name = os.getlogin()
    if os.getuid() == 0 and user_name != 'root':
        user_uid = pwd.getpwnam(user_name).pw_uid
        user_gid = grp.getgrnam(user_name).gr_gid
        os.chown(envs_path, user_uid, user_gid)
        os.chmod(envs_path, 0o644)

    print(f'Spectrum Conductor {package} configuration variables successfully '
          'loaded\n')


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
    parser.add_argument('action', choices=['prep', 'install'],
                        help='Action to take: prep or install')

    parser.add_argument('--print', '-p', dest='log_lvl_print',
                        help='print log level', default='info')

    parser.add_argument('--file', '-f', dest='log_lvl_file',
                        help='file log level', default='info')

    args = parser.parse_args()

    logger.create(args.log_lvl_print, args.log_lvl_file)

    soft = software()

    if args.action == 'prep':
        soft.prep()
    elif args.action == 'install':
        soft.install()
