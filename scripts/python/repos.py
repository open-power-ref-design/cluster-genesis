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

import argparse
import os
import re

import lib.logger as logger
from lib.utilities import sub_proc_display, sub_proc_exec, heading1, rlinput, \
    get_url, setup_source_file


class remote_nginx_repo(object):
    def __init__(self, arch='ppc64le', rhel_ver='7'):
        self.repo_name = 'nginx repo'
        self.arch = arch
        self.rhel_ver = str(rhel_ver)
        self.log = logger.getlogger()

    def yum_create_remote(self):
        """Create the /etc/yum.repos.d/
        """
        self.log.info('Registering remote repo {} with yum.'.format(self.repo_name))
        repo_link_path = '/etc/yum.repos.d/nginx.repo'
        if os.path.isfile(repo_link_path):
            self.log.info('Remote linkage for repo {} already exists.'
                          .format(self.repo_name))
            self.log.info(repo_link_path)

        self.log.info('Creating remote repo link.')
        self.log.info(repo_link_path)
        with open(repo_link_path, 'w') as f:
            f.write('[nginx]\n')
            f.write('name={}\n'.format(self.repo_name))
            f.write(f'baseurl=http://nginx.org/packages/mainline/rhel/'
                    '{self.rhel_ver}/{self.arch}\n')
            f.write('gpgcheck=0\n')
            f.write('enabled=1\n')


class local_epel_repo(object):

    def __init__(self, repo_name='epel-ppc64le', arch='ppc64le', rhel_ver='7'):
        repo_name = 'epel-ppc64le' if repo_name is None else repo_name
        self.repo_name = repo_name.lower()
        self.arch = arch
        self.rhel_ver = str(rhel_ver)
        self.log = logger.getlogger()

    def yum_create_local(self):
        """Create the /etc/yum.repos.d/
        """
        self.log.info('Registering local repo {} with yum.'.format(self.repo_name))

        repo_link_path = '/etc/yum.repos.d/{}-local.repo'.format(self.repo_name)
        if os.path.isfile(repo_link_path):
            self.log.info('Remote linkage for repo {} already exists.'
                          .format(self.repo_name))
            self.log.info(repo_link_path)

        self.log.info('Creating local repo link.')
        self.log.info(repo_link_path)
        with open(repo_link_path, 'w') as f:
            f.write('[{}-local]\n'.format(self.repo_name))
            f.write('name={}_local_repo\n'.format(self.repo_name))
            f.write('baseurl="file:///srv/repos/epel/{}/epel-{}/"\n'
                    .format(self.rhel_ver, self.arch))
            f.write('gpgcheck=0')

    def sync(self):
        self.log.info('Syncing repository {}'.format(self.repo_name))
        self.log.info('This can take many minutes or hours for large repositories\n')
        cmd = 'reposync -a {} -r {} -p /srv/repos/epel/{} -l -m'.format(
            self.arch, self.repo_name, self.rhel_ver)
        rc = sub_proc_display(cmd)
        if rc != 0:
            self.log.error(f'Failed EPEL repo sync. {rc}')
        else:
            self.log.info('EPEL sync finished successfully')

    def create_dirs(self):
        """Create directories to be used to hold the repository
        """
        if not os.path.exists(f'/srv/repos/epel/{self.rhel_ver}'):
            self.log.info(f'creating directory /srv/repos/epel/{self.rhel_ver}')
            os.makedirs('/srv/repos/epel/{}'.format(self.rhel_ver))
        else:
            self.log.info(f'Directory /srv/repos/epel/{self.rhel_ver} already exists')

    def create_meta(self):
        if not os.path.exists('/srv/repos/epel/{}/{}/repodata'.format(
                self.rhel_ver, self.repo_name)):
            self.log.info('Creating repository metadata and databases')
            cmd = 'createrepo -v -g comps.xml /srv/repos/epel/{}/{}'.format(
                self.rhel_ver, self.repo_name)
            proc, rc = sub_proc_exec(cmd)
            if rc != 0:
                self.log.error('Repo creation error: {}'.format(rc))
            else:
                self.log.info('Repo create process finished succesfully')
        else:
            self.log.debug(f'Repo {self.repo_name} already exists. Skipping metadata'
                           'creation.')

    def yum_create_remote(self, repo_url=None):
        """Creates the .repo file in /etc/yum.repos.d used as the external source
        for syncing the local repo.
        Inputs:
            repo_url: (str) URL for the external repo source
        """
        self.log.info('Registering remote repo {} with yum.'.format(self.repo_name))

        repo_link_path = '/etc/yum.repos.d/{}.repo'.format(self.repo_name)
        if os.path.isfile(repo_link_path):
            self.log.info('Remote linkage for repo {} already exists. Rewriting'
                          .format(self.repo_name))
            self.log.info(repo_link_path)

        self.log.info('Creating remote repo link.')
        self.log.info(repo_link_path)

        src = ' '
        while len(src) != 1 or src not in 'pi':
            src = input('Use public mirror or internal web site (p/i)? ')

        if src == 'i':
            if not repo_url:
                repo_url = f'http://9.3.210.46/repos/epel/{self.rhel_ver}/epel-{self.arch}'
            tmp = get_url(repo_url, 'EPEL')
            if tmp is None:
                return repo_url
            else:
                repo_url = tmp

        with open(repo_link_path, 'w') as f:
            f.write('[{}]\n'.format(self.repo_name))
            f.write('name=Extra Packages for Enterprise Linux {} - {}\n'.format(self.rhel_ver, self.arch))
            if src == 'i':
                f.write(f'baseurl={repo_url}\n')
                f.write(f'#metalink=https://mirrors.fedoraproject.org/metalink?repo=epel-{self.rhel_ver}&arch={self.arch}\n')
            else:
                f.write('#baseurl=http://download.fedoraproject.org/pub/epel/{}/{}\n'.format(self.rhel_ver, self.arch))
                f.write(f'metalink=https://mirrors.fedoraproject.org/metalink?repo=epel-{self.rhel_ver}&arch={self.arch}\n')
            f.write('failovermethod=priority\n')
            f.write('enabled=1\n')
            f.write('gpgcheck=1\n')
            f.write('gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-{}\n'.format(self.rhel_ver))
            f.write('\n')
            f.write('[{}-debuginfo]\n'.format(self.repo_name))
            f.write('name=Extra Packages for Enterprise Linux {} - {} - Debug\n'.format(self.rhel_ver, self.arch))
            f.write('#baseurl=http://download.fedoraproject.org/pub/epel/{}/{}/debug\n'.format(self.rhel_ver, self.arch))
            f.write('metalink=https://mirrors.fedoraproject.org/metalink?repo=epel-debug-{}&arch={}\n'.format(self.rhel_ver, self.arch))
            f.write('failovermethod=priority\n')
            f.write('enabled=0\n')
            f.write('gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-{}\n'.format(self.rhel_ver))
            f.write('gpgcheck=1\n')
            f.write('\n')
            f.write('[{}-source]\n'.format(self.repo_name))
            f.write('name=Extra Packages for Enterprise Linux {} - {} - Source\n'.format(self.rhel_ver, self.arch))
            f.write('#baseurl=http://download.fedoraproject.org/pub/epel/{}/SRPMS\n'.format(self.rhel_ver))
            f.write('metalink=https://mirrors.fedoraproject.org/metalink?repo=epel-source-{}&arch={}\n'.format(self.rhel_ver, self.arch))
            f.write('failovermethod=priority\n')
            f.write('enabled=0\n')
            f.write('gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-{}\n'.format(self.rhel_ver))
            f.write('gpgcheck=1\n')
            return repo_url

    def get_yum_powerup_client(self):
        """Generate the yum.repo file for the powerup remote client. The file
        content is stored in a dictionary with two key value pairs. The first pair
        is the filename. 'filename':'name of repofile'. The filename needs to end
        in .repo and is typically written to /etc/yum.repos.d/ on the client. The
        second key value pair is 'content': 'file content'. The file content will
        be a string with lines separated by \n and can thus be written to the
        client with a single write. The file content will contain formatting
        braces {host} which need to be formatted with the deployer hostname or
        ip address. ie; repofile['content'].format(host=powerup_host / powerup_ip)
        """
        self.log.debug('Creating powerup client epel repo file content'
                       .format(self.repo_name))

        repo_file = {'filename': self.repo_name + '-powerup.repo', 'content': '[{}'
                     .format(self.repo_name) + '-powerup]\n'}
        repo_file['content'] += 'name={}'.format(self.repo_name) + '-powerup\n'
        repo_file['content'] += 'baseurl=http://{host}' + 'repos/epel/{}/{}\n'.format(
            self.rhel_ver, self.repo_name)
        repo_file['content'] += 'enabled=1\n'
        repo_file['content'] += 'gpgcheck=0\n'
        return repo_file


class local_cuda_repo(object):

    def __init__(self, repo_name='cuda', arch='ppc64le', rhel_ver='7'):
        repo_name = 'cuda' if repo_name is None else repo_name
        self.repo_name = repo_name.lower()
        self.arch = arch
        self.rhel_ver = str(rhel_ver)
        self.log = logger.getlogger()

    def yum_create_local(self):
        """Create the /etc/yum.repos.d/
        """
        self.log.info('Registering local repo {} with yum.'.format(self.repo_name))

        repo_link_path = f'/etc/yum.repos.d/{self.repo_name}-local.repo'
        if os.path.isfile(repo_link_path):
            self.log.info('Remote linkage for repo {} already exists.'
                          .format(self.repo_name))
            self.log.info(repo_link_path)

        self.log.info('Creating local repo link.')
        self.log.info(repo_link_path)
        with open(repo_link_path, 'w') as f:
            f.write('[{}-local]\n'.format(self.repo_name))
            f.write('name={}_local_repo\n'.format(self.repo_name))
            f.write('baseurl="file:///srv/repos/epel/{}/epel-{}/"\n'
                    .format(self.rhel_ver, self.arch))
            f.write('gpgcheck=0')

    def sync(self):
        self.log.info('Syncing repository {}'.format(self.repo_name))
        self.log.info('This can take many minutes or hours for large repositories\n')
        cmd = f'reposync -a {self.arch} -r {self.repo_name} -p /srv/repos/{self.repo_name} -l -m'
        rc = sub_proc_display(cmd)
        if rc != 0:
            self.log.error(f'Failed {self.repo_name} repo sync. {rc}')
        else:
            self.log.info(f'{self.repo_name} sync finished successfully')

    def create_dirs(self):
        """Create directories to be used to hold the repository
        """
        if not os.path.exists(f'/srv/repos/{self.repo_name}'):
            self.log.info(f'creating directory /srv/repos/{self.rhel_ver}')
            os.makedirs('/srv/repos/{self.repo_name}'
        else:
            self.log.info(f'Directory /srv/repos/{self.repo_name} already exists')

    def create_meta(self):
        if not os.path.exists('/srv/repos/{self.repo_name}/repodata':
            self.log.info('Creating repository metadata and databases')
            cmd = 'createrepo -v -g comps.xml /srv/repos/{self.repo_name}'
            proc, rc = sub_proc_exec(cmd)
            if rc != 0:
                self.log.error('Repo creation error: {}'.format(rc))
            else:
                self.log.info('Repo create process finished succesfully')
        else:
            self.log.debug(f'Repo {self.repo_name} already exists. Skipping metadata'
                           'creation.')

    def yum_create_remote(self, repo_url=None):
        """Creates the .repo file in /etc/yum.repos.d used as the external source
        for syncing the local repo.
        Inputs:
            repo_url: (str) URL for the external repo source
        """
        self.log.info('Registering remote repo {} with yum.'.format(self.repo_name))

        repo_link_path = '/etc/yum.repos.d/{}.repo'.format(self.repo_name)
        if os.path.isfile(repo_link_path):
            self.log.info('Remote linkage for repo {} already exists. Rewriting'
                          .format(self.repo_name))
            self.log.info(repo_link_path)

        self.log.info('Creating remote repo link.')
        self.log.info(repo_link_path)

        src = ' '
        while len(src) != 1 or src not in 'pi':
            src = input('Use public mirror or internal web site (p/i)? ')

        if src == 'i':
            if not repo_url:
                repo_url = f'http://9.3.210.46/repos/{self.repo_name}'
            tmp = get_url(repo_url, 'cuda')
            if tmp is None:
                return repo_url
            else:
                repo_url = tmp

        with open(repo_link_path, 'w') as f:
            f.write('[{}]\n'.format(self.repo_name))
            f.write('name=cuda'
            if src == 'i':
                f.write(f'baseurl={repo_url}\n')
            else:
                f.write('baseurl=http://developer.download.nvidia.com/compute/cuda/repos/rhel7/ppc64le\n'
            f.write('enabled=1\n')
            f.write('gpgcheck=1\n')
            f.write('gpgkey=http://developer.download.nvidia.com/compute/cuda/repos/rhel7/ppc64le/7fa2af80.pub')
            return repo_url

    def get_yum_powerup_client(self):
        """Generate the yum.repo file for the powerup remote client. The file
        content is stored in a dictionary with two key value pairs. The first pair
        is the filename. 'filename':'name of repofile'. The filename needs to end
        in .repo and is typically written to /etc/yum.repos.d/ on the client. The
        second key value pair is 'content': 'file content'. The file content will
        be a string with lines separated by \n and can thus be written to the
        client with a single write. The file content will contain formatting
        braces {host} which need to be formatted with the deployer hostname or
        ip address. ie; repofile['content'].format(host=powerup_host / powerup_ip)
        """
        self.log.debug('Creating powerup client {self.repo_name} repo file content')

        repo_file = {'filename': self.repo_name + '-powerup.repo', 'content': '[{}'
                     .format(self.repo_name) + '-powerup]\n'}
        repo_file['content'] += 'name={}'.format(self.repo_name) + '-powerup\n'
        repo_file['content'] += 'baseurl=http://{host}' + 'repos/{self.repo_name}\n'
        repo_file['content'] += 'enabled=1\n'
        repo_file['content'] += 'gpgcheck=0\n'
        return repo_file


def create_repo_from_rpm_pkg(pkg_name, pkg_file, dest_dir, src_dir, web=None):
        heading1(f'Setting up the {pkg_name} repository')
        #cuda_dir = 'cuda-rpm'
        ver = ''
        src_installed, src_path = setup_source_file(cuda_src, cuda_dir, 'PowerAI')
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
            ver0 = ver.split('.')[0]
            ver1 = ver.split('.')[1]
            ver2 = ver.split('.')[2]
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


if __name__ == '__main__':
    """ setup reposities. sudo env "PATH=$PATH" python repo.py
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('repo_name', nargs='?',
                        help='repository name')

    parser.add_argument('--print', '-p', dest='log_lvl_print',
                        help='print log level', default='info')

    parser.add_argument('--file', '-f', dest='log_lvl_file',
                        help='file log level', default='info')

    args = parser.parse_args()
    # args.repo_name = args.repo_name[0]

    if args.log_lvl_print == 'debug':
        print(args)

    logger.create(args.log_lvl_print, args.log_lvl_file)

#    nginx_repo = remote_nginx_repo()
#    nginx_repo.yum_create_remote()
#
    repo = local_epel_repo(args.repo_name)
    repo.yum_create_remote()
    repo.create_dirs()
    repo.sync()
    repo.create()
    repo.yum_create_local()
    client_file = repo.get_yum_client_powerup()
    print(client_file['filename'])
    print(client_file['content'].format(host='192.168.1.2'))
