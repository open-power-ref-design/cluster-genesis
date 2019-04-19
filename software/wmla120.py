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
from shutil import copy2, rmtree
import calendar
import time
import yaml
from orderedattrdict.yamlutils import AttrDictYAMLLoader
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
    parse_rpm_filenames, lscpu
from lib.genesis import GEN_SOFTWARE_PATH, get_ansible_playbook_path, \
    get_playbooks_path, get_nginx_root_dir
from nginx_setup import nginx_setup

ENVIRONMENT_VARS = {
    "ANSIBLE_CONFIG": str(get_playbooks_path()) + "/" + "ansible.cfg",  # this probably should be different
    "DEFAULT_GATHER_TIMEOUT": "10",
    "ANSIBLE_GATHER_TIMEOUT": "10"
}


class software(object):
    """ Software installation class. The prep method is used to setup
    repositories, download files to the installer node or perform other
    initialization activities. The install method implements the actual
    installation.
    Args:
        eval_ver (bool): Set to True to install the evaluation version of WMLA
        non_int (bool): Set True to run non-interactively (not yet implemented)
        arch (str): ppc64le or x86_64
        proc_family (str): p8 or p8
        engr_mode (bool): Set true to gather package dependencies
        base_dir (str): Name of the directory to use. This can only be a
            depth of one (no slashes)('/'). This directory name will be
            appended to the root_dir_nginx directory.
    """
    def __init__(self, eval_ver=False, non_int=False, arch='ppc64le',
                 proc_family=None, engr_mode=False, base_dir=None):
        self.log = logger.getlogger()
        self.log_lvl = logger.get_log_level_print()
        self.my_name = sys.modules[__name__].__name__
        self.rhel_ver = '7'
        self.arch = arch
        self.yum_powerup_repo_files = []
        self.eval_ver = eval_ver
        self.non_int = non_int

        if isinstance(proc_family, list):
            self.proc_family = proc_family[0]
        else:
            self.proc_family = proc_family
        if self.arch == 'x86_64' and not proc_family:
            self.proc_family = self.arch

        # add filename to distinguish architecture
        self.base_filename = f'{self.my_name}' if self.arch == 'ppc64le' \
            else f'{self.my_name}_{self.arch}'

        self._load_filelist()
        self.eng_mode = engr_mode
        yaml.add_constructor(YAMLVault.yaml_tag, YAMLVault.from_yaml)
        self.ana_platform_basename = '64' if self.arch == "x86_64" else self.arch

        self.sw_vars_file_name = 'software-vars.yml'
        self.log.info(f"Using architecture: {self.arch}")

        self._load_content()
        self._load_pkglist()

        sw_vars_path = os.path.join(GEN_SOFTWARE_PATH, f'{self.sw_vars_file_name}')
        if os.path.isfile(sw_vars_path):
            try:
                self.sw_vars = yaml.load(open(sw_vars_path))
            except IOError:
                copy2(sw_vars_path, sw_vars_path + '.bak')
                self.log.error(f'Unable to open {sw_vars_path}. \n'
                               f'Backup made to {sw_vars_path}.bak\n'
                               'Recreating software vars file.')
            except yaml.parser.ParserError:
                self.log.error(f'Unable to load {sw_vars_path}.')
                self.sw_vars = {}
            else:
                if not self.sw_vars:
                    self.sw_vars = {}
        else:
            self.log.info('Creating software vars yaml file')
            self.sw_vars = {}
            self.sw_vars['init-time'] = time.ctime()
            self.README()
            input('\nPress enter to continue')

        if not isinstance(self.sw_vars, dict):
            self.sw_vars = {}
            self.sw_vars['init-time'] = time.ctime()

        self.root_dir_nginx = get_nginx_root_dir()
        if not os.path.isdir(f'{self.root_dir_nginx}'):
            os.makedirs(f'{self.root_dir_nginx}')
            cmd = f'sudo chcon -Rv --type=httpd_sys_content_t {self.root_dir_nginx}'
            resp, err, rc = sub_proc_exec(cmd)
            if rc != 0:
                self.log.error('An error occurred while setting access \n'
                               f'permissions for directory {self.root_dir_nginx}.\n'
                               'This may cause http access problems if SELinux '
                               'is running')
                if not get_yesno('Continue ?'):
                    sys.exit('Exit at user request')

        if base_dir is not None:
            # force to single level directory
            base_dir = base_dir.replace('/', '')
            if base_dir:
                self.root_dir = f'{self.root_dir_nginx}/{base_dir}/'
                self.sw_vars['base_dir'] = base_dir
            else:
                if 'base_dir' in self.sw_vars:
                    del self.sw_vars['base_dir']
                self.root_dir = f'{self.root_dir_nginx}/{self.my_name}-{arch}/'
        elif 'base_dir' in self.sw_vars:
            self.root_dir = f"{self.root_dir_nginx}/{self.sw_vars['base_dir']}/"
        else:
            self.root_dir = f'{self.root_dir_nginx}/{self.my_name}-{arch}/'

        # Primarily intended for display purposes:
        self.repo_shortname = self.root_dir[len(self.root_dir_nginx):].strip('/')

        if ('ana_powerup_repo_channels' not in self.sw_vars or not
                isinstance(self.sw_vars['ana_powerup_repo_channels'], list)):
            self.sw_vars['ana_powerup_repo_channels'] = []
        if ('yum_powerup_repo_files' not in self.sw_vars or not
                isinstance(self.sw_vars['yum_powerup_repo_files'], dict)):
            self.sw_vars['yum_powerup_repo_files'] = {}
        if ('content_files' not in self.sw_vars or not
                isinstance(self.sw_vars['content_files'], dict)):
            self.sw_vars['content_files'] = {}

        self.sw_vars['rhel_ver'] = self.rhel_ver
        self.sw_vars['arch'] = self.arch

        if os.path.isdir('/srv/wmla-license') and not os.path.isdir(self.root_dir):
            msg = ('\nThis version of the PowerUp software server utilizes a new '
                   'directory layout.\n'
                   f'No software server content exists under {self.root_dir}\n'
                   'PowerUp can copy or move your existing repositories.')
            print(msg)
            if get_yesno('Would you like to copy or move your existing '
                         'repositories? '):

                import create_base_dir_wmla120
                create_base_dir_wmla120.create_base_dir(self.root_dir_nginx)

        if 'ansible_inventory' not in self.sw_vars:
            self.sw_vars['ansible_inventory'] = None
        if 'ansible_become_pass' not in self.sw_vars:
            self.sw_vars['ansible_become_pass'] = None
        self.vault_pass = None
        self.vault_pass_file = f'{GEN_SOFTWARE_PATH}.vault'

        self.log.debug(f'software variables: {self.sw_vars}')

    def __del__(self):
        if os.path.isfile(self.vault_pass_file):
            os.remove(self.vault_pass_file)

    def README(self):
        kc_link = bold('   https://www.ibm.com/support/knowledgecenter/SSFHA8/ \n\n')
        rtd_link = bold('   https://power-up.readthedocs.io/en/latest/'
                        'Running-paie.html\n\n')
        print(bold('\nWMLA Enterprise software installer module'))
        text = ('\nThis module installs the Watson Machine Learning Accelerated\n'
                'Enterprise software to a cluster of OpenPOWER or x86 nodes.\n'
                'Before beginning installation, be sure that the pre-requisite\n'
                'setup steps have been performed. For guidance, see:\n\n'
                '' + kc_link +
                'For additional help in using the automated installer, see:\n\n'
                '' + rtd_link +
                'WMLA Enterprise installation involves three steps;\n'
                '\n  1 - Preparation. Prepares the installer node software server.\n'
                '       The preparation phase may be run multiple times if needed.\n'
                f'       usage: pup software --prep {self.my_name}\n'
                '\n  2 - Initialization of client nodes\n'
                f'       usage: pup software --init-clients {self.my_name}\n'
                '\n  3 - Installation. Install software on the client nodes\n'
                f'       usage: pup software --install {self.my_name}\n\n'
                'Before beginning, the following files should be extracted from the\n'
                'Watson MLA Enterprise binary file and present on this node;\n'
                f'- ibm-wmla-1.2.0_{self.arch}.bin\n'
                f'- ibm-wmla-license-1.2.0-*.tar.bz2\n'
                f'- conductor2.3.0.0_{self.arch}.bin\n'
                '- conductor_entitlement.dat\n'
                f'- dli-1.2.2.0_{self.arch}.bin\n'
                '- dli_entitlement.dat\n\n'
                f'For installation status: pup software --status {self.my_name}\n'
                f'To redisplay this README: pup software --README {self.my_name}\n\n'
                'Note: The \'pup\' cli supports tab autocompletion.\n\n')
        print(text)

    def _is_nginx_running(self):
        cmd = 'nginx -v'
        ret = False
        try:
            resp, err, rc = sub_proc_exec(cmd)
            if 'nginx version:' in err:
                ret = True
        except FileNotFoundError:
            pass

        return ret

    def status(self, which='all'):
        self._update_software_vars()
        self.prep_init()
        self.status_prep(which)
        self.prep_post()

    def status_prep(self, which='all'):
        self.state = {}

        def yum_repo_status(item):
            repo_id = item.repo_id.format(arch=self.arch)
            search_dir = f'{self.root_dir}repos/{repo_id}/**/repodata'
            repodata = glob.glob(search_dir, recursive=True)
            sw_vars_data = (f'{repo_id}-powerup.repo' in
                            self.sw_vars['yum_powerup_repo_files'])
            if repodata and sw_vars_data:
                self.state[item.desc] = 'Setup'
            else:
                self.state[item.desc] = '-'

        def content_status(item):
            ver_mis = False
            item_dir = item.path
            if self.eval_ver and hasattr(item, 'fileglob_eval'):
                fileglob = item.fileglob_eval.format(arch=self.arch)
            else:
                fileglob = item.fileglob.format(arch=self.arch)
            exists = glob.glob(f'{self.root_dir}{item_dir}/**/{fileglob}', recursive=True)

            sw_vars_data = item_dir in self.sw_vars['content_files']

            if exists and sw_vars_data:
                name = item.name
                if not item.license_for:
                    if exists[0] in self.sw_vars['content_files'][item_dir]:
                        self.state[name] = ('Present')
                    else:
                        ver_mis = True
                        self.state[name] = (Color.yellow +
                                            'Present but not at release level' +
                                            Color.endc)
                else:
                    self.state[item.name] = ('Present')
            else:
                self.state[item.name] = '-'
            return ver_mis

        def conda_repo_status(item):
            repo_id = item.repo_id
            repo_name = item.repo_name
            if 'Main' in repo_name:
                name = 'main'
            elif 'Free' in repo_name:
                name = 'free'
            else:
                name = ''
            dirglob_lin = os.path.join(f'{self.root_dir}', 'repos', f'{repo_id}',
                                       '**', f'{name}', f'linux-{self.arch}', '')
            path_lin = glob.glob(dirglob_lin, recursive=True)

            dirglob_na = os.path.join(f'{self.root_dir}', 'repos', f'{repo_id}',
                                      '**', f'{name}', 'noarch', '')
            path_na = glob.glob(dirglob_na, recursive=True)

            in_channel_list = False
            for chan in self.sw_vars['ana_powerup_repo_channels']:
                if f'/{name}/' in chan:
                    in_channel_list = True
                    break

            if path_lin and path_na and in_channel_list:
                self.state[item.desc] = 'Setup'
            else:
                self.state[item.desc] = '-'

        ver_mis = False
        for _item in self.content:
            item = self.content[_item]
            if item.type == 'file':
                ret = content_status(item)
                ver_mis = ver_mis or ret
                continue

            # yum repos status
            if item.type == 'yum':
                yum_repo_status(item)
                continue

            if item.type == 'conda':
                conda_repo_status(item)

            if item.type == 'simple':
                if os.path.exists(f'{self.root_dir}repos/{item.repo_id}/simple/') and \
                        len(os.listdir(f'{self.root_dir}repos/{item.repo_id}/simple/')) >= 1:
                    self.state[item.desc] = 'Setup'
                else:
                    self.state[item.desc] = '-'

            # Nginx web server status
            if item == 'Nginx Web Server' and self._is_nginx_running():
                temp_dir = 'nginx-test-dir-123'
                abs_temp_dir = os.path.join(self.root_dir, temp_dir)
                test_file = 'test-file.abc'
                test_path = os.path.join(abs_temp_dir, test_file)
                try:
                    rmtree(abs_temp_dir, ignore_errors=True)
                    os.mkdir(abs_temp_dir)
                    # os.mknod(test_file)
                    with open(test_path, 'x') as f:
                        _ = f  # tox mug
                        pass
                except:
                    self.log.error('Failed trying to create temporary file '
                                   f'{test_path}. Check access privileges')
                    sys.exit('Exiting. Unable to continue.')
                else:
                    self.state[item.desc] = '-'
                continue

        # Firewall status
        item = 'Firewall'
        if item == 'Firewall':
            cmd = 'firewall-cmd --list-all'
            resp, _, _ = sub_proc_exec(cmd)
            if re.search(r'services:\s+.+http', resp):
                self.state[item] = "Running and configured for http"

        # Nginx web server status
        item = 'Nginx Web Server'
        if item == 'Nginx Web Server':
            temp_dir = 'nginx-test-dir-123'
            abs_temp_dir = os.path.join(self.root_dir_nginx, temp_dir)
            test_file = 'test-file.abc'
            test_path = os.path.join(abs_temp_dir, test_file)
            try:
                rmtree(abs_temp_dir, ignore_errors=True)
                os.mkdir(abs_temp_dir)
                # os.mknod(test_file)
                with open(test_path, 'x') as f:
                    f.close
            except:
                self.log.error('Failed trying to create temporary file '
                               f'{test_path}. Check access privileges')
                sys.exit('Exiting. Unable to continue.')
            else:
                cmd = f'curl -I http://127.0.0.1/{temp_dir}/{test_file}'
                resp, _, _ = sub_proc_exec(cmd)
                if 'HTTP/1.1 200 OK' in resp:
                    self.state[item] = 'Nginx is configured and running'
                else:
                    print()
                    msg = ('Nginx is unable to access content under '
                           f'{self.root_dir}.\n This can be due to SElinux '
                           'configuration, access priveleges or other reasons.')
                    self.log.error(msg)
                    self.state[item] = '-'
            finally:
                rmtree(abs_temp_dir, ignore_errors=True)
            try:
                rmtree(abs_temp_dir, ignore_errors=True)
            except:
                pass

        exists = True
        if which == 'all':
            heading1(f'Preparation Summary for {self.repo_shortname}')
            for item in self.state:
                status = self.state[item]
                it = (item + '                              ')[:39]
                print(f'  {it:<40} : ' + status)
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

    def _is_firewall_running(self, eval_ver=False, non_int=False):
        cmd = 'systemctl status firewalld.service'
        resp, _, _ = sub_proc_exec(cmd)
        if 'Active: active (running)' in resp.splitlines()[2]:
            self.log.debug('Firewall is running')
            return True
        return False

    def _setup_firewall(self, eval_ver=False, non_int=False):
        if self._is_firewall_running():
            heading1('Configuring firewall to enable http')
            fw_err = 0
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
        else:
            self.log.debug('Firewall is not running')
            self.log.info(bold('The firewall is not enabled.\n'))
            print('The PowerUp software installer utilizes Nginx web server.')
            print('Nginx will run without the Firewall enabled, but it is \n'
                  'advisable to utilize a firewall when running a web server.')
#            if not get_yesno('\nContinue with installation? ', default='y'):
#                self.log.info('Exiting at user request')
#                sys.exit()

    def _setup_nginx_server(self, eval_ver=False, non_int=False):
        # nginx setup
        heading1('Set up Nginx')

        # if not self._is_nginx_running():
        nginx_setup(root_dir=self.root_dir_nginx, repo_id='nginx')

        exists = self.status_prep(which='Nginx Web Server')
        if not exists:
            self.log.error('Nginx is unable to access content.')
            sys.exit()

        self.status_prep(which='Nginx Web Server')
        if self.state['Nginx Web Server'] == '-':
            self.log.info('nginx web server is not running')
        else:
            self.log.info(self.state['Nginx Web Server'])

    def create_cuda_drv_repo(self, eval_ver=False, non_int=False):
        # Setup repository for cuda packages. The Cuda public repo is enabled
        # and the package list can be downloaded from there or alternately the
        # cuda packages repo can be created from a local directory or an
        # existing repository on another node.
        name = 'cuda_driver'
        _repo = self.content[name]
        repo_id = _repo.repo_id
        repo_name = _repo.repo_name
        baseurl = _repo.source.baseurl.format(arch=self.arch)
        gpgkey = _repo.gpgkey.format(baseurl=baseurl)
        heading1(f'Set up {repo_name}\n')
        # list to str
        pkg_list = ' '.join(self.pkgs['cuda_drivers'])

        if f'{repo_id}_alt_url' in self.sw_vars:
            alt_url = self.sw_vars[f'{repo_id}_alt_url']
        else:
            alt_url = None

        # exists = self.status_prep(which='CUDA Driver Repository')
        exists = self.status_prep(which=_repo.desc)
        if exists:
            self.log.info(f'The {repo_name} exists already'
                          ' in the POWER-Up server')
            pr_str = (f'\nDo you want to resync the {repo_name}'
                      ' at this time\n')
        else:
            pr_str = (f'\nDo you want to create the {repo_name}'
                      ' at this time\n')

        ch = 'S'
        if get_yesno(prompt=pr_str, yesno='Y/n'):
            if platform.machine() == self.arch:
                ch, item = get_selection('Sync required packages from public repo.\n'
                                         'Create from Nvidia "local" driver RPM.\n'
                                         'Sync from an alternate Repository.\n'
                                         'Skip',
                                         'P\nrpm\nA\nS',
                                         'Repository source? ')
            else:
                ch, item = get_selection('Sync required packages from public repo.\n'
                                         'Create from Nvidia "local" driver RPM.\n'
                                         'Sync from an alternate Repository.\n'
                                         'Skip',
                                         'P\nrpm\nA\nS',
                                         'Repository source? ')

        if ch == 'P':
            # Enable the public repo
            repo_cuda = PowerupRepo(repo_id, repo_name, self.root_dir, arch=self.arch)
            dot_repo_content = repo_cuda.get_yum_dotrepo_content(url=baseurl, gpgkey=gpgkey)
            repo_cuda.write_yum_dot_repo_file(dot_repo_content)

            repo = PowerupRepo(repo_id, repo_name, self.root_dir, arch=self.arch)
            repo_dir = repo.get_repo_dir()
            self._add_dependent_packages(repo_dir, pkg_list, also_get_newer=False)
            repo.create_meta()

        elif ch == 'rpm':
            # prompts user for the location of the rpm file to be loaded into
            # the PowerUp server.  The file is copied to /srv/{repo_id}. The
            # contents of the rpm file are then extracted under /srv/repos/
            # Meta data is created. yum.repo content is generated and added to
            # the software-vars.yml file
            repo = PowerupRepoFromRpm(repo_id, repo_name, self.root_dir, arch=self.arch)

            if f'{repo_id}_src_rpm_dir' in self.sw_vars:
                src_path = self.sw_vars[f'{repo_id}_src_rpm_dir']
            else:
                # default is to search recursively under all /home/
                # directories
                src_path = '/home/**/cuda-repo-rhel7-10-1-local-*.rpm'
            rpm_path = repo.get_rpm_path(src_path)
            if rpm_path:
                self.sw_vars[f'{repo_id}_src_rpm_dir'] = rpm_path
                repo_dir = repo.extract_rpm(rpm_path)
                repo.create_meta()
                # content = repo.get_yum_dotrepo_content(
                #     repo_dir=repo_dir, gpgcheck=0, client=True)
            else:
                self.log.info('No path chosen. Skipping create custom '
                              'repository.')

        elif ch == 'A':
            if f'{repo_id}_alt_url' in self.sw_vars:
                alt_url = self.sw_vars[f'{repo_id}_alt_url']
            else:
                alt_url = None

            repo = PowerupYumRepoFromRepo(repo_id, repo_name, self.root_dir, arch=self.arch)
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

                self.log.info('Repository setup complete')

        else:
            print(f'{repo_name} repository not updated')
        if ch != 'S':
            repo_dir += '/cuda-drivers-[4-9][0-9][0-9].[0-9]*-[0-9]*'
            files = glob.glob(repo_dir, recursive=True)
            if files:
                self.sw_vars['cuda-drivers'] = re.search(r'cuda-drivers-\d+\.\d+-\d+',
                                                         ' '.join(files)).group(0)
            else:
                self.log.error('No cuda toolkit file found in cuda repository')
        self.prep_post()

    def create_ibmai_repo(self, eval_ver=False, non_int=False):
        # Setup IBM AI conda repo
        name = 'ibmai'
        _repo = self.content[name]
        repo_id = _repo.repo_id
        repo_name = _repo.repo_name
        baseurl = _repo.source.baseurl.format(ana_platform_basename=self.
                                              ana_platform_basename)
        # repo_id = 'ibmai'
        # repo_name = 'IBM AI Repository'
        # baseurl = ('https://public.dhe.ibm.com/ibmdl/export/pub/software/server/'
        #           f'ibm-ai/conda/linux-{self.ana_platform_basename}/')
        heading1(f'Set up {repo_name}\n')

        vars_key = get_name_dir(repo_name)  # format the name
        if f'{vars_key}-alt-url' in self.sw_vars:
            alt_url = self.sw_vars[f'{vars_key}-alt-url']
        else:
            alt_url = None

        exists = self.status_prep(which=_repo.desc)
        if exists:
            self.log.info(f'The {repo_name} exists already'
                          ' in the POWER-Up server\n')

        repo = PowerupAnaRepoFromRepo(repo_id, repo_name, self.root_dir,
                                      arch=self.arch)
        ch = repo.get_action(exists)
        if ch in 'Y':
            # if not exists or ch == 'F':
            url = repo.get_repo_url(baseurl, alt_url, contains=['ibmai', 'linux',
                                    f'{self.arch}'], excludes=['noarch', 'main'],
                                    filelist=['caffe-1.0*'])
            if url:
                if not url == baseurl:
                    if '@na.' in url:
                        cred_end = url.find('@na.')
                        _url = url[cred_end:]
                    else:
                        _url = url
                    self.sw_vars[f'{vars_key}-alt-url'] = _url

                # accept_list is used for linux_{self.arch}, reject_list for noarch
                if 'accept_list' in self.pkgs[f'ibm_ai_conda_linux_{self.arch}']:
                    al = self.pkgs[f'ibm_ai_conda_linux_{self.arch}']['accept_list']
                else:
                    al = None

                if 'reject_list' in self.pkgs[f'ibm_ai_conda_linux_{self.arch}']:
                    rl = self.pkgs[f'ibm_ai_conda_linux_{self.arch}']['reject_list']
                else:
                    rl = None

                dest_dir = repo.sync_ana(url, acclist=al, rejlist=rl)
                if dest_dir is None:
                    print(f'{repo_name} repository not updated')
                    return False

                dest_dir = dest_dir[4 + dest_dir.find('/srv'):6 +
                                    dest_dir.find(f'{repo_id}')]
                # form .condarc channel entry. Note that conda adds
                # the corresponding 'noarch' channel automatically.
                channel = f'  - http://{{{{ host_ip.stdout }}}}{dest_dir}'
                if channel not in self.sw_vars['ana_powerup_repo_channels']:
                    self.sw_vars['ana_powerup_repo_channels'].append(channel)

                if 'accept_list' in self.pkgs['ibm_ai_conda_noarch']:
                    al = self.pkgs['ibm_ai_conda_noarch']['accept_list']
                else:
                    al = None

                if 'reject_list' in self.pkgs['ibm_ai_conda_noarch']:
                    rl = self.pkgs['ibm_ai_conda_noarch']['reject_list']
                else:
                    rl = None
                noarch_url = os.path.split(url.rstrip('/'))[0] + '/noarch/'

                repo.sync_ana(noarch_url, acclist=al, rejlist=rl)
            self.prep_post()

    # Get WMLA Enterprise license file
    def create_wmla_license(self, eval_ver=False, non_int=False):
        name = 'wmla_license'
        heading1(f'Set up {name.title()} \n')
        item = self.content[name]
        lic_src = item.fileglob
        lic_dir = item.path
        exists = self.status_prep(item.name)
        lic_url = ''

        if f'{name}_alt_url' in self.sw_vars:
            alt_url = self.sw_vars[f'{name}_alt_url']
        else:
            alt_url = 'http://<host>/'

        if exists:
            self.log.info('WMLA Enterprise license exists already in the POWER-Up '
                          'server')

        if not exists or get_yesno(f'Copy a new {name.title()} file '):
            src_path, dest_path, state = setup_source_file(name, lic_src, lic_dir,
                                                           self.root_dir, lic_url,
                                                           alt_url=alt_url)
            if src_path and 'http' in src_path:
                self.sw_vars[f'{name}_alt_url'] = os.path.dirname(src_path) + '/'
            if dest_path:
                self.sw_vars['content_files'][get_name_dir(name)] = dest_path
            self.prep_post()

        # Get Spectrum Conductor
    def create_spectrum_conductor(self, eval_ver=False, non_int=False):
        name = 'spectrum_conductor'
        heading1(f'Set up {name.title()} \n')
        item = self.content[name]
        spc_src = item.fileglob.format(arch=self.arch)
        spc_dir = item.path
        entitlement = self.content[item.license_file].fileglob
        exists = self.status_prep(item.name)
        spc_url = ''

        if f'{name}_alt_url' in self.sw_vars:
            alt_url = self.sw_vars[f'{name}_alt_url']
        else:
            alt_url = 'http://<host>/'

        if exists:
            self.log.info('Spectrum conductor content exists already in the '
                          'POWER-Up server')

        if not exists or get_yesno(f'Copy a new {name.title()} file '):
            src_path, dest_path, state = setup_source_file(name, spc_src, spc_dir,
                                                           self.root_dir,
                                                           spc_url,
                                                           alt_url=alt_url,
                                                           src2=entitlement)
            if src_path and 'http' in src_path:
                self.sw_vars[f'{name}_alt_url'] = os.path.dirname(src_path) + '/'
            if dest_path:
                self.sw_vars['content_files'][get_name_dir(name)] = dest_path
            if state:
                self.sw_vars['content_files'][get_name_dir(name) + '-entitlement'] = (
                    os.path.dirname(dest_path) + '/' + entitlement)
            self.prep_post()

    def create_spectrum_dli(self, eval_ver=False, non_int=False):
        # Get Spectrum DLI
        name = 'spectrum_dli'
        heading1(f'Set up {name.title()} \n')
        # spdli_src = self.globs[name]
        # entitlement = self.globs[name + ' entitlement']
        item = self.content[name]
        spdli_src = item.fileglob.format(arch=self.arch)
        spdli_dir = item.path
        entitlement = self.content[item.license_file].fileglob
        exists = self.status_prep(item.name)
        spdli_url = ''

        if f'{name}_alt_url' in self.sw_vars:
            alt_url = self.sw_vars[f'{name}_alt_url']
        else:
            alt_url = 'http://<host>/'

        if exists:
            self.log.info('Spectrum DLI content exists already in the POWER-Up server')

        if not exists or get_yesno(f'Copy a new {name.title()} file '):
            src_path, dest_path, state = setup_source_file(name, spdli_src, spdli_dir,
                                                           self.root_dir, spdli_url,
                                                           alt_url=alt_url,
                                                           src2=entitlement)
            if src_path and 'http' in src_path:
                self.sw_vars[f'{name}_alt_url'] = os.path.dirname(src_path) + '/'
            if dest_path:
                self.sw_vars['content_files'][get_name_dir(name)] = dest_path
            if state:
                self.sw_vars['content_files'][get_name_dir(name) + '-entitlement'] = (
                    os.path.dirname(dest_path) + '/' + entitlement)
            self.prep_post()

    def create_dependency_repo(self, eval_ver=False, non_int=False):
        # Setup repository for redhat dependent packages. This is intended to deal
        # specifically with redhat packages requiring red hat subscription for access,
        # however dependent packages can come from any YUM repository enabled on the
        # POWER-Up Installer node. Alternately the dependent packages repo can be
        # Created from a local directory or an existing repository on another node.
        # repo_id = 'dependencies'
        # repo_name = 'Dependencies'
        # baseurl = ''

        name = 'dependent_packages'
        _repo = self.content[name]
        repo_id = _repo.repo_id
        repo_name = _repo.repo_name
        baseurl = ''

        heading1(f'Set up {repo_name} repository')

        exists = self.status_prep(which=_repo.desc)
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
            _lscpu = lscpu()
            installer_proc_model = None
            try:
                if 'POWER8' in _lscpu['Model name'].upper():
                    installer_proc_model = 'p8'
                elif 'POWER9' in _lscpu['Model name'].upper():
                    installer_proc_model = 'p9'
                elif 'x86_64' in _lscpu['Architecture']:
                    installer_proc_model = 'x86_64'
            except KeyError:
                pass

            if self.arch == 'ppc64le' and not self.proc_family:
                self.proc_family, item = get_selection('Power 8\nPower 9', 'p8\np9',
                                                       'Processor family? ')

            if self.proc_family == 'p9':
                dep_list = ' '.join(self.pkgs['yum_pkgs_p9'])
            elif self.proc_family == 'p8':
                dep_list = ' '.join(self.pkgs['yum_pkgs_p8'])
            elif self.arch == 'x86_64':
                dep_list = ' '.join(self.pkgs['yum_pkgs_x86_64'])

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

            if (platform.machine() == self.arch and
                    self.proc_family == installer_proc_model):
                ch, item = get_selection('Sync required dependent packages from '
                                         'Enabled YUM repos\n'
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
                repo = PowerupRepo(repo_id, repo_name, self.root_dir,
                                   proc_family=self.proc_family)
                repo_dir = repo.get_repo_dir()
                os.makedirs(repo_dir, exist_ok=True)
                self._add_dependent_packages(repo_dir, dep_list, also_get_newer=True)
                self._add_dependent_packages(repo_dir, more, also_get_newer=True)
                repo.create_meta()
                # content = repo.get_yum_dotrepo_content(gpgcheck=0, local=True)
                # repo.write_yum_dot_repo_file(content)

            elif ch == 'D':
                repo = PowerupRepoFromDir(repo_id, repo_name, self.root_dir,
                                          arch=self.arch, proc_family=self.proc_family)

                if f'{repo_id}_src_dir' in self.sw_vars:
                    src_dir = self.sw_vars[f'{repo_id}_src_dir']
                else:
                    src_dir = None
                src_dir, dest_dir = repo.copy_dirs(src_dir)
                if src_dir:
                    self.sw_vars[f'{repo_id}_src_dir'] = src_dir
                    repo.create_meta()
                    # content = repo.get_yum_dotrepo_content(gpgcheck=0, local=True)
                    # repo.write_yum_dot_repo_file(content)

            elif ch == 'R':
                if f'{repo_id}_alt_url' in self.sw_vars:
                    alt_url = self.sw_vars[f'{repo_id}_alt_url']
                else:
                    alt_url = None
                repo = PowerupYumRepoFromRepo(repo_id, repo_name, self.root_dir,
                                              arch=self.arch,
                                              proc_family=self.proc_family)

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

                    # Setup local access to the new repo copy
                    # if platform.machine() == self.arch:
                    #    content = repo.get_yum_dotrepo_content(gpgcheck=0, local=True)
                    #    repo.write_yum_dot_repo_file(content)
                    # Prep setup of POWER-Up client access to the repo copy
                    self.log.info('Repository setup complete')
            else:
                print(f'{repo_name} repository not updated')

            if ch in ('R', 'E', 'D'):
                self.prep_post()

    def create_conda_content_repo(self, eval_ver=False, non_int=False):
        # Get Anaconda
        ana_name = 'anaconda'
        item = self.content[ana_name]
        ana_src = item.fileglob.format(arch=self.arch)
        ana_url = item.source.url
        ana_dir = item.path
        if f'{ana_name}_alt_url' in self.sw_vars:
            alt_url = self.sw_vars[f'{ana_name}_alt_url']
        else:
            alt_url = 'http://<host>/'
        exists = self.status_prep(which=item.name)

        heading1('Set up Anaconda\n')

        if exists:
            self.log.info(f'The {ana_name} exists already '
                          'in the POWER-Up server.')

        if not exists or get_yesno(f'Recopy {ana_name} '):

            src_path, dest_path, state = setup_source_file(ana_name, ana_src,
                                                           ana_dir, self.root_dir,
                                                           ana_url, alt_url=alt_url)
            if dest_path:
                self.sw_vars['content_files'][get_name_dir(ana_name)] = dest_path
            if src_path and 'http' in src_path:
                self.sw_vars[f'{ana_name}_alt_url'] = os.path.dirname(src_path) + '/'
            self.prep_post()

    def create_conda_free_repo(self, eval_ver=False, non_int=False):
        # Setup Anaconda Free Repo.  (not a YUM repo)
        name = 'anaconda_free'
        _repo = self.content[name]
        repo_id = _repo.repo_id
        repo_name = _repo.repo_name
        baseurl = _repo.source.baseurl.format(ana_platform_basename=self.
                                              ana_platform_basename)
        heading1(f'Set up {repo_name}\n')

        vars_key = get_name_dir(repo_name)  # format the name
        if f'{vars_key}-alt-url' in self.sw_vars:
            alt_url = self.sw_vars[f'{vars_key}-alt-url']
        else:
            alt_url = None

        exists = self.status_prep(which=_repo.desc)
        if exists:
            self.log.info('The Anaconda Repository exists already'
                          ' in the POWER-Up server\n')

        repo = PowerupAnaRepoFromRepo(repo_id, repo_name, self.root_dir,
                                      arch=self.arch)
        ch = repo.get_action(exists)
        if ch in 'Y':
            # if not exists or ch == 'F':
            url = repo.get_repo_url(baseurl, alt_url, contains=['free', 'linux',
                                    f'{self.arch}'], excludes=['noarch', 'main'],
                                    filelist=['cython-*'])
            if url:
                if not url == baseurl:
                    self.sw_vars[f'{vars_key}-alt-url'] = url

                # accept_list and rej_list are mutually exclusive.
                # accept_list takes priority
                al = self.pkgs[f'anaconda_free_linux_{self.arch}']['accept_list']
                rl = self.pkgs[f'anaconda_free_linux_{self.arch}']['reject_list']

                dest_dir = repo.sync_ana(url, acclist=al, rejlist=rl)
                dest_dir = dest_dir[4 + dest_dir.find('/srv'):5 + dest_dir.find('free')]
                # form .condarc channel entry. Note that conda adds
                # the corresponding 'noarch' channel automatically.
                channel = f'  - http://{{{{ host_ip.stdout }}}}{dest_dir}'
                if channel not in self.sw_vars['ana_powerup_repo_channels']:
                    self.sw_vars['ana_powerup_repo_channels'].append(channel)
                noarch_url = os.path.split(url.rstrip('/'))[0] + '/noarch/'

                al = self.pkgs['anaconda_free_noarch']['accept_list']
                rl = self.pkgs['anaconda_free_noarch']['reject_list']
                repo.sync_ana(noarch_url, acclist=al, rejlist=rl)
            self.prep_post()

    def create_conda_main_repo(self, eval_ver=False, non_int=False):
        # Setup Anaconda Main Repo.  (not a YUM repo)
        name = 'anaconda_main'
        _repo = self.content[name]
        repo_id = _repo.repo_id
        repo_name = _repo.repo_name
        baseurl = _repo.source.baseurl.format(ana_platform_basename=self.
                                              ana_platform_basename)

        heading1(f'Set up {repo_name}\n')

        vars_key = get_name_dir(repo_name)  # format the name
        if f'{vars_key}-alt-url' in self.sw_vars:
            alt_url = self.sw_vars[f'{vars_key}-alt-url']
        else:
            alt_url = None

        exists = self.status_prep(which=_repo.desc)
        if exists:
            self.log.info('The Anaconda Repository exists already'
                          ' in the POWER-Up server\n')

        repo = PowerupAnaRepoFromRepo(repo_id, repo_name, self.root_dir, arch=self.arch)

        ch = repo.get_action(exists)
        if ch in 'Y':
            url = repo.get_repo_url(baseurl, alt_url, contains=['main', 'linux',
                                    f'{self.arch}'], excludes=['noarch', 'free'],
                                    filelist=['bzip2-*'])
            if url:
                if not url == baseurl:
                    self.sw_vars[f'{vars_key}-alt-url'] = url
                # accept_list is used for main, reject_list for noarch
                al = self.pkgs[f'anaconda_main_linux_{self.arch}']['accept_list']
                rl = self.pkgs[f'anaconda_main_linux_{self.arch}']['reject_list']

                dest_dir = repo.sync_ana(url, acclist=al, rejlist=rl)
                dest_dir = dest_dir[4 + dest_dir.find('/srv'):5 + dest_dir.find('main')]
                # form .condarc channel entry. Note that conda adds
                # the corresponding 'noarch' channel automatically.
                channel = f'  - http://{{{{ host_ip.stdout }}}}{dest_dir}'
                if channel not in self.sw_vars['ana_powerup_repo_channels']:
                    self.sw_vars['ana_powerup_repo_channels'].insert(0, channel)
                noarch_url = os.path.split(url.rstrip('/'))[0] + '/noarch/'

                al = self.pkgs['anaconda_main_noarch']['accept_list']
                rl = self.pkgs['anaconda_main_noarch']['reject_list']
                repo.sync_ana(noarch_url, acclist=al, rejlist=rl)
            self.prep_post()

    def create_pypi_repo(self, eval_ver=False, non_int=False):
        # Setup Python package repository. (pypi)
        _repo = self.content['pypi']
        repo_id = _repo.repo_id
        repo_name = _repo.repo_name
        baseurl = _repo.source.baseurl

        heading1(f'Set up {repo_name} repository\n')
        if f'{repo_id}_alt_url' in self.sw_vars:
            alt_url = self.sw_vars[f'{repo_id}_alt_url']
        else:
            alt_url = None

        exists = self.status_prep(which=_repo.desc)
        if exists:
            self.log.info('The Python Package Repository exists already'
                          ' in the POWER-Up server')

        repo = PowerupPypiRepoFromRepo(repo_id, repo_name, self.root_dir,
                                       arch=self.arch)
        ch = repo.get_action(exists, exists_prompt_yn=True)

        pkg_list = ' '.join(self.pkgs['python_pkgs'])
        if ch == 'Y':
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
            self.prep_post()

    def create_epel_repo(self, eval_ver=False, non_int=False):
        # Setup EPEL Repo
        name = 'epel'
        _repo = self.content[name]
        repo_id = _repo.repo_id.format(arch=self.arch)
        repo_name = _repo.repo_name.format(arch=self.arch)
        baseurl = ''
        heading1(f'Set up {repo_name} repository')
        epel_list = ' '.join(self.pkgs['epel_pkgs'])

        file_more = GEN_SOFTWARE_PATH + 'epel-packages.list'
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

        exists = self.status_prep(which=_repo.desc)
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
            ch, item = get_selection(f'Sync required {repo_id} packages from '
                                     'Enabled YUM repo\n'
                                     'Create from package files in a local Directory\n'
                                     'Sync from an alternate Repository\n'
                                     'Skip',
                                     'E\nD\nR\nS',
                                     'Repository source? ')

            if ch == 'E':
                repo = PowerupRepo(repo_id, repo_name, self.root_dir)
                repo_dir = repo.get_repo_dir()
                self._add_dependent_packages(repo_dir, epel_list, also_get_newer=True)
                self._add_dependent_packages(repo_dir, more, also_get_newer=True)
                repo.create_meta()
                # content = repo.get_yum_dotrepo_content(gpgcheck=0, local=True)
                # repo.write_yum_dot_repo_file(content)

            elif ch == 'D':
                repo = PowerupRepoFromDir(repo_id, repo_name, self.root_dir)

                if f'{repo_id}_src_dir' in self.sw_vars:
                    src_dir = self.sw_vars[f'{repo_id}_src_dir']
                else:
                    src_dir = None
                src_dir, dest_dir = repo.copy_dirs(src_dir)
                if src_dir:
                    self.sw_vars[f'{repo_id}_src_dir'] = src_dir
                    repo.create_meta()
                    # content = repo.get_yum_dotrepo_content(gpgcheck=0, local=True)
                    # repo.write_yum_dot_repo_file(content)

            elif ch == 'R':
                if f'{repo_id}_alt_url' in self.sw_vars:
                    alt_url = self.sw_vars[f'{repo_id}_alt_url']
                else:
                    alt_url = None

                repo = PowerupYumRepoFromRepo(repo_id, repo_name, self.root_dir,
                                              arch=self.arch)
                url = repo.get_repo_url(baseurl, alt_url, contains=[repo_id],
                                        filelist=['openblas-*'])
                if url:
                    if not url == baseurl:
                        self.sw_vars[f'{repo_id}_alt_url'] = url
                    # Set up access to the repo
                    content = repo.get_yum_dotrepo_content(url, gpgcheck=0)
                    repo.write_yum_dot_repo_file(content)

                    repo.sync()
                    repo.create_meta()

                    # Setup local access to the new repo copy in /srv/repo/
                    # if platform.machine() == self.arch:
                    #    content = repo.get_yum_dotrepo_content(gpgcheck=0, local=True)
                    #    repo.write_yum_dot_repo_file(content)
                    # Prep setup of POWER-Up client access to the repo copy
                    self.log.info('Repository setup complete')
            else:
                print(f'{repo_name} repository not updated')

            if ch in ('R', 'E', 'D'):
                self.prep_post()

    def create_custom_repo(self, eval_ver=False, non_int=False):
        # Create custom repositories
        if hasattr(self, 'eng_mode'):
            if self.eng_mode:  # == 'custom-repo':
                heading1('Create custom repositories')
                if get_yesno('Would you like to create a custom repository '):
                    repo_id = input('Enter a repo id (yum short name): ')
                    repo_name = input('Enter a repo name (Descriptive name): ')

                    ch, _ = get_selection('Create from files in a directory\n'
                                          'Create from an RPM file\n'
                                          'Create from an existing repository',
                                          'dir\nrpm\nrepo',
                                          'Repository source? ', allow_none=True)
                    if ch != 'N':
                        if ch == 'rpm':
                            # prompts user for the location of the rpm file to be loaded
                            # into the PowerUp server. The file is copied to
                            # {self.root_dir}{repo_id}. The contents of the rpm file
                            # are then extracted under {self.root_dir}repos/
                            # Meta data is created. yum.repo content is generated and
                            # added to the software-vars.yml file
                            repo = PowerupRepoFromRpm(repo_id, repo_name, arch=self.arch)

                            if f'{repo_id}_src_rpm_dir' in self.sw_vars:
                                src_path = self.sw_vars[f'{repo_id}_src_rpm_dir']
                            else:
                                # default is to search recursively under all /home/
                                # directories
                                src_path = '/home/**/*.rpm'
                            rpm_path = repo.get_rpm_path(src_path)
                            if rpm_path:
                                self.sw_vars[f'{repo_id}_src_rpm_dir'] = rpm_path
                                src_path = repo.copy_rpm(rpm_path)
                                repodata_dir = repo.extract_rpm(src_path)
    #                            if repodata_dir:
    #                                content = repo.get_yum_dotrepo_content(
    #                                    repo_dir=repodata_dir, gpgcheck=0)
    #                            else:
    #                                print('Failed extracting rpm content')
    #                                content = repo.get_yum_dotrepo_content(gpgcheck=0,
    #                                                                       local=True)
    #                            repo.write_yum_dot_repo_file(content)
                                repo.create_meta()
                                content = repo.get_yum_dotrepo_content(
                                    repo_dir=repodata_dir, gpgcheck=0, client=True)
                                filename = repo_id + '-powerup.repo'
                                self.sw_vars['yum_powerup_repo_files'][filename] = content
                            else:
                                self.log.info('No path chosen. Skipping create custom '
                                              'repository.')

                        elif ch == 'dir':
                            repo = PowerupRepoFromDir(repo_id, repo_name, arch=self.arch)

                            if f'{repo_id}_src_dir' in self.sw_vars:
                                src_dir = self.sw_vars[f'{repo_id}_src_dir']
                            else:
                                src_dir = None
                            src_dir, dest_dir = repo.copy_dirs(src_dir)
                            if src_dir:
                                self.sw_vars[f'{repo_id}_src_dir'] = src_dir
                                repo.create_meta()
                                content = repo.get_yum_dotrepo_content(gpgcheck=0,
                                                                       client=True)
                                filename = repo_id + '-powerup.repo'
                                self.sw_vars['yum_powerup_repo_files'][filename] = content
                        elif ch == 'repo':
                            baseurl = 'http://'

                            repo = PowerupYumRepoFromRepo(repo_id, repo_name, arch=self.arch)

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

                            # Setup local access to the new repo copy in {self.root_dir}repo/
                            # content = repo.get_yum_dotrepo_content(gpgcheck=0, local=True)
                            # repo.write_yum_dot_repo_file(content)
                            # Prep setup of POWER-Up client access to the repo copy
                            content = repo.get_yum_dotrepo_content(gpgcheck=0, client=True)
                            filename = repo_id + '-powerup.repo'
                            self.sw_vars['yum_powerup_repo_files'][filename] = content
                        self.log.info('Repository setup complete')
                        self.prep_post()

    def prep_init(self, eval_ver=False, non_int=False):
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
        self._setup_firewall()
        self._setup_nginx_server()

    def prep(self, eval_ver=False, non_int=False):

        self.prep_init()

        self.create_ibmai_repo()

        self.create_wmla_license()

        self.create_spectrum_conductor()

        self.create_spectrum_dli()

        self.create_cuda_drv_repo()

        self.create_dependency_repo()

        self.create_conda_content_repo()

        self.create_conda_free_repo()

        self.create_conda_main_repo()

        # self.create_conda_forge_repo()

        self.create_pypi_repo()

        self.create_epel_repo()

        self.create_custom_repo()

        # Display status
        self.status_prep()

    def prep_post(self, eval_ver=False, non_int=False):
        # write software-vars file.
        try:
            if 'ana_powerup_repo_channels' in self.sw_vars:
                chan_list = []
                for chan in ('free', 'main', 'ibmai'):
                    for item in self.sw_vars['ana_powerup_repo_channels']:
                        if chan in item:
                            chan_list.append(item)
                # prepend any remaining which are not in ('free', 'main', 'ibmai')
                for item in self.sw_vars['ana_powerup_repo_channels']:
                    if item not in chan_list:
                        chan_list = [item] + chan_list
                self.sw_vars['ana_powerup_repo_channels'] = chan_list
        except:
            pass
        if not os.path.exists(GEN_SOFTWARE_PATH):
            os.mkdir(GEN_SOFTWARE_PATH)
        if self.eval_ver:
            with open(GEN_SOFTWARE_PATH + f'{self.sw_vars_file_name}', 'w') as f:
                f.write('# Do not edit this file. This file is autogenerated.\n')
            with open(GEN_SOFTWARE_PATH + f'{self.sw_vars_file_name}', 'a') as f:
                yaml.dump(self.sw_vars, f, default_flow_style=False)
        else:
            with open(GEN_SOFTWARE_PATH + f'{self.sw_vars_file_name}', 'w') as f:
                f.write('# Do not edit this file. This file is autogenerated.\n')
            with open(GEN_SOFTWARE_PATH + f'{self.sw_vars_file_name}', 'a') as f:
                yaml.dump(self.sw_vars, f, default_flow_style=False)

    def _load_content(self):
        try:
            self.content = yaml.load(open(GEN_SOFTWARE_PATH +
                                     f'content-{self.my_name}.yml'),
                                     Loader=AttrDictYAMLLoader)
        except IOError:
            self.log.error(f'Error opening the content list file '
                           f'(content-{self.base_filename}.yml)')
            sys.exit('Exit due to critical error')

    def _load_pkglist(self):
        try:
            self.pkgs = yaml.load(open(GEN_SOFTWARE_PATH + f'pkg-lists-'
                                  f'{self.base_filename}.yml'))
        except IOError:
            self.log.error(f'Error opening the pkg lists file '
                           f'(pkg-lists-{self.base_filename}.yml)')
            sys.exit('Exit due to critical error')

    def _load_filelist(self):
        # When searching for files in other web servers, the fileglobs are converted to
        # regular expressions. An asterisk (*) after a bracket is converted to a
        # regular extression of [0-9]{0,3} Other asterisks are converted to regular
        # expression of .*
        try:
            file_lists = yaml.load(open(GEN_SOFTWARE_PATH + f'file-lists-'
                                   f'{self.base_filename}.yml'))
        except IOError:
            self.log.info('Error while reading installation file lists for '
                          'WMLA Enterprise')
            sys.exit('exiting')
            input('\nPress enter to continue')
        else:
            if self.eval_ver:
                self.globs = file_lists['globs_eval']
                self.files = file_lists['files_eval']
            else:
                self.globs = file_lists['globs']
                self.files = file_lists['files']

    def _add_dependent_packages(self, repo_dir, dep_list, also_get_newer=True):
        def yum_download(repo_dir, dep_list):
            cmd = (f'yumdownloader --archlist={self.arch} --destdir '
                   f'{repo_dir} {dep_list}')
            resp, err, rc = sub_proc_exec(cmd)
            if rc != 0:
                self.log.error('An error occurred while downloading dependent '
                               f'packages.\n Download command: {cmd}'
                               f'rc: {rc} err: {err}')
            resp = resp.splitlines()
            for item in resp:
                if 'No Match' in item:
                    self.log.error(f'Dependent packages download error. {item}')

        if also_get_newer:
            dep_list_list = dep_list.split()
            versionless_dep_list, ver = parse_rpm_filenames(dep_list_list)
            versionless_dep_list = ' '.join(versionless_dep_list)
            yum_download(repo_dir, versionless_dep_list)

            # Form new dep_list consisting of packages not already in repo_dir
            in_repo_list = os.listdir(repo_dir)
            dep_list = ''
            for _file in dep_list_list:
                if _file + '.rpm' not in in_repo_list:
                    dep_list = dep_list + _file + ' '

        if dep_list:
            yum_download(repo_dir, dep_list)

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

        print(bold(f'\nInitializing clients for install from  Repository : '
              f'{self.repo_shortname}\n'))
        self.sw_vars['init_clients'] = self.repo_shortname

        self._update_software_vars()

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
                           GEN_SOFTWARE_PATH + f"{self.sw_vars_file_name}"))
        else:
            cmd = ('{} -i {} {}init_clients.yml --extra-vars "@{}" '
                   .format(get_ansible_playbook_path(),
                           self.sw_vars['ansible_inventory'],
                           GEN_SOFTWARE_PATH,
                           GEN_SOFTWARE_PATH + f"{self.sw_vars_file_name}"))
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
            resp, err, rc = sub_proc_exec(cmd, shell=True, env=ENVIRONMENT_VARS)
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
                self.sw_vars['proc_family'] = self.proc_family
                self.sw_vars['arch'] = self.arch
                self.sw_vars['eval_ver'] = self.eval_ver
                self.prep_post()
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
            cmd += f'--extra-vars "@{GEN_SOFTWARE_PATH}{self.sw_vars_file_name}" '
        else:
            cmd += ' --ask-become-pass '
        resp, err, rc = sub_proc_exec(cmd, shell=True, env=ENVIRONMENT_VARS)
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

    def _get_file_paths(self, fileglob):
        """ Searches under the software server's root directory for the
        given fileglob.
        Args:
            fileglob (str): String with a bash style file glob.
        Returns: A list of sorted paths. For rpm files, the newest version
        will be last
        """
        paths = glob.glob(f'{self.root_dir}**/{fileglob}', recursive=True)
        paths = sorted(paths)
        return paths

    def _get_yum_repo_dirs(self, repo_id):
        _dirglob = os.path.join(f'{self.root_dir}', 'repos', f'{repo_id}',
                                '**', 'repodata')
        paths = glob.glob(_dirglob, recursive=True)
        paths = [path.rstrip('repodata') for path in paths]
        return paths

    def _get_conda_repo_dirs(self, repo_id, repo_name):
        if 'Main' in repo_name:
            name = 'main'
        elif 'Free' in repo_name:
            name = 'free'
        else:
            name = ''
        _dirglob = os.path.join(f'{self.root_dir}', 'repos', f'{repo_id}',
                                '**', f'{name}', f'linux-{self.arch}', '')
        paths = glob.glob(_dirglob, recursive=True)
        paths = [path.rstrip('/') for path in paths]
        paths = [path.rstrip(f'linux-{self.arch}') for path in paths]
        return paths

    def _extract_processor_family(self, _dir):
        if '/p8/' in _dir:
            self.proc_family = 'p8'
        elif '/p9/' in _dir:
            self.proc_family = 'p9'
        elif '/x86_64/' in _dir:
            self.proc_family = 'x86_64'

    def _update_software_vars(self):
        self.sw_vars['content_files'] = {}
        self.sw_vars['ana_powerup_repo_channels'] = []
        self.sw_vars['yum_powerup_repo_files'] = {}
        self.sw_vars['root_dir_nginx'] = self.root_dir_nginx
        for _item in self.content:
            item = self.content[_item]
            if item.type == 'file':
                if self.eval_ver and hasattr(item, 'fileglob_eval'):
                    _glob = item.fileglob_eval
                else:
                    _glob = item.fileglob
                _glob = _glob.format(arch=self.arch)
                paths = self._get_file_paths(_glob)

                if len(set(paths)) > 1:
                    release_lvl_file = item.filename_eval if self.eval_ver \
                        else item.filename
                    print(f'Multiple files matching the requirement for\n {_glob}\nare '
                          'present in the PowerUp software server. The release level\n'
                          f'is: {release_lvl_file}\n'
                          'Please select a file for this WMLA installation.')
                    ch, path = get_selection(paths)
                elif len(paths) == 1:
                    path = paths[0]
                else:
                    self.log.error(f'No {_glob} found in software server.')
                    path = ''
                self.sw_vars['content_files'][_item.replace('_', '-')] = path
            elif item.type == 'conda':
                repo_id = item.repo_id
                repo_name = item.repo_name
                dirs = self._get_conda_repo_dirs(repo_id, repo_name)
                if len(dirs) == 1:
                    _dir = dirs[0]
                elif len(dirs) > 1:
                    msg = (f'More than one {item.name} repository exists in the\n'
                           'PowerUp software server. Please select the repository '
                           'to use for this WMLA installation.')
                    print(msg)
                    ch, _dir = get_selection(dirs)
                else:
                    self.log.error(f'No {repo_name} found in software server.')
                    _dir = ''
                _dir = _dir[len(self.root_dir_nginx):]
                # form .condarc channel entry. Note that conda adds
                # the corresponding 'noarch' channel automatically.
                if _dir:
                    channel = f'  - http://{{{{ host_ip.stdout }}}}{_dir}'
                else:
                    channel = ''
                if channel not in self.sw_vars['ana_powerup_repo_channels']:
                    self.sw_vars['ana_powerup_repo_channels'].append(channel)

            elif item.type == 'yum':
                repo_id = item.repo_id.format(arch=self.arch)
                repo_name = item.repo_name.format(arch=self.arch)
                dirs = self._get_yum_repo_dirs(repo_id)
                if self.proc_family and repo_name == 'Dependencies':
                    dirs = [d for d in dirs if self.proc_family in d]

                if len(dirs) == 1:
                    _dir = dirs[0]

                elif len(dirs) > 1:
                    msg = (f'More than one {item.name} repository exists in the\n'
                           'PowerUp software server. Please select the repository '
                           'to use for this WMLA installation.')
                    print(msg)
                    ch, _dir = get_selection(dirs)
                else:
                    self.log.error(f'No {repo_id} repo found in software server.')
                    _dir = ''
                _dir = _dir.rstrip('/')

                if repo_id == 'dependencies' and not self.proc_family:
                    self._extract_processor_family(_dir)

                filename = repo_id + '-powerup.repo'
                if _dir:
                    repo = PowerupRepo(repo_id, repo_name, self.root_dir, self.arch,
                                       self.proc_family)
                    dotrepo_content = repo.get_yum_dotrepo_content(repo_dir=_dir,
                                                                   gpgcheck=0,
                                                                   client=True)
                    self.sw_vars['yum_powerup_repo_files'][filename] = dotrepo_content
                else:
                    self.sw_vars['yum_powerup_repo_files'][filename] = ''
            elif item.type == 'simple':
                path = self._get_file_paths(item.type)
                if path:
                    path = path[0]
                    self.sw_vars['pypi_repo_path'] = path
                    self.sw_vars['pypi_http_path'] = path[len(self.root_dir_nginx):]
                else:
                    self.sw_vars['pypi_repo_path'] = ''

    def _install_ready(self):
        ready = True
        ready = ready and all([item != '' for item in
                              self.sw_vars['content_files'].values()])
        ready = ready and all([item != '' for item in
                              self.sw_vars['yum_powerup_repo_files'].values()])
        ready = ready and all([item != '' for item in
                              self.sw_vars['ana_powerup_repo_channels']])
        return ready

    def _init_clients_check(self):
        ready = True
        if 'init_clients' not in self.sw_vars:
            self.log.error('Initialization of clients has not been run. Please run\n'
                           'pup software --init-clients \n'
                           'before running install.')
            ready = False
        if self.repo_shortname != self.sw_vars['init_clients']:
            self.log.warning('The cluster nodes were last configured for installation\n'
                             'from self.sw_vars["init_clients"], but you are requesting\n'
                             'installation from {self.repo_shortname}')
            if not get_yesno('Okay to continue? '):
                ready = False

        if self.sw_vars['proc_family'] != self.proc_family:
            sys.exit('\nThe cluster nodes were last configured for installation as '
                     f'{self.sw_vars["proc_family"]}\n, but you are running install '
                     f'with processor family set to {self.proc_family}.\nPlease rerun '
                     ' init-clients. Exiting.')
            ready = False

        if self.sw_vars['arch'] != self.arch:
            sys.exit('\nThe cluster nodes were last configured for installation as '
                     f'{self.sw_vars["arch"]}\n, but you are running install '
                     f'with architecture set to {self.arch}.\nPlease rerun '
                     '--init-clients. Exiting.')
            ready = False

        if self.sw_vars['eval_ver'] != self.eval_ver:
            sys.exit('\nThe cluster nodes were last configured for installation with '
                     f'evaluation version set to{self.sw_vars["eval_ver"]}\n'
                     f'but you are running the current install '
                     f'with evaluation version set to {self.eval_ver}.\n Please rerun '
                     '--init-clients. Exiting.')
            ready = False

        return ready

    def install(self):
        self._update_software_vars()
        if not self._install_ready():
            msg = ('\nNot all content is present in the software server. Re-run\n'
                   'the prep phase of installation to update needed content\n'
                   'then re-run install.\n'
                   'Hint: The "--step" flag can be used to address specific\n'
                   'missing content.\nRun: pup software -h for additional '
                   'help\nExiting\n')
            sys.exit(msg)

        if not self._init_clients_check():
            sys.exit('Exiting')

        print(bold(f'\n     Installing from Repository : {self.repo_shortname}\n'))

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
        specific_arch = "_" + self.arch if self.arch == 'x86_64' else ""
        install_tasks = yaml.load(open(GEN_SOFTWARE_PATH +
                                       f'{self.my_name}_install_procedure{specific_arch}.yml'))

        for task in install_tasks:
            if 'engr_mode' in task['tasks'] and not self.eng_mode:
                continue
            heading1(f"Client Node Action: {task['description']}")
            if task['description'] == "Install Anaconda installer":
                _interactive_anaconda_license_accept(
                    self.sw_vars['ansible_inventory'],
                    self.sw_vars['content_files']['anaconda'])
            elif (task['description'] ==
                    "Check WMLA License acceptance and install to root"):
                _interactive_wmla_license_accept(
                    self.sw_vars['ansible_inventory'], self.eval_ver)
            extra_args = ''
            if 'hosts' in task:
                extra_args = f"--limit \'{task['hosts']},localhost\'"
            self._run_ansible_tasks(task['tasks'], extra_args)
#            if self.eng_mode == 'gather-dependencies':
#                pass
        print('Done')

    def _run_ansible_tasks(self, tasks_path, extra_args=''):
        log = logger.getlogger()
        tasks_path = f'{self.my_name}_ansible/' + tasks_path
        if self.sw_vars['ansible_become_pass'] is not None:
            extra_args += ' --vault-password-file ' + self.vault_pass_file
        elif 'become:' in open(f'{GEN_SOFTWARE_PATH}{tasks_path}').read():
            extra_args += ' --ask-become-pass'
        verbose = ''
        # verbose = '-vvv'
        if self.eval_ver:
            cmd = (f'{get_ansible_playbook_path()} -i '
                   f'{self.sw_vars["ansible_inventory"]} '
                   f'{GEN_SOFTWARE_PATH}{self.my_name}_ansible/run.yml {verbose} '
                   f'--extra-vars "task_file={GEN_SOFTWARE_PATH}{tasks_path}" '
                   f'--extra-vars "@{GEN_SOFTWARE_PATH}{self.sw_vars_file_name}" '
                   f'{extra_args}')
        else:
            cmd = (f'{get_ansible_playbook_path()} -i '
                   f'{self.sw_vars["ansible_inventory"]} '
                   f'{GEN_SOFTWARE_PATH}{self.my_name}_ansible/run.yml {verbose} '
                   f'--extra-vars "task_file={GEN_SOFTWARE_PATH}{tasks_path}" '
                   f'--extra-vars "@{GEN_SOFTWARE_PATH}{self.sw_vars_file_name}" '
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

            if self.log_lvl == 'debug':
                rc = sub_proc_display(cmd, shell=True, env=ENVIRONMENT_VARS)
                resp = ''
                err = ''
            else:
                resp, err, rc = sub_proc_exec(cmd, shell=True, env=ENVIRONMENT_VARS)

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
    resp, err, rc = sub_proc_exec(cmd, env=ENVIRONMENT_VARS)

    # If install directory already exists assume license has been accepted
    if rc == 0:
        print(f'Anaconda license already accepted on {hostname}')
    else:
        print(bold('Manual Anaconda license acceptance required on at least '
                   'one client!'))
        rlinput(f'Press Enter to run interactively on {hostname}')
        fn = os.path.basename(ana_path)
        cmd = f'{base_cmd} sudo ~/{fn} -p {ip}'
        rc = sub_proc_display(cmd, env=ENVIRONMENT_VARS)
        if rc == 0:
            print('\nLicense accepted. Acceptance script will be run quietly '
                  'on remaining servers.')
        else:
            log.error("Anaconda license acceptance required to continue!")
            sys.exit('Exiting')
    return rc


def _interactive_wmla_license_accept(ansible_inventory, eval_ver):
    log = logger.getlogger()

    cmd = (f'ansible-inventory --inventory {ansible_inventory} --list')
    resp, err, rc = sub_proc_exec(cmd, shell=True)
    inv = json.loads(resp)

    # accept_cmd = 'IBM_POWERAI_LICENSE_ACCEPT=yes;/opt/anaconda3/bin/accept-ibm-wmla-license.sh '
    accept_cmd = 'sudo env IBM_POWERAI_LICENSE_ACCEPT=yes /opt/anaconda3/bin/accept-ibm-wmla-license.sh '
    if eval_ver:
        check_cmd = 'ls ~/.powerai/ibm-wmla-license-eval/1.2.0/license/status.dat'
    else:
        check_cmd = 'ls ~/.powerai/ibm-wmla-license/1.2.0/license/status.dat'

    print(bold('Acceptance of the WMLA Enterprise license is required on '
               'all nodes in the cluster.'))
    rlinput(f'Press Enter to silently install on each host')

    for hostname, hostvars in inv['_meta']['hostvars'].items():
        base_cmd = f'ssh -t {hostvars["ansible_user"]}@{hostname} '
        if "ansible_ssh_common_args" in hostvars:
            base_cmd += f'{hostvars["ansible_ssh_common_args"]} '
        if "ansible_ssh_private_key_file" in hostvars:
            base_cmd += f'-i {hostvars["ansible_ssh_private_key_file"]} '

        cmd = base_cmd + check_cmd
        resp, err, rc = sub_proc_exec(cmd, env=ENVIRONMENT_VARS)
        if rc == 0:
            print(bold('WMLA Enterprise license already accepted on '
                       f'{hostname}'))
        else:
            run = True
            while run:
                print(bold('\nRunning WMLA Enterprise license script on '
                           f'{hostname}'))
                cmd = base_cmd + accept_cmd
                rc = sub_proc_display(cmd, env=ENVIRONMENT_VARS)
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
            for key, value in yaml.load(open(envs_path)).items():
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
