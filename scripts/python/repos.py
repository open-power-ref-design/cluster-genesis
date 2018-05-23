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
import glob
import os
import re
from shutil import copy2, copytree, rmtree, Error
import code

import lib.logger as logger
from lib.utilities import sub_proc_display, sub_proc_exec, heading1, rlinput, \
    get_url, get_yesno, get_selection, bold


#def setup_source_dir():
#    """Interactive selection of a source dir. Searching starts in the cwd.
#    Returns:
#        path (str or None) : Selected path
#    """
#    log = logger.getlogger()
#    path = os.path.abspath('.')
#    while True:
#        path = rlinput(f'Enter an absolute directory location (S to skip): ', path)
#        if path == 'S':
#            return None
#        if os.path.exists(path):
#            print()
#            #listdir = os.listdir(path) #.sort()
#            #code.interact(banner='here', local=dict(globals(), **locals()))
#            top, dirs, files = next(os.walk(path))
#            files.sort()
#            cnt = 0
#            rpm_cnt = 0
#            for f in files:
#                if f.endswith('.rpm'):
#                    rpm_cnt += 1
#                    if rpm_cnt <= 10:
#                        print(f)
#            if rpm_cnt >0:
#                print(bold(f'{rpm_cnt} rpm files found'))
#                print(f'including the {min(10, rpm_cnt)} files above.\n')
#            else:
#                print(bold('No rpm files found\n'))
#            for f in files:
#                if cnt + rpm_cnt >= 10:
#                    break
#                if not f.endswith('.rpm') and not f.startswith('.'):
#                    print(f)
#                    cnt += 1
#            if cnt >0:
#                print(f'{cnt} non-rpm files found')
#                print(f'including the {min(10, cnt)} files above.')
#            else:
#                print('No non rpm files found')
#            print(f'\nThe entered path was: {top}')
#            r = get_yesno('Use the entered path? ')
#            if r == 'yes':
#                return path
#            print('Sub directories of the entered directory: ')
#            dirs.sort()
#            print(dirs)


def setup_source_file(src_name, dest, name=None):
    """Interactive selection of a source file and copy it to the /srv/<dest>
    directory. The source file can include file globs. Searching starts in the
    /home directory and then expands to the entire file system if no matches
    found in any home directory.
    Inputs:
        src_name (str): Source file name to look for. Can include file globs
        dest (str) : destination directory. Will be created if necessary under
            /srv/
        name (str): Name for the source. Used only for display and prompts.
    Returns:
        state (bool) : State is True/False to indicate that a file
            matching the src_name exists or was copied to the dest directory.
        src_path (str) : The path for the file found / chosen by the user. If
            only a single match is found it is used without choice and returned.
    """
    log = logger.getlogger()
    if not name:
        name = dest.capitalize()
    if not os.path.exists(f'/srv/{dest}'):
        os.mkdir(f'/srv/{dest}')
    g = glob.glob(f'/srv/{dest}/{src_name}')
    if g:
        print(f'\n{name} source file already exists in the \n'
              'POWER-Up software server directory')
        for item in g:
            print(item)
        print()
        r = get_yesno(f'Do you wish to update the {name} source file', 'yes/n')
    else:
        r = 'yes'
    if r == 'yes':
        print()
        log.info(f'Searching for {name} source file')
        # Search home directories first
        cmd = (f'find /home -name {src_name}')
        resp, err, rc = sub_proc_exec(cmd)
        while not resp:
            # Expand search to entire file system
            cmd = (f'find / -name {src_name}')
            resp, err, rc = sub_proc_exec(cmd)
            if not resp:
                print(f'{name} source file {src_name} not found')
                r = get_yesno('Search again', 'y/no')
                if r == 'n':
                    log.error(f'{name} source file {src_name} not found.\n {name} is not'
                              ' setup.')
                    return False, None

        ch, src_path = get_selection(resp, prompt='Select a source file: ')
        log.info(f'Using {name} source file: {src_path}')
        if f'/srv/{dest}/' in src_path:
            print(f'Skipping copy. \n{src_path} already \nin /srv/{dest}/')
            return True, src_path

        try:
            copy2(f'{src_path}', f'/srv/{dest}/')
        except Error as err:
            self.log.debug(f'Failed copying {name} source to /srv/{dest}/ '
                           f'directory. \n{err}')
            return False, None
        else:
            log.info(f'Successfully installed {name} source file '
                     'into the POWER-Up software server.')
            return True, src_path
    else:
        return True, None


class PowerupRepoFromRepo(object):
    """Sets up a yum repository for access by POWER-Up software clients.
    The repo is first sync'ed locally from the internet or a user specified
    URL which should reside on another host.
    """
    def __init__(self, repo_id, repo_name, arch='ppc64le', rhel_ver='7'):
        self.repo_id = repo_id
        self.repo_name = repo_name
        self.arch = arch
        self.rhel_ver = str(rhel_ver)
        self.repo_dir = f'/srv/repos/{self.repo_id}/rhel{self.rhel_ver}'
        self.log = logger.getlogger()

    def get_repo_path(self):
        return self.repo_path

    def get_action(self):
        new = True
        if os.path.isfile(f'/etc/yum.repos.d/{self.repo_id}.repo') and \
                os.path.exists(self.repo_dir + f'/{self.repo_id}'):
            new = False
            print(f'\nDo you want to sync the local {self.repo_name} repository'
                  ' at this time?\n')
            print('This can take a few minutes.\n')
            items = 'Yes,no,Sync repository and Force recreation of yum ".repo" files'
            ch, item = get_selection(items, 'Y,n,F', sep=',')
        else:
            print(f'\nDo you want to create a local {self.repo_name} repository'
                  'at this time?\n')
            print('This can take a significant amount of time')
            ch = get_yesno(prompt='Create Repo? ', yesno='Y/n')
        return ch, new

    def get_yum_dotrepo_content(self, url=None, gpgkey=None, gpgcheck=1,
                                metalink=False, local=False, client=False):
        """creates the content for a yum '.repo' file.
        """
        self.log.info(f'Creating yum ". repo" file for {self.repo_name}')
        content = ''
        # repo id
        if client:
            content += f'[{self.repo_id}-powerup]\n'
        elif local:
            content += f'[{self.repo_id}-local]\n'
        else:
            content = f'[{self.repo_id}]\n'

        # name
        content += f'name={self.repo_name}\n'

        # repo url
        if local:
            content += f'baseurl=file://{self.repo_dir}/{self.repo_id}/\n'
        elif client:
            content += 'baseurl=http://{host}/repos/' + f'{self.repo_id}/\n'
        elif metalink:
            content += f'metalink={url}\n'
            content += 'failovermethod=priority\n'
        elif url:
            content += f'baseurl={url}\n'
        else:
            self.log.error('No ".repo" link type was specified')
        content += 'enabled=1\n'
        content += f'gpgcheck={gpgcheck}\n'
        if gpgcheck:
            content += f'gpgkey={gpgkey}'
        return content

    def get_repo_url(self, url, alt_url=None):
        """Allows the user to choose the default url or enter an alternate
        Inputs:
            repo_url: (str) URL or metalink for the external repo source
        """

        ch, item = get_selection('Public mirror.Alternate web site', 'pub.alt', '.',
                                 'Select source: ')
        if ch == 'alt':
            if not alt_url:
                alt_url = f'http://host/repos/{self.repo_id}/'
            tmp = get_url(alt_url, prompt_name=self.repo_name)
            if tmp is None:
                return None
            else:
                if tmp[-1] != '/':
                    tmp = tmp + '/'
                alt_url = tmp
        url = alt_url if ch == 'alt' else url
        return url

    def write_yum_dot_repo_file(self, content, repo_link_path=None):
        if repo_link_path is None:
            if f'{self.repo_id}-local' in content:
                repo_link_path = f'/etc/yum.repos.d/{self.repo_id}-local.repo'
            else:
                repo_link_path = f'/etc/yum.repos.d/{self.repo_id}.repo'
        with open(repo_link_path, 'w') as f:
            f.write(content)

    def create_dirs(self, pad_dir=''):
        """Create directories to be used to hold the repository
        inputs:
            pad_dir (str)
        """
        if not os.path.exists(self.repo_dir):
            self.log.debug(self.repo_dir)
            os.makedirs(self.repo_dir)
        else:
            self.log.debug(f'Directory {self.repo_dir} already exists')

    def sync(self):
        self.log.info(f'Syncing {self.repo_name}')
        self.log.info('This can take many minutes or hours for large repositories\n')
        cmd = f'reposync -a {self.arch} -r {self.repo_id} -p {self.repo_dir} -l -m'
        rc = sub_proc_display(cmd)
        if rc != 0:
            self.log.error(f'Failed {self.repo_name} repo sync. {rc}')
        else:
            self.log.info(f'{self.repo_name} sync finished successfully')

    def create_meta(self, update=False):
        if not os.path.exists(f'{self.repo_dir}/{self.repo_id}/repodata'):
            self.log.info('Creating repository metadata and databases')
        else:
            self.log.info('Updating repository metadata and databases')
        print('This may take a few minutes.')
        if not update:
            cmd = f'createrepo -v {self.repo_dir}/{self.repo_id}'
        else:
            cmd = f'createrepo -v --update {self.repo_dir}/{self.repo_id}'
        resp, err, rc = sub_proc_exec(cmd)
        if rc != 0:
            self.log.error(f'Repo creation error: rc: {rc} stderr: {err}')
        else:
            self.log.info('Repo create process finished succesfully')


class PowerupRepoFromDir(object):
    def __init__(self, repo_id, repo_name, arch='ppc64le', rhel_ver='7'):
        self.repo_id = repo_id
        self.repo_name = repo_name
        self.arch = arch
        self.rhel_ver = rhel_ver
        self.repo_dir = f'/srv/repos/{self.repo_id}/rhel{self.rhel_ver}/{self.repo_id}'
        self.log = logger.getlogger()

    def copy_dirs(self, src_dir):
        if os.path.exists(self.repo_dir):
            r = get_yesno(f'Directory {self.repo_dir} already exists. OK to replace it? ')
            if r == 'yes':
                rmtree(self.repo_dir, ignore_errors=True)
            else:
                self.log.info('Directory not created')
                return None
        try:
            copytree(src_dir, self.repo_dir)
        except Error as exc:
            print(f'Copy error: {exc}')
            return None
        else:
            return self.repo_dir

    def create_meta(self):
        if not os.path.exists(f'/srv/repos/{self.repo_id}/{self.rhel_ver}/'
                              f'{self.repo_id}/repodata'):
            self.log.info('Creating repository metadata and databases')
        else:
            self.log.info('Updating repository metadata and databases')
        print('This may take a few minutes.')
        #cmd = f'createrepo -v /srv/repos/{self.repo_id}/{self.rhel_ver}'
        cmd = f'createrepo -v /srv/repos/{self.repo_id}/rhel{self.rhel_ver}/{self.repo_id}'
        resp, err, rc = sub_proc_exec(cmd)
        if rc != 0:
            self.log.error(f'Repo creation error: rc: {rc} stderr: {err}')
        else:
            self.log.info('Repo create process finished succesfully')


def create_repo_from_rpm_pkg(pkg_name, pkg_file, src_dir, dst_dir, web=None):
        heading1(f'Setting up the {pkg_name} repository')
        ver = ''
        src_installed, src_path = setup_source_file(cuda_src, cuda_dir, 'PowerAI')
        ver = re.search(r'\d+\.\d+\.\d+', src_path).group(0) if src_path else ''
        self.log.debug(f'{pkg_name} source path: {src_path}')
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


class RemoteNginxRepo(object):
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
