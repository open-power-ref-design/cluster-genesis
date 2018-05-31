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
    get_url, get_dir, get_yesno, get_selection, get_file_path, bold
from lib.exception import UserException


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
        state (bool) : state is True if a file matching the src_name exists
            in the dest directory or was succesfully copied there. state is
            False if there is no file matching src_name in the dest directory
            OR if the attempt to copy a new file to the dest directory failed.
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

    if get_yesno(f'Do you wish to update the {name} source file', 'yes/n'):
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

                if not get_yesno('Search again', 'y/no', default='y'):
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
    elif g:
        return True, None
    else:
        return False, None


class PowerupRepo(object):
    """Base class for creating a yum repository for access by POWER-Up software
     clients.
    """
    def __init__(self, repo_id, repo_name, arch='ppc64le', rhel_ver='7'):
        self.repo_id = repo_id
        self.repo_name = repo_name
        self.arch = arch
        self.rhel_ver = str(rhel_ver)
        self.repo_dir = f'/srv/repos/{self.repo_id}/rhel{self.rhel_ver}/{self.repo_id}'
        self.log = logger.getlogger()

    def get_repo_dir(self):
        return self.repo_dir

    def get_src_path(self, src_name):
        """Search for src_name and allow interactive selection if more than one match
        """
        while True:
            cmd = (f'find /home -name {src_name}')
            resp, err, rc = sub_proc_exec(cmd)
            if rc != 0:
                self.log.error(f'Error searching for {src_name}')
                return None
            if not resp:
                cmd = (f'find / -name {src_name}')
                resp, err, rc = sub_proc_exec(cmd)
                if rc != 0:
                    self.log.error(f'Error searching for {src_name}')
                    return None
                if not resp:
                    print(f'{name} source file {src_name} not found')
                    if not get_yesno('Search again', 'y/no', default='y'):
                        log.error(f'{name} source file {src_name} not found.\n {name} is not'
                                  ' setup.')
                        return None
            else:
                ch, src_path = get_selection(resp, prompt='Select a source file: ')
                return src_path

    def copy_to_srv(self, src_path, dst):
        dst_dir = f'/srv/{dst}'
        if not os.path.exists(dst_dir):
            os.mkdir(dst_dir)
        copy2(src_path, dst_dir)

    def get_yum_dotrepo_content(self, url=None, repo_dir=None, gpgkey=None, gpgcheck=1,
                                metalink=False, local=False, client=False):
        """creates the content for a yum '.repo' file. To create content for a POWER-Up
        client, set client=True. To create content for this node (the POWER-Up node),
        set local=True. If neither client or local is true, content is created for this
        node to access a remote URL. Note: client and local should be considered
        mutaully exclusive. If repo_dir is not included, self.repo_dir is used as the
        baseurl for client and local .repo content.
        """
        self.log.info(f'Creating yum ". repo" file for {self.repo_name}')
        if not repo_dir:
            repo_dir = self.repo_dir
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
            content += f'baseurl=file://{repo_dir}/\n'
        elif client:
            d = repo_dir.lstrip('/')
            d = d.lstrip('srv')
            content += 'baseurl=http://{host}' + f'{d}/\n'
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

    def write_yum_dot_repo_file(self, content, repo_link_path=None):
        if repo_link_path is None:
            if f'{self.repo_id}-local' in content:
                repo_link_path = f'/etc/yum.repos.d/{self.repo_id}-local.repo'
            else:
                repo_link_path = f'/etc/yum.repos.d/{self.repo_id}.repo'
        with open(repo_link_path, 'w') as f:
            f.write(content)

    def create_meta(self, update=False):
        if not os.path.exists(f'{self.repo_dir}/repodata'):
            self.log.info('Creating repository metadata and databases')
        else:
            self.log.info('Updating repository metadata and databases')
        print('This may take a few minutes.')
        if not update:
            cmd = f'createrepo -v {self.repo_dir}'
        else:
            cmd = f'createrepo -v --update {self.repo_dir}'
        resp, err, rc = sub_proc_exec(cmd)
        if rc != 0:
            self.log.error(f'Repo creation error: rc: {rc} stderr: {err}')
        else:
            self.log.info(f'Repo create process for {self.repo_id} finished'
                          ' succesfully')


class PowerupRepoFromRpm(PowerupRepo):
    """Sets up a yum repository for access by POWER-Up software clients.
    The repo is created from an rpm file selected interactively by the user.
    """
    def __init__(self, repo_id, repo_name, arch='ppc64le', rhel_ver='7'):
        super(PowerupRepoFromRpm, self).__init__(repo_id, repo_name, arch, rhel_ver)

    def get_rpm_path(self, filepath='/home/**/*.rpm'):
        """Interactive search for the rpm path.
        Returns: Path to file or None
        """
        while True:
            self.rpm_path = get_file_path(filepath)
            # Check for .rpm files in the chosen file
            cmd = 'rpm -qlp self.rpm_path'
            resp, err, rc = sub_proc_exec(cmd)
            if self.rpm_path:
                if '.rpm' not in resp:
                    print('There are no ".rpm" files in the selected path')
                    if get_yesno('Use selected path? ', default='n'):
                        return self.rpm_path
            else:
                return None

    def get_src_path(self, src_name):
        """Search for src_name and allow interactive selection if more than one match
        """
        while True:
            cmd = (f'find /home -name {src_name}')
            resp, err, rc = sub_proc_exec(cmd)
            if rc != 0:
                self.log.error(f'Error searching for {src_name}')
                return None
            if not resp:
                cmd = (f'find / -name {src_name}')
                resp, err, rc = sub_proc_exec(cmd)
                if rc != 0:
                    self.log.error(f'Error searching for {src_name}')
                    return None
                if not resp:
                    print(f'{name} source file {src_name} not found')
                    if not get_yesno('Search again', 'y/no', default='y'):
                        log.error(f'{name} source file {src_name} not found.\n {name} is not'
                                  ' setup.')
                        return None
            else:
                ch, self.rpm_path = get_selection(resp, prompt='Select a source file: ')
                return self.rpm_path

    def copy_rpm(self):
        """copy the selected rpm file (self.rpm_path) to the /srv/{self.repo_id}
        directory.
        The directory is created if it does not exist.
        """
        dst_dir = f'/srv/{self.repo_id}'
        if not os.path.exists(dst_dir):
            os.mkdir(dst_dir)
        copy2(self.rpm_path, dst_dir)

    def extract_rpm(self):
        """Extracts files from the selected rpm file to a repository directory
        under /srv/repoid/rhel7/repoid. If a repodata directory is included in
        the extracted data, then the path to repodata directory is returned
        Inputs: Uses self.repo_dir and self.repo_id
        Outputs:
            repodata_dir : absolute path to repodata directory
        """
        extract_dir = self.repo_dir
        if not os.path.exists(extract_dir):
            os.makedirs(extract_dir)
        os.chdir(extract_dir)
        cmd = f'rpm2cpio {self.rpm_path} | sudo cpio -div'
        resp, err, rc = sub_proc_exec(cmd, shell=True)
        if rc != 0:
            self.log.error(f'Failed extracting {self.rpm_path}')

        repodata_dir = glob.glob(f'{extract_dir}/**/repodata', recursive=True)
        if repodata_dir:
            return os.path.dirname(repodata_dir[0])
        else:
            return None

#    def create_meta(self, repodata_dir=None, update=False):
#        if not repodata_dir:
#            #repodata_dir = os.path.join(self_repo_dir, self.repo_id)
#            repodata_dir = self_repo_dir
#        if not os.path.exists(f'{repodata_dir}/repodata'):
#            self.log.info('Creating repository metadata and databases')
#        else:
#            self.log.info('Updating repository metadata and databases')
#        print('This may take a few minutes.')
#        if not update:
#            cmd = f'createrepo -v {repodata_dir}'
#        else:
#            cmd = f'createrepo -v --update {repodata_dir}'
#        resp, err, rc = sub_proc_exec(cmd)
#        if rc != 0:
#            self.log.error(f'Repo creation error: rc: {rc} stderr: {err}')
#        else:
#            self.log.info('Repo create process finished succesfully')


class PowerupRepoFromRepo(PowerupRepo):
    """Sets up a yum repository for access by POWER-Up software clients.
    The repo is first sync'ed locally from the internet or a user specified
    URL which should reside on another host.
    """
    def __init__(self, repo_id, repo_name, arch='ppc64le', rhel_ver='7'):
        super(PowerupRepoFromRepo, self).__init__(repo_id, repo_name, arch, rhel_ver)

    def get_action(self):
        new = True
        if os.path.isfile(f'/etc/yum.repos.d/{self.repo_id}.repo') and \
                os.path.exists(self.repo_dir):
            new = False
            print(f'\nDo you want to sync the local {self.repo_name}\nrepository'
                  ' at this time?\n')
            print('This can take a few minutes.\n')
            items = 'Yes,no,Sync repository and Force recreation of yum ".repo" files'
            ch, item = get_selection(items, 'Y,n,F', sep=',')
        else:
            print(f'\nDo you want to create a local {self.repo_name}\n repository'
                  ' at this time?\n')
            print('This can take a significant amount of time')
            ch = 'Y' if get_yesno(prompt='Create Repo? ', yesno='Y/n') else 'n'
        return ch, new

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
            tmp = get_url(alt_url, prompt_name=self.repo_name, repo_chk=True)
            if tmp is None:
                return None
            else:
                if tmp[-1] != '/':
                    tmp = tmp + '/'
                alt_url = tmp
        url = alt_url if ch == 'alt' else url
        return url

    def sync(self):
        self.log.info(f'Syncing {self.repo_name}')
        self.log.info('This can take many minutes or hours for large repositories\n')
        cmd = (f'reposync -a {self.arch} -r {self.repo_id} -p'
               f'{os.path.dirname(self.repo_dir)} -l -m')
        rc = sub_proc_display(cmd)
        if rc != 0:
            self.log.error(bold(f'\nFailed {self.repo_name} repo sync. {rc}'))
            raise UserException
        else:
            self.log.info(f'{self.repo_name} sync finished successfully')


class PowerupRepoFromDir(PowerupRepo):
    def __init__(self, repo_id, repo_name, arch='ppc64le', rhel_ver='7'):
        super(PowerupRepoFromDir, self).__init__(repo_id, repo_name, arch, rhel_ver)

    def copy_dirs(self, src_dir=None):
        if os.path.exists(self.repo_dir):
            r = get_yesno(f'Directory {self.repo_dir} already exists. OK to replace it? ')
            if r == 'yes':
                rmtree(os.path.dirname(self.repo_dir), ignore_errors=True)
            else:
                self.log.info('Directory not created')
                return None, None

        src_dir = get_dir(src_dir)
        if not src_dir:
            return None, None

        try:
            dest_dir = self.repo_dir
            copytree(src_dir, dest_dir)
        except Error as exc:
            print(f'Copy error: {exc}')
            return None, dest_dir
        else:
            return src_dir, dest_dir


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
    repo.sync()
    repo.create()
    repo.yum_create_local()
    client_file = repo.get_yum_client_powerup()
    print(client_file['filename'])
    print(client_file['content'].format(host='192.168.1.2'))
