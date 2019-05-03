#!/usr/bin/env python
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
import json
import glob
import os
import re
from shutil import copy, copytree, rmtree, Error
import time

import lib.logger as logger
from lib.utilities import sub_proc_display, sub_proc_exec, get_url, \
    get_dir, get_yesno, get_selection, get_file_path, get_src_path, bold, \
    parse_conda_filenames, parse_rpm_filenames, parse_pypi_filenames, get_rpm_info
from lib.exception import UserException


def setup_source_file(name, src_glob, dest_dir, base_dir, url='', alt_url='http://',
                      src2=None):
    """Interactive selection of a source file and copy it to the {self.repo_base_dir}
    {dest_dir} directory. The source file can include file globs and can come from
    a URL or the local disk. Local disk searching starts in the /home and /root
    directory and then expands to the entire file system if no matches
    found in those directories. URLs must point to the directory with the file
    or a parent directory.
    Inputs:
        name (str) : Name used in prompts and logs to refer to the file being
            dealt with.
        src_glob (str): Source file name to look for. Can include file globs
        src2(str): An additional file to be copied from the same source as src_glob.
            This file would typically be a support file such as an entitlement file.
        dest_dir (str) : destination directory. Will be created if necessary under
            {base_dir}.
        base_dir (str): Base directory. Typically set to the web browser root_dir.
        url (str): url for the public web site where the file can be obtained.
            leave empty to prevent prompting for a public url option.
        alt_url (str): Alternate url where the file can be found. Usually this
            is an intranet web site.
        name (str): Name for the source. Used for prompts and dest dir (/srv/{name}).
    Returns:
        state (bool) : state is True if a file matching the src_name exists
            in the dest directory or was successfully copied there. state is
            False if there is no file matching src_name in the dest directory
            OR if the attempt to copy a new file to the dest directory failed.
        src_path (str) : The path for the file found / chosen by the user. If
            only a single match is found it is used without choice and returned.
        dest_path (str)
    """
    src_path = None
    dest_path = None
    log = logger.getlogger()
    exists = glob.glob(f'{base_dir}{dest_dir}/**/{src_glob}', recursive=True)
    if exists:
        dest_path = exists[0]
    copied = False
    ch = ''
    while not copied:
        ch, item = get_selection('Copy from URL\nSearch local Disk', 'U\nD',
                                 allow_none=True)

        if ch == 'U':
            _url = alt_url if alt_url else 'http://<host>/'
            if url:
                ch1, item = get_selection('Public web site.Alternate web site', 'P.A',
                                          'Select source: ', '.')
                if ch1 == 'P':
                    _url = url
            rc = -9
            while _url is not None and rc != 0:
                _url = get_url(_url, fileglob=src_glob)
                if _url:
                    abs_dest_dir = f'{base_dir}{dest_dir}'
                    if not os.path.exists(dest_dir):
                        os.mkdir(dest_dir)
                    cmd = f'wget -P {abs_dest_dir} {_url}'
                    rc = sub_proc_display(cmd)
                    if rc != 0:
                        log.error(f'Failed downloading {name} source to'
                                  f' {abs_dest_dir}/ directory. \n{rc}')
                        copied = False
                    else:
                        src_path = _url
                        dest_path = os.path.join(dest_dir, os.path.basename(_url))
                        copied = True
                    if src2:
                        _url2 = os.path.join(os.path.dirname(_url), src2)
                        cmd = f'wget -P {abs_dest_dir} {_url2}'
                        rc = sub_proc_display(cmd)
                        if rc != 0:
                            log.error(f'Failed downloading {name} source file {src2} to'
                                      f' {abs_dest_dir}/ directory. \n{rc}')
                            copied = False
                        else:
                            src_path = _url
                            copied = copied and True
        elif ch == 'D':
            src_path = get_src_path(src_glob)
            if src_path:
                abs_dest_dir = f'{base_dir}{dest_dir}'
                if not os.path.exists(abs_dest_dir):
                    os.mkdir(abs_dest_dir)
                try:
                    copy(src_path, abs_dest_dir)
                except Error as err:
                    log.debug(f'Failed copying {name} source file to {abs_dest_dir}/ '
                              f'directory. \n{err}')
                    copied = False
                else:
                    log.info(f'Successfully installed {name} source file '
                             'into the POWER-Up software server.')
                    dest_path = os.path.join(abs_dest_dir, os.path.basename(src_path))
                    copied = True
                if src2:
                    try:
                        src2_path = os.path.join(os.path.dirname(src_path), src2)
                        copy(src2_path, abs_dest_dir)
                    except Error as err:
                        log.debug(f'Failed copying {name} source file to {abs_dest_dir}/ '
                                  f'directory. \n{err}')
                        copied = False
                    else:
                        log.info(f'Successfully installed {name} source file {src2} '
                                 'into the POWER-Up software server.')
                        copied = copied and True
        elif ch == 'N':
            log.info(f'No {name.capitalize()} source file copied to POWER-Up '
                     'server directory')
            break

    return src_path, dest_path, copied


def get_name_dir(name):
    """Construct a reasonable directory name from a descriptive name. Replace
    spaces with dashes, convert to lower case and remove 'content' and 'Repository'
    if present.
    """
    return name.lower().replace(' ', '-').replace('-content', '')\
        .replace('-repository', '')


def powerup_file_from_disk(name, file_glob, base_dir):
    log = logger.getlogger()
    name_src = get_name_dir(name)
    dest_path = None
    src_path = get_src_path(file_glob)
    if src_path:
        if not os.path.exists(f'{base_dir}{name_src}'):
            os.mkdir(f'{base_dir}{name_src}')
        try:
            copy(src_path, f'{base_dir}{name_src}/')
        except Error as err:
            log.debug(f'Failed copying {name} source file to {base_dir}{name_src}/ '
                      f'directory. \n{err}')
        else:
            log.info(f'Successfully installed {name} source file '
                     'into the POWER-Up software server.')
            dest_path = os.path.join(f'{base_dir}{name_src}/',
                                     os.path.basename(src_path))
    return src_path, dest_path


class PowerupRepo(object):
    """Base class for creating a repository for access by POWER-Up software
     clients.
    Args:
        repo_id (str): ID for the repo. For yum repos, this is the yum repo id.
        repo_name (str):
        repo_base_dir (str): This is the base directory for the repository. In the
            case of software install modules, it is the catenation of root_dir_nginx
            and the base_dir (base_dir for software install modules is typically
            derived from the install module name or user provided)
    """
    def __init__(self, repo_id, repo_name, repo_base_dir, arch='ppc64le',
                 proc_family='family', rhel_ver='7'):
        self.repo_id = repo_id
        self.repo_name = repo_name
        self.arch = arch
        self.proc_family = proc_family
        self.repo_type = 'yum'
        self.rhel_ver = str(rhel_ver)
        self.repo_base_dir = repo_base_dir  # '/srv'
        if self.repo_id in ('dependencies', 'rhel-common', 'rhel-optional',
                            'rhel-supplemental', 'rhel-extras'):
            self.yumrepo_dir = (f'{self.repo_base_dir}repos/{self.repo_id}/rhel'
                                f'{self.rhel_ver}/{self.proc_family}/{self.repo_id}')
        else:
            self.yumrepo_dir = (f'{self.repo_base_dir}repos/{self.repo_id}/rhel'
                                f'{self.rhel_ver}/{self.repo_id}')
        self.log = logger.getlogger()

    def get_repo_dir(self):
        return self.yumrepo_dir

    def get_repo_base_dir(self):
        return self.repo_base_dir

    def get_ver_state(self, ver_in_repo, ver_in_pkg_lst):
        """Compares two version of the form n.m.o.p.... Versions are first
        padded to the same length, then compared on a field bases.
           Returns -1, 0, 1 if ver_in_repo is older, same , newer than
           ver_in_pkg_lst.
        """
        if ver_in_pkg_lst == '':
            return 0

        ver_in_repo_s = ver_in_repo.split('.')
        ver_in_pkg_lst_s = ver_in_pkg_lst.split('.')

        if len(ver_in_repo_s) > len(ver_in_pkg_lst_s):
            # pad to equal length (equal number of fields)
            ver_in_pkg_lst_s = ((['0'] * (len(ver_in_repo_s) -
                                len(ver_in_pkg_lst_s))) + ver_in_pkg_lst_s)
        elif len(ver_in_pkg_lst_s) > len(ver_in_repo_s):
            ver_in_repo_s = ((['0'] * (len(ver_in_pkg_lst_s) -
                             len(ver_in_repo_s))) + ver_in_repo_s)
        state = 0
        # pad each field to at least 5 characters
        for r in range(len(ver_in_repo_s)):
            if (('     ' + ver_in_repo_s[r])[-5:] >
                    ('     ' + ver_in_pkg_lst_s[r])[-5:]):
                state = 1
                break
            elif (('     ' + ver_in_pkg_lst_s[r])[-5:] >
                  ('     ' + ver_in_repo_s[r])[-5:]):
                state = -1
                break
        return state

    def get_pkg_state(self, pkg_in_repo, pkg):
        """Determines whether a package in a yum repo is
        older, equal to or newer than the pkg called out in the pkg
        list file.
        Args:
            pkg(dict): Pkg from pkg-list in form returned by
                parse_rpm_filenames. ie {basename: {'ep': epoch, 'ver':
                version, 'rel': release_lvl}}
            pkg_in_repo(dict): Pkg in the yum repo.
        Returns (int) -1, 0 , 1 = pg in PowerUp repo is older, same,
            newer version
        """
        state = self.get_ver_state(pkg_in_repo['ver'], pkg['ver'])
        if state == 0:
            if pkg['ep'] == pkg_in_repo['ep'] or pkg['ep'] == '':
                if pkg['rel'] == pkg_in_repo['rel'] or pkg['rel'] == '':
                    state = 0
                elif pkg['rel'] > pkg_in_repo['rel']:
                    state = -1
                else:
                    state = 1
            elif pkg['ep'] > pkg_in_repo['ep']:
                state = -1
            else:
                state = 1
        return state

    def verify_pkgs(self, pkglist):
        pkgs_vers = parse_rpm_filenames(pkglist, form='dict')
        pkg_lst_cnt = len(pkgs_vers)
        try:
            filelist = os.listdir(self.yumrepo_dir)
        except FileNotFoundError:
            filelist = []
        filelist = [fi for fi in filelist if fi[-4:] == '.rpm']
        files_vers = get_rpm_info(filelist, self.yumrepo_dir)
        pkg_cnt = 0
        nwr_cnt = 0
        old_cnt = 0
        for _file in pkgs_vers:
            if _file in files_vers:
                pkg_cnt += 1
                ver_state = self.get_pkg_state(files_vers[_file], pkgs_vers[_file])
                if ver_state == 1:
                    nwr_cnt += 1
                if ver_state == -1:
                    self.log.debug(f'Older yum pkg: {_file}')
                    old_cnt += 1
            else:
                self.log.debug(f'Missing yum pkg: {_file}')
        return pkg_lst_cnt, pkg_cnt, nwr_cnt, old_cnt

    def get_action(self, exists, exists_prompt_yn=False):
        if exists:
            print(f'\nDo you want to sync the local {self.repo_name}\n'
                  ' at this time?\n')
            print('This can take a few minutes.\n')
            ch = 'Y' if get_yesno(prompt='Sync Repo? ', yesno='y/n',
                                  default='y') else 'n'
        else:
            print(f'\nDo you want to create a local {self.repo_name}\n'
                  'at this time?\n')
            print('This can take several minutes.')
            ch = 'Y' if get_yesno(prompt='Create Repo? ', yesno='y/n',
                                  default='y') else 'n'
        return ch

    def get_repo_url(self, url, alt_url=None, name='', contains=[], excludes=[],
                     filelist=[]):
        """Allows the user to choose the default url or enter an alternate
        Inputs:
            repo_url: (str) URL or metalink for the default external repo source
            alt_url: (str) An alternate url that the user can modify
            contains: (list of strings) Filter criteria. The presented list is
                restricted to those urls that contain elements from 'contains' and no
                elements of 'excludes'.
            excludes: (list of strings)
            filelist: (list of strings) Can be globs. Used to validate a repo. The
                specified files must be present
        """
        if name:
            print(f'\nChoice for source of {name} repository:')
        if url:
            sel_txt = 'Public mirror.Alternate web site'
            sel_chcs = 'P.A'
        else:
            sel_txt = ''
            sel_chcs = ''
#            sel_txt = 'Alternate web site'
#            sel_chcs = 'A'
        _url = None
        while _url is None:
            if sel_txt:
                ch, item = get_selection(sel_txt, sel_chcs,
                                         'Choice: ', '.', allow_none=True)
            else:
                ch = 'A'
            if ch == 'P':
                _url = url
                break
            if ch == 'A':
                if not alt_url:
                    base_name = self.repo_base_dir.strip('/').split('/')[-1]
                    alt_url = f'http://<host>/{base_name}/repos/{self.repo_id}/'
                _url = get_url(alt_url, prompt_name=self.repo_name,
                               repo_chk=self.repo_type, contains=contains,
                               excludes=excludes, filelist=filelist)
                if _url and _url[-1] != '/':
                    _url = _url + '/'
                    break
            elif ch == 'N':
                _url = None
                break
        return _url

    def copy_to_srv(self, src_path, dst):
        dst_dir = f'{self.repo_base_dir}/{dst}'
        if not os.path.exists(dst_dir):
            os.mkdir(dst_dir)
        copy(src_path, dst_dir)

    def copytree_to_srv(self, src_dir, dst):
        """Copy a directory recursively to the POWER-Up server base directory.
        Note that if the directory exists already under the self.base_dir durectory, it
        will be recursively erased before the copy begins.
        """
        dst_dir = f'{self.repo_base_dir}/{dst}'
        if os.path.exists(dst_dir):
            os.removedirs(dst_dir)
        copytree(src_dir, dst_dir)

    def get_yum_dotrepo_content(self, url=None, repo_dir=None, gpgkey=None, gpgcheck=1,
                                metalink=False, local=False, client=False):
        """creates the content for a yum '.repo' file. To create content for a POWER-Up
        client, set client=True. To create content for this node (the POWER-Up node),
        set local=True. If neither client or local is true, content is created for this
        node to access a remote URL. Note: client and local should be considered
        mutually exclusive. If repo_dir is not included, self.yumrepo_dir is used as the
        baseurl for client and local .repo content.
        """
        self.log.debug(f'Creating yum ". repo" file for {self.repo_name}')
        if not repo_dir:
            repo_dir = self.yumrepo_dir
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
            rstrip = len(self.repo_base_dir) - \
                len(self.repo_base_dir.rstrip('/').split('/')[-1]) - 2
            d = repo_dir[rstrip:]
            content += 'baseurl=http://{{ host_ip.stdout }}' + f'{d}/\n'
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
        """Writes '.repo' files to /etc/yum.repos.d/. If the .repo file already
        exists and the new content is different than the existing content, any
        existing yum cache data and any repodata for that repository is erased.
        """
        if repo_link_path is None:
            if f'{self.repo_id}-local' in content:
                repo_link_path = f'/etc/yum.repos.d/{self.repo_id}-local.repo'
            else:
                repo_link_path = f'/etc/yum.repos.d/{self.repo_id}.repo'
                if os.path.exists(repo_link_path):
                    with open(repo_link_path, 'r') as f:
                        curr_content = f.read()
                        if curr_content != content:
                            self.log.info(f'Sync source for repository {self.repo_id} '
                                          'has changed')
                            cache_dir = (f'/var/cache/yum/{self.arch}/7Server/'
                                         f'{self.repo_id}')
                            if os.path.exists(cache_dir):
                                self.log.info(f'Removing existing cache directory '
                                              f'{cache_dir}')
                                rmtree(cache_dir)
                            if os.path.exists(cache_dir + '-local'):
                                self.log.info(f'Removing existing cache directory '
                                              f'{cache_dir}-local')
                                rmtree(cache_dir + '-local')
                            if os.path.exists(f'{self.yumrepo_dir}/repodata'):
                                self.log.info(f'Removing existing repodata for '
                                              f'{self.repo_id}')
                                rmtree(f'{self.yumrepo_dir}/repodata')
                            if os.path.isfile(f'/etc/yum.repos.d/{self.repo_id}-local.repo'):
                                self.log.info(f'Removing existing local .repo for'
                                              f' {self.repo_id}-local')
                                os.remove(f'/etc/yum.repos.d/{self.repo_id}-local.repo')
        with open(repo_link_path, 'w') as f:
            f.write(content)

    def create_meta(self, update=False):
        action = ('update', 'Updating') if update else ('create', 'Creating')
        self.log.info(f'{action[1]} repository metadata and databases')
        print('This may take a few minutes.')
        if not update:
            cmd = f'createrepo -v {self.yumrepo_dir}'
        else:
            cmd = f'createrepo -v --update {self.yumrepo_dir}'
        resp, err, rc = sub_proc_exec(cmd)
        if rc != 0:
            self.log.error(f'Repo creation error: rc: {rc} stderr: {err}')
        else:
            self.log.info(f'Repo {action[0]} metadata for {self.repo_id} finished'
                          ' successfully')


class PowerupRepoFromRpm(PowerupRepo):
    """Sets up a yum repository for access by POWER-Up software clients.
    The repo is created from an rpm file selected interactively by the user.
    """
    def __init__(self, repo_id, repo_name, repo_base_dir, arch='ppc64le', proc_family='family',
                 rhel_ver='7'):
        super(PowerupRepoFromRpm, self).__init__(repo_id, repo_name, repo_base_dir, arch,
                                                 proc_family, rhel_ver)

    def get_rpm_path(self, filepath='/home/**/*.rpm'):
        """Interactive search for the rpm path.
        Returns: Path to file or None
        """
        continu = True
        while continu:
            self.rpm_path = get_file_path(filepath)
            if '.rpm' not in self.rpm_path:
                r = get_yesno('Continue searching')
                if not r:
                    continu = False
            # Check for .rpm files in the chosen file
            cmd = f'rpm -qlp {self.rpm_path}'
            resp, err, rc = sub_proc_exec(cmd)
            if rc != 0:
                print('An error occured while querying the selcted rpm file')
                return
            else:
                if '.rpm' not in resp:
                    print('There are no ".rpm" files in the selected file')
                else:
                    return self.rpm_path

    def copy_rpm(self, src_path):
        """copy the selected rpm file (self.rpm_path) to the /srv/{self.repo_id}
        directory.
        The directory is created if it does not exist.
        """
        self.rpm_path = src_path
        dst_dir = f'{self.yumrepo_dir}{self.repo_id}'
        if not os.path.exists(dst_dir):
            os.mkdir(dst_dir)
        copy(self.rpm_path, dst_dir)
        dest_path = os.path.join(dst_dir, os.path.basename(src_path))
        dest_path = os.path.join(dst_dir, os.path.basename(src_path))
        print(dest_path)
        return dest_path

    def extract_rpm(self, src_path):
        """Extracts files from the selected rpm file to a repository directory
        under /{repo_base_dir}/repoid/rhel7/repoid. If a repodata directory is included
        in the extracted data, then the path to repodata directory is returned
        Inputs: Uses self.yumrepo_dir and self.repo_id
        Outputs:
            repodata_dir : absolute path to repodata directory if one exists
        """
        extract_dir = self.yumrepo_dir
        if not os.path.exists(extract_dir):
            os.makedirs(extract_dir)

        # Move to the target directory
        os.chdir(extract_dir)
        cmd = f'rpm2cpio {src_path} | sudo cpio -div'
        resp, err, rc = sub_proc_exec(cmd, shell=True)
        if rc != 0:
            self.log.error(f'Failed extracting {src_path}')

        repodata_dir = glob.glob(f'{extract_dir}/**/repodata', recursive=True)
        if repodata_dir:
            repo_dir = os.path.dirname(repodata_dir[0])
            return repo_dir
        else:
            return None


class PowerupYumRepoFromRepo(PowerupRepo):
    """Sets up a yum repository for access by POWER-Up software clients.
    The repo is first sync'ed locally from the internet or a user specified
    URL which could reside on another host or from a local directory. (ie
    a file based URL pointing to a mounted disk. eg file:///mnt/my-mounted-usb)
    """
    def __init__(self, repo_id, repo_name, repo_base_dir, arch='ppc64le',
                 proc_family='family', rhel_ver='7'):
        super(PowerupYumRepoFromRepo, self).__init__(repo_id, repo_name, repo_base_dir,
                                                     arch, proc_family, rhel_ver)

    def sync(self):
        self.log.info(f'Syncing {self.repo_name}')
        self.log.info('This can take many minutes or hours for large repositories\n')
        cmd = (f'reposync -a {self.arch} -r {self.repo_id} -p '
               f'{os.path.dirname(self.yumrepo_dir)} -l -m')
        rc = sub_proc_display(cmd)
        if rc != 0:
            self.log.error(bold(f'\nFailed {self.repo_name} repo sync. {rc}'))
            raise UserException
        else:
            self.log.info(f'{self.repo_name} sync finished successfully')


class PowerupAnaRepoFromRepo(PowerupRepo):
    """Sets up an Anaconda repository for access by POWER-Up software clients.
    The repo is first sync'ed locally from the internet or a user specified
    URL which could reside on another host or from a local directory. (ie
    a file based URL pointing to a mounted disk. eg file:///mnt/my-mounted-usb)
    To download the entire repository, leave the accept list (acclist) and rejlist
    empty. Note that the accept list and reject list are mutually exclusive.
    inputs:
        acclist (str): Accept list. List of files to download. If specified,
            only the listed files will be downloaded.
        rejlist (str): Reject list. List of files to reject. If specified,
            the entire repository except the files in the rejlist will be downloaded.
    """
    def __init__(self, repo_id, repo_name, repo_base_dir, arch='ppc64le', rhel_ver='7'):
        super(PowerupAnaRepoFromRepo, self).__init__(repo_id, repo_name,
                                                     repo_base_dir, arch, rhel_ver)
        self.repo_type = 'ana'
        self.anarepo_dir = f'{self.repo_base_dir}repos/{self.repo_id}'
        if self.repo_id == 'anaconda':
            self.anarepo_dir = os.path.join(self.anarepo_dir, 'pkgs', f'{self.repo_name}')

    def get_repo_dir(self):
        return self.anarepo_dir

    def _get_conda_pkg_state(self, pkg, pkg_in_repo):
        """Determines whether a package in a conda repo is
        older, equal to or newer than the pkgs called out in the pkg
        list file.
        Args:
            pkg(tuple): Pkg from pkg-list with (version, build)
            pkg_in_repo(list of tuples): Pkgs from repo filelist.
        Returns (int) -2, -1, 0 , 1 = pkg in PowerUp repo is no match,
            older, same, newer version
        """
        state = -2  # same version and build
        for ver, bld in pkg_in_repo:
            if pkg[0] == ver:
                if pkg[1] == bld:
                    state = 0
                    break
                else:
                    pkg_py_ver = re.search(r'py\d+', pkg[1])
                    pkg_in_repo_py_ver = re.search(r'py\d+', bld)
                    if pkg_py_ver and pkg_in_repo_py_ver:
                        if pkg_py_ver.group(0) == pkg_in_repo_py_ver.group(0):
                            if pkg[1] > bld:
                                state = -1
                            else:
                                state = 1
                            break
            elif pkg[0] > ver:
                state = -1
            elif pkg[0] < ver:
                state = 1

        return state

    def verify_pkgs(self, pkglist, noarch=False):
        if pkglist == 'all' or pkglist is None or not pkglist:
            # With no pkg list to assess, return all 0's(get_pkg_list can be used
            # for 'all')
            return 0, 0, 0, 0
        pkgs_vers = parse_conda_filenames(pkglist)

        pkg_lst_cnt = 0
        for item in pkgs_vers:
            pkg_lst_cnt += len(pkgs_vers[item]['ver_bld'])
        if noarch:
            repo_dir = os.path.join(self.anarepo_dir, 'noarch')
        else:
            repo_dir = os.path.join(self.anarepo_dir, f'linux-{self.arch}')

        filelist = os.listdir(repo_dir)
        filelist = [fi for fi in filelist if fi[-8:] == '.tar.bz2']
        files_vers = parse_conda_filenames(filelist)
        pkg_cnt = 0
        new_cnt = 0
        old_cnt = 0
        missing = []
        for _file in pkgs_vers:
            if _file in files_vers:
                for ver_bld in pkgs_vers[_file]['ver_bld']:
                    ver_state = self._get_conda_pkg_state(ver_bld, files_vers[_file]
                                                          ['ver_bld'])
                    if ver_state == -1:
                        self.log.debug(f'Older conda pkg: {_file}')
                        old_cnt += 1
                        pkg_cnt += 1
                    elif ver_state == 0:
                        pkg_cnt += 1
                    elif ver_state == 1:
                        new_cnt += 1
                        pkg_cnt += 1
                    else:
                        self.log.debug(f'Missing conda pkg: {_file}')
                        missing.append(_file)
            else:
                self.log.debug(f'Missing conda pkg: {_file}')
                missing.append(_file)
        if missing:
            self.log.info(f'Missing {self.repo_id} files: {missing}')

        return (pkg_lst_cnt, pkg_cnt, new_cnt, old_cnt)

    def get_pkg_list(self, path):
        """ Looks for the repodata.json file. If present, it is loaded and the
        package list is extracted and returned
        Args:
            path (str): url to the repodata
        Returns:
            list of packages. Full names, no path.
        """
        if os.path.isfile(path):
            with open(path, 'r') as f:
                repodata = f.read()
        else:
            return

        repodata = json.loads(repodata)
        pkgs = repodata['packages'].keys()
        return pkgs

    def _update_repodata(self, path):
        """ Update the repodata.json file to reflect the actual contents of the
        repodata directory.
            Args:
        path: (str) full path to the repodata directory.
        """
        status = True
        path = os.path.join(path, 'repodata.json')
        exists = glob.glob(path, recursive=True)
        if exists:
            repodata_path = exists[0]
            dir_name = os.path.dirname(repodata_path)
            file_list = glob.glob(os.path.join(dir_name, '*'))
            file_list = [f.rsplit('/', 1)[1] for f in file_list]
        else:
            self.log.error(f'Unable to find repodata for {self.repo_name}')

        with open(path, 'r') as f:
            repodata = f.read()

        repodata = json.loads(repodata)
        pkgs = {pkg: repodata['packages'][pkg] for pkg in
                repodata['packages'] if pkg in file_list}

        # Build the new dict from the original. Replace the value of the 'packages'
        # key in the new dict
        new_repodata = {}
        for item in repodata.keys():
            if item == 'packages':
                new_repodata[item] = pkgs
            else:
                new_repodata[item] = repodata[item]

        # write (replace) the repodata file
        with open(path, 'w') as f:
            json.dump(new_repodata, f, indent=2)

        return status

    def sync_ana(self, url, rejlist=None, acclist=None, noarch=False):
        """Syncs an Anaconda repository using wget or rsync.
        To download the entire repository, leave the accept list (acclist) and rejlist
        empty. Alternately, set the acclist to all or the rejlist to all to accept or
        reject the entire repo. Note that the accept list and reject list are mutually
        exclusive.
        inputs:
            acclist (str): Accept list. List of files to download. If specified,
                only the listed files will be downloaded.
            rejlist (str): Reject list. List of files to reject. If specified,
                the entire repository except the files in the rejlist will be downloaded.
        """
        def _get_table_row(file_handle):
            """read lines from file handle until end of table row </tr> found
            return:
                row: (str) with the balance of the table row.
                filename: (str) with the name of the file referenced in the row.
            """
            row = ''
            filename = ''
            while '</tr>' not in row and '</table>' not in row:
                line = file_handle.readline()
                name = re.search(r'href="(.*?)"', line)
                row += line
                if name:
                    filename = name.group(1)
            return row, filename

        if 'http:' in url or 'https:' in url:
            if noarch:
                dest_dir = os.path.join(self.anarepo_dir, 'noarch')
            else:
                dest_dir = os.path.join(self.anarepo_dir, f'linux-{self.arch}')
            self.log.info(f'Syncing {self.repo_name}')
            self.log.info('This can take several minutes\n')
            # Get the repodata.json files and html index files
            # -S = preserve time stamp.  -N = only if Newer or missing -P = download path
            for file in ('repodata.json', 'repodata2.json', 'repodata.json.bz2',
                         'index.html'):
                cmd = (f'wget -N -S -P {dest_dir} {url}{file}')
                res, err, rc = sub_proc_exec(cmd, shell=True)
                if rc != 0 and file == 'repodata.json':
                    self.log.error(f'Error downloading {file}.  rc: {rc} url:{url} '
                                   f'dest_dir:{dest_dir}\ncmd:{cmd}')
                err = err.splitlines()
                for line in err:
                    if '-- not retrieving' in line:
                        print(line, '\n')

            # Get the list of packages in the repo. Note that if both acclist
            # and rejlist are not provided the full set of packages is downloaded
            pkgs = self.get_pkg_list(os.path.join(dest_dir, 'repodata.json'))
            if pkgs is None:
                self.log.error('repodata.json file not found')
                return None

            download_set = set(pkgs)

            if acclist and acclist != 'all':
                download_set = download_set & set(acclist)
                missing = set(acclist) - download_set
                if missing:
                    self.log.warning('The following packages are not present at \n'
                                     f'{url}\n{missing}')
            elif rejlist:
                if rejlist == 'all':
                    download_set = ()
                else:
                    download_set = download_set - set(rejlist)

            # Get em
            for file in sorted(download_set):
                print(file)
                cmd = (f'wget -N -S -P {dest_dir} {url}{file}')
                res, err, rc = sub_proc_exec(cmd, shell=True)
                if rc != 0:
                    self.log.error(f'Error downloading {url}.  rc: {rc}')
                err = err.splitlines()
                for line in err:
                    if '-- not retrieving' in line:
                        print(line, '\n')
            self._update_repodata(dest_dir)

        elif 'file:///' in url:
            src_dir = url[7:]
            if noarch:
                dest_dir = os.path.join(self.anarepo_dir, 'noarch')
            else:
                dest_dir = os.path.join(self.anarepo_dir, f'linux-{self.arch}')

            if not os.path.isdir(dest_dir):
                os.makedirs(dest_dir)
            cmd = f'rsync -uaPv {src_dir} {dest_dir}'
            rc = sub_proc_display(cmd)
            if rc != 0:
                self.log.error('Sync of {self.repo_id} failed. rc: {rc}')
            else:
                self.log.info(f'{self.repo_name} sync finished successfully')

        self._update_repodata(dest_dir)

        # Filter content of index.html
        if '/pkgs' in dest_dir or '/ibmai' in dest_dir:
            filelist = os.listdir(dest_dir)
            filecnt = 0
            dest = os.path.join(dest_dir, 'index.html')
            src = os.path.join(dest_dir, 'index-src.html')
            os.rename(dest, src)
            line = ''
            with open(src, 'r') as s, open(dest, 'w') as d:
                # copy Table header info over to new index.html
                while '<tr>' not in line:
                    line = s.readline()
                    if '<table>' in line:
                        table_indent = line.find('<table>')
                    d.write(line)
                row = ''
                # Copy table rows till end of table found
                while '</table>' not in row:
                    row, filename = _get_table_row(s)
                    if filename in filelist or 'Filename' in row:
                        d.write(row)
                        if filename in filelist:
                            filecnt += 1
                    elif '</table>' in row:
                        row = '          '[0:table_indent] + '</table>\n'
                        d.write(row)
                while True:
                    line = s.readline()
                    if not line:
                        break
                    ts = re.search(r'Updated: (.+) - Files:', line)
                    if ts:
                        ts = ts.group(1).replace('+', '\\+')
                        line = re.sub(ts, time.asctime(), line)
                        dec = 1  # Assume repodata.json always present
                        dec = dec + 1 if 'repodata2.json' in filelist else dec
                        dec = dec + 1 if 'repodata.json.bz2' in filelist else dec
                        line = re.sub(r'Files:\s+\d+', f'Files: {filecnt-dec}', line)
                    d.write(line)
        else:
            # Remove index.html files retrieved from conda-forge so they don't
            # interfere with web browser viewing
            idx_path = os.path.join(dest_dir, 'index.html')
            if os.path.isfile(idx_path):
                os.remove(idx_path)
            idx_path = os.path.join(dest_dir[:dest_dir.find('conda-forge')],
                                    'index.html')
            if os.path.isfile(idx_path):
                os.remove(idx_path)
        return dest_dir


class PowerupPypiRepoFromRepo(PowerupRepo):
    """Sets up a Pypi (pip) repository for access by POWER-Up software clients.
    The repo is first sync'ed locally from the internet or a user specified
    URL which could reside on another host or from a local directory. (ie
    a file based URL pointing to a mounted disk. eg file:///mnt/my-mounted-usb)
    """
    def __init__(self, repo_id, repo_name, repo_base_dir, arch='ppc64le', rhel_ver='7'):
        super(PowerupPypiRepoFromRepo, self).__init__(repo_id, repo_name,
                                                      repo_base_dir, arch, rhel_ver)
        self.repo_type = 'pypi'
        self.pypirepo_dir = f'{self.repo_base_dir}repos/{self.repo_id}'

    def get_repo_dir(self):
        return self.pypirepo_dir

    def parse_pypi_pkg_list(self, pkg_list):
        """ Given a pkg list with items formatted as name[>=<]=version
        returns a list of tuples of (name, ver)
        Args:
            pkg_list(list) pkg==ver or pkg<=ver or pkg>=ver). Versions
            with alpha characters in the last place are truncated. eg
            3.2.3post2 is truncated to 3.2.3
        returns (list) of tuples of form (name, ver)
        """
        _pkg__list = []
        for item in pkg_list:
            ver = re.search(r'\d+(\.\d+)+', item)
            if ver:
                ver = ver.group(0)
            else:
                ver = ''
                self.log.error(f'Unable to resolve version in pkg list item {item}')
            name = re.search(r'(.+)[>=<]{2}', item)
            if name:
                name = name.group(1)
                _pkg__list.append((name, ver))
            else:
                self.log.error(f'Unable to resolve name in pkg list item {item}')

        return _pkg__list

    def get_pypi_pkg_state(self, pkg_in_repo, pkg):
        """Determines whether a package in a pypi simple repo is
        older, equal to or newer than the pkgs called out in the pkg
        list file.
        Args:
            pkg(tuple): Pkg from pkg-list with (version, build)
            pkg_in_repo(list of tuples): Pkgs from repo filelist.
        Returns (int) -2, -1, 0 , 1 = pkg in PowerUp repo is no match,
            older, same, newer version
        """
        state = -2  # same version and build
        ver_pkg_lst, _ = pkg
        for ver_repo, bld in pkg_in_repo:
            this_state = self.get_ver_state(ver_repo, ver_pkg_lst)
            if this_state == 0:
                state = this_state
                break
            elif this_state > state:
                state = this_state
        return state

    def verify_pkgs(self, pkglist):
        try:
            filenames = os.listdir(self.pypirepo_dir)
        except FileNotFoundError:
            filenames = []
        files_vers = parse_pypi_filenames(filenames)
        pkgs_vers = self.parse_pypi_pkg_list(pkglist)

        pkg_lst_cnt = len(pkgs_vers)

        pkg_cnt = 0
        new_cnt = 0
        old_cnt = 0
        missing = []
        for pkg in pkgs_vers:
            _file = pkg[0]
            # pypi filenames allow both dashes and underscores in filenames
            # and also have cases with dashes in package names but
            # underscores in filenames.
            fyle = ''
            if _file in files_vers:
                fyle = _file
            elif _file.replace('-', '_') in files_vers:
                fyle = _file.replace('-', '_')
            if fyle:
                ver_state = -2
                ver_state = self.get_pypi_pkg_state(files_vers[fyle]['ver_bld'],
                                                    (pkg[1], ''))

                if ver_state == -1:
                    self.log.debug(f'Older pypi file {pkg}')
                    old_cnt += 1
                    pkg_cnt += 1
                elif ver_state == 0:
                    pkg_cnt += 1
                elif ver_state == 1:
                    new_cnt += 1
                    pkg_cnt += 1
                else:
                    missing.append(_file)
            else:
                missing.append(_file)
        if missing:
            self.log.debug(f'Missing {self.repo_id} files: {missing}')

        return (pkg_lst_cnt, pkg_cnt, new_cnt, old_cnt)

    def sync(self, pkg_list, alt_url=None, py_ver=27):
        """
        inputs:
            pkg_list (str): list of packages separated by space(s). Packages can
                include versions. ie Keras==2.0.5
        """
        if not os.path.isdir(self.pypirepo_dir):
            os.mkdir(self.pypirepo_dir)
        pkg_cnt = len(pkg_list.split())
        print(f'Downloading {pkg_cnt} python{py_ver} packages plus dependencies:\n')

        pkg_list2 = pkg_list.split()
        if alt_url:
            host = re.search(r'http://([^/]+)', alt_url).group(1)
            cmd = host  # Dummy assign to silence tox
            # wait on 'f' string formatting since 'pkg' is not available yet
            cmd = ("f'python -m pip download --python-version {py_ver} "
                   "--platform {self.arch} --no-deps --index-url={alt_url} "
                   "-d {self.pypirepo_dir} {pkg} --trusted-host {host}'")
        else:
            cmd = ("f'python -m pip download --python-version {py_ver} "
                   "--platform {self.arch} --no-deps -d {self.pypirepo_dir} {pkg}'")
        for pkg in pkg_list2:
            print(pkg)
            resp, err, rc = sub_proc_exec(eval(cmd), shell=True)
            if rc != 0:
                err_str = '"python setup.py egg_info" failed with error code 1 in'
                if 'functools32' in resp or 'weave' in resp and err_str in err:
                    pass
                else:
                    self.log.error('Error occured while downloading python packages: '
                                   f'\nResp: {resp} \nRet code: {rc} \nerr: {err}')

        if not os.path.isdir(self.pypirepo_dir + '/simple'):
            os.mkdir(self.pypirepo_dir + '/simple')
        dir_list = os.listdir(self.pypirepo_dir)
        cnt = 0

        for item in dir_list:
            if item[0] != '.' and os.path.isfile(self.pypirepo_dir + '/' + item):
                res = re.search(r'([-_+\w\.]+)(?=-(\d+\.\d+){1,3}).+', item)
                if res:
                    cnt += 1
                    name = res.group(1)
                    name = name.replace('.', '-')
                    name = name.replace('_', '-')
                    name = name.lower()
                    if not os.path.isdir(self.pypirepo_dir + f'/simple/{name}'):
                        os.mkdir(self.pypirepo_dir + f'/simple/{name}')
                    if not os.path.islink(self.pypirepo_dir + f'/simple/{name}/{item}'):
                        os.symlink(self.pypirepo_dir + f'/{item}',
                                   self.pypirepo_dir + f'/simple/{name}/{item}')
                else:
                    self.log.error(f'mismatch: {item}. There was a problem entering '
                                   f'{item}\ninto the python package index')
        self.log.info(f'A total of {cnt} packages exist or were added to the python '
                      'package repository')
# dir2pi changes underscores to dashes in the links it creates which caused some
# packages to fail to install. In particular python_heatclient and other python
# openstack packages
#        cmd = f'dir2pi -N {self.pypirepo_dir}'
#        resp, err, rc = sub_proc_exec(cmd)
#        if rc != 0:
#            self.log.error('An error occured while creating python package index: \n'
#                           f'dir2pi utility results: \nResp: {resp} \nRet code: '
#                           f'{rc} \nerr: {err}')


class PowerupRepoFromDir(PowerupRepo):
    def __init__(self, repo_id, repo_name, repo_base_dir, arch='ppc64le',
                 proc_family='family', rhel_ver='7'):
        super(PowerupRepoFromDir, self).__init__(repo_id, repo_name, repo_base_dir,
                                                 arch, proc_family, rhel_ver)

    def copy_dirs(self, src_dir=None):
        if os.path.exists(self.yumrepo_dir):
            if get_yesno(f'Directory {self.yumrepo_dir} already exists.\n'
                         'OK to replace it? '):
                rmtree(os.path.dirname(self.yumrepo_dir), ignore_errors=True)
            else:
                self.log.info('Directory not created')
                return None, None

        src_dir = get_dir(src_dir)
        if not src_dir:
            return None, None

        try:
            dest_dir = self.yumrepo_dir
            copytree(src_dir, dest_dir)
        except Error as exc:
            print(f'Copy error: {exc}')
            return None, dest_dir
        else:
            return src_dir, dest_dir


# def create_repo_from_rpm_pkg(pkg_name, pkg_file, src_dir, dst_dir, web=None):
#        heading1(f'Setting up the {pkg_name} repository')
#        ver = ''
#        src_installed, src_path = setup_source_file(cuda_src, cuda_dir, 'PowerAI')
#        ver = re.search(r'\d+\.\d+\.\d+', src_path).group(0) if src_path else ''
#        self.log.debug(f'{pkg_name} source path: {src_path}')
#        cmd = f'rpm -ihv --test --ignorearch {src_path}'
#        resp1, err1, rc = sub_proc_exec(cmd)
#        cmd = f'diff /opt/DL/repo/rpms/repodata/ /srv/repos/DL-{ver}/repo/rpms/repodata/'
#        resp2, err2, rc = sub_proc_exec(cmd)
#        if 'is already installed' in err1 and resp2 == '' and rc == 0:
#            repo_installed = True
#        else:
#            repo_installed = False
#
#        # Create the repo and copy it to /srv directory
#        if src_path:
#            if not ver:
#                self.log.error('Unable to find the version in {src_path}')
#                ver = rlinput('Enter a version to use (x.y.z): ', '5.1.0')
#            ver0 = ver.split('.')[0]
#            ver2 = ver.split('.')[2]
#            # First check if already installed
#            if repo_installed:
#                print(f'\nRepository for {src_path} already exists')
#                print('in the POWER-Up software server.\n')
#                r = get_yesno('Do you wish to recreate the repository')
#
#            if not repo_installed or r == 'yes':
#                cmd = f'rpm -ihv  --force --ignorearch {src_path}'
#                rc = sub_proc_display(cmd)
#                if rc != 0:
#                    self.log.info('Failed creating PowerAI repository')
#                    self.log.info(f'Failing cmd: {cmd}')
#                else:
#                    shutil.rmtree(f'/srv/repos/DL-{ver}', ignore_errors=True)
#                    try:
#                        shutil.copytree('/opt/DL', f'/srv/repos/DL-{ver}')
#                    except shutil.Error as exc:
#                        print(f'Copy error: {exc}')
#                    else:
#                        self.log.info('Successfully created PowerAI repository')
#        else:
#            if src_installed:
#                self.log.debug('PowerAI source file already in place and no '
#                               'update requested')
#            else:
#                self.log.error('PowerAI base was not installed.')
#
#        if ver:
#            dot_repo = {}
#            dot_repo['filename'] = f'powerai-{ver}.repo'
#            dot_repo['content'] = (f'[powerai-{ver}]\n'
#                                   f'name=PowerAI-{ver}-powerup\n'
#                                   'baseurl=http://{host}}/repos/'
#                                   f'DL-{ver}/repo/rpms\n'
#                                   'enabled=1\n'
#                                   'gpgkey=http://{host}/repos/'
#                                   f'DL-{ver}/repo/mldl-public-key.asc\n'
#                                   'gpgcheck=0\n')
#            if dot_repo not in self.sw_vars['yum_powerup_repo_files']:
#                self.sw_vars['yum_powerup_repo_files'].append(dot_repo)


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
