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
from shutil import copy2, copytree, rmtree, Error
import time

import lib.logger as logger
from lib.utilities import sub_proc_display, sub_proc_exec, get_url, \
    get_dir, get_yesno, get_selection, get_file_path, get_src_path, bold
from lib.exception import UserException


def setup_source_file(name, src_glob, url='', alt_url='http://',
                      dest_dir=None, src2=None):
    """Interactive selection of a source file and copy it to the /srv/<dest_dir>
    directory. The source file can include file globs and can come from a URL
    or the local disk. Local disk searching starts in the /home and /root
    directory and then expands to the entire file system if no matches
    found in those directories. URLs must point to the directory with the file
    or a parent directory.
    Inputs:
        src_glob (str): Source file name to look for. Can include file globs
        src2(str): An additional file to be copied from the same source as src_glob.
            This file would typically be a support file such as an entitlement file.
        dest (str) : destination directory. Will be created if necessary under
            /srv/
        url (str): url for the public web site where the file can be obtained.
            leave empty to prevent prompting for a public url option.
        alt_url (str): Alternate url where the file can be found. Usually this
            is an intranet web site.
        name (str): Name for the source. Used for prompts and dest dir (/srv/{name}).
    Returns:
        state (bool) : state is True if a file matching the src_name exists
            in the dest directory or was succesfully copied there. state is
            False if there is no file matching src_name in the dest directory
            OR if the attempt to copy a new file to the dest directory failed.
        src_path (str) : The path for the file found / chosen by the user. If
            only a single match is found it is used without choice and returned.
        dest_path (str)
    """
    src_path = None
    dest_path = None
    log = logger.getlogger()
    name_src = get_name_dir(name)
    exists = glob.glob(f'/srv/{name_src}/**/{src_glob}', recursive=True)
    if exists:
        dest_path = exists[0]
    copied = False
    ch = ''
    while not copied:
        ch, item = get_selection('Copy from URL\nSearch local Disk', 'U\nD',
                                 allow_none=True)

        if ch == 'U':
            _url = alt_url if alt_url else 'http://'
            if url:
                ch1, item = get_selection('Public web site.Alternate web site', 'P.A',
                                          'Select source: ', '.')
                if ch1 == 'P':
                    _url = url
            rc = -9
            while _url is not None and rc != 0:
                _url = get_url(_url, fileglob=src_glob)
                if _url:
                    dest_dir = f'/srv/{name_src}'
                    if not os.path.exists(dest_dir):
                        os.mkdir(dest_dir)
                    cmd = f'wget -r -l 1 -nH -np --cut-dirs=1 -P {dest_dir} {_url}'
                    rc = sub_proc_display(cmd)
                    if rc != 0:
                        log.error(f'Failed downloading {name} source to'
                                  f' /srv/{name_src}/ directory. \n{rc}')
                        copied = False
                    else:
                        src_path = _url
                        dest_path = os.path.join(dest_dir, os.path.basename(_url))
                        copied = True
                    if src2:
                        _url2 = os.path.join(os.path.dirname(_url), src2)
                        cmd = f'wget -r -l 1 -nH -np --cut-dirs=1 -P {dest_dir} {_url2}'
                        rc = sub_proc_display(cmd)
                        if rc != 0:
                            log.error(f'Failed downloading {name} source file {src2} to'
                                      f' /srv/{name_src}/ directory. \n{rc}')
                            copied = False
                        else:
                            src_path = _url
                            copied = copied and True
        elif ch == 'D':
            src_path = get_src_path(src_glob)
            if src_path:
                dest_dir = f'/srv/{name_src}'
                if not os.path.exists(dest_dir):
                    os.mkdir(dest_dir)
                try:
                    copy2(src_path, dest_dir)
                except Error as err:
                    log.debug(f'Failed copying {name} source file to /srv/{name_src}/ '
                              f'directory. \n{err}')
                    copied = False
                else:
                    log.info(f'Successfully installed {name} source file '
                             'into the POWER-Up software server.')
                    dest_path = os.path.join(dest_dir, os.path.basename(src_path))
                    copied = True
                if src2:
                    try:
                        src2_path = os.path.join(os.path.dirname(src_path), src2)
                        copy2(src2_path, dest_dir)
                    except Error as err:
                        log.debug(f'Failed copying {name} source file to /srv/{name_src}/ '
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


def powerup_file_from_disk(name, file_glob):
    log = logger.getlogger()
    name_src = get_name_dir(name)
    dest_path = None
    src_path = get_src_path(file_glob)
    if src_path:
        if not os.path.exists(f'/srv/{name_src}'):
            os.mkdir(f'/srv/{name_src}')
        try:
            copy2(src_path, f'/srv/{name_src}/')
        except Error as err:
            log.debug(f'Failed copying {name} source file to /srv/{name_src}/ '
                      f'directory. \n{err}')
        else:
            log.info(f'Successfully installed {name} source file '
                     'into the POWER-Up software server.')
            dest_path = os.path.join(f'/srv/{name_src}/',
                                     os.path.basename(src_path))
    return src_path, dest_path


class PowerupRepo(object):
    """Base class for creating a yum repository for access by POWER-Up software
     clients.
    """
    def __init__(self, repo_id, repo_name, arch='ppc64le', proc_family='family',
                 rhel_ver='7'):
        self.repo_id = repo_id
        self.repo_name = repo_name
        self.arch = arch
        self.proc_family = proc_family
        self.repo_type = 'yum'
        self.rhel_ver = str(rhel_ver)
        self.repo_base_dir = '/srv'
        if self.repo_id in ('dependencies', 'rhel-common', 'rhel-optional',
                            'rhel-supplemental', 'rhel-extras'):
            self.repo_dir = (f'/srv/repos/{self.repo_id}/rhel{self.rhel_ver}/'
                             f'{self.proc_family}/{self.repo_id}')
        else:
            self.repo_dir = (f'/srv/repos/{self.repo_id}/rhel{self.rhel_ver}/'
                             f'{self.repo_id}')
        self.anarepo_dir = f'/srv/repos/{self.repo_id}'
        self.pypirepo_dir = f'/srv/repos/{self.repo_id}'
        self.log = logger.getlogger()

    def get_repo_dir(self):
        return self.repo_dir

    def get_repo_base_dir(self):
        return self.repo_base_dir

    def get_action(self, exists, exists_prompt_yn=False):
        if exists:
            print(f'\nDo you want to sync the local {self.repo_name}\nrepository'
                  ' at this time?\n')
            print('This can take a few minutes.\n')
            ch = 'Y' if get_yesno(prompt='Sync Repo? ', yesno='Y/n') else 'n'
        else:
            print(f'\nDo you want to create a local {self.repo_name}\n repository'
                  ' at this time?\n')
            print('This can take a significant amount of time')
            ch = 'Y' if get_yesno(prompt='Create Repo? ', yesno='Y/n') else 'n'
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
            sel_txt = 'Alternate web site'
            sel_chcs = 'A'
        _url = None
        while _url is None:
            ch, item = get_selection(sel_txt, sel_chcs,
                                     'Choice: ', '.', allow_none=True)
            if ch == 'P':
                _url = url
                break
            if ch == 'A':
                if not alt_url:
                    alt_url = f'http://host/repos/{self.repo_id}/'
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
        copy2(src_path, dst_dir)

    def copytree_to_srv(self, src_dir, dst):
        """Copy a directory recursively to the POWER-Up server base directory.
        Note that if the directory exists already under the /srv durectory, it
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
        mutually exclusive. If repo_dir is not included, self.repo_dir is used as the
        baseurl for client and local .repo content.
        """
        self.log.debug(f'Creating yum ". repo" file for {self.repo_name}')
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
                            if os.path.exists(f'{self.repo_dir}/repodata'):
                                self.log.info(f'Removing existing repodata for '
                                              f'{self.repo_id}')
                                rmtree(f'{self.repo_dir}/repodata')
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
            cmd = f'createrepo -v {self.repo_dir}'
        else:
            cmd = f'createrepo -v --update {self.repo_dir}'
        resp, err, rc = sub_proc_exec(cmd)
        if rc != 0:
            self.log.error(f'Repo creation error: rc: {rc} stderr: {err}')
        else:
            self.log.info(f'Repo {action[0]} process for {self.repo_id} finished'
                          ' succesfully')


class PowerupRepoFromRpm(PowerupRepo):
    """Sets up a yum repository for access by POWER-Up software clients.
    The repo is created from an rpm file selected interactively by the user.
    """
    def __init__(self, repo_id, repo_name, arch='ppc64le', proc_family='family',
                 rhel_ver='7'):
        super(PowerupRepoFromRpm, self).__init__(repo_id, repo_name, arch,
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
        dst_dir = f'/srv/{self.repo_id}'
        if not os.path.exists(dst_dir):
            os.mkdir(dst_dir)
        copy2(self.rpm_path, dst_dir)
        dest_path = os.path.join(dst_dir, os.path.basename(src_path))
        print(dest_path)
        return dest_path

    def extract_rpm(self, src_path):
        """Extracts files from the selected rpm file to a repository directory
        under /srv/repoid/rhel7/repoid. If a repodata directory is included in
        the extracted data, then the path to repodata directory is returned
        Inputs: Uses self.repo_dir and self.repo_id
        Outputs:
            repodata_dir : absolute path to repodata directory if one exists
        """
        extract_dir = self.repo_dir
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
            self.repo_dir = os.path.dirname(repodata_dir[0])
            return self.repo_dir
        else:
            return None


class PowerupYumRepoFromRepo(PowerupRepo):
    """Sets up a yum repository for access by POWER-Up software clients.
    The repo is first sync'ed locally from the internet or a user specified
    URL which could reside on another host or from a local directory. (ie
    a file based URL pointing to a mounted disk. eg file:///mnt/my-mounted-usb)
    """
    def __init__(self, repo_id, repo_name, arch='ppc64le', proc_family='family',
                 rhel_ver='7'):
        super(PowerupYumRepoFromRepo, self).__init__(repo_id, repo_name, arch,
                                                     proc_family, rhel_ver)

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
    def __init__(self, repo_id, repo_name, arch='ppc64le', rhel_ver='7'):
        super(PowerupAnaRepoFromRepo, self).__init__(repo_id, repo_name, arch, rhel_ver)
        self.repo_type = 'ana'

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

    def sync_ana(self, url, rejlist=None, acclist=None):
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
            if '/pkgs/' in url:
                dest_dir = f'/srv/repos/{self.repo_id}' + url[url.find('/pkgs/'):]
            elif '/conda-forge' in url:
                dest_dir = f'/srv/repos/{self.repo_id}' + url[url.find('/conda-forge'):]
            elif self.repo_id == 'ibmai':
                dest_dir = os.path.join(f'/srv/repos/{self.repo_id}',
                                        url.rsplit('/', 2)[1])
            self.log.info(f'Syncing {self.repo_name}')
            self.log.info('This can take several minutes\n')

            # Get the repodata.json files and html index files
            # -S = preserve time stamp.  -N = only if Newer or missing -P = download path
            for file in ('repodata.json', 'repodata2.json', 'repodata.json.bz2',
                         'index.html'):
                cmd = (f'wget -N -S -P {dest_dir} {url}{file}')
                res, err, rc = sub_proc_exec(cmd, shell=True)
                if rc != 0 and file == 'repodata.json':
                    self.log.error(f'Error downloading {file}.  rc: {rc} url:{url} dest_dir:{dest_dir}\ncmd:{cmd}')
                err = err.splitlines()
                for line in err:
                    if '-- not retrieving' in line:
                        print(line, '\n')

            # Get the list of packages in the repo. Note that if both acclist
            # and rejlist are not provided the full set of packages is downloaded
            pkgs = self.get_pkg_list(os.path.join(dest_dir, 'repodata.json'))
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
            if '/pkgs/' in url:
                dest_dir = self.anarepo_dir + url[url.find('/pkgs/'):]
            elif self.anarepo_dir in url:
                dest_dir = url[url.find(self.anarepo_dir):]
            else:
                dest_dir = self.anarepo_dir + url
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
        if '/pkgs' in dest_dir:
            filelist = os.listdir(dest_dir)
            filecnt = 0
            dest = dest_dir + 'index.html'
            src = dest_dir + 'index-src.html'
            os.rename(dest, src)
            line = ''
            with open(src, 'r') as s, open(dest, 'w') as d:
                while '<tr>' not in line:
                    line = s.readline()
                    d.write(line)
                d.write(line)
                row = ''
                while '</table>' not in row:
                    row, filename = _get_table_row(s)
                    if filename in filelist or 'Filename' in row:
                        d.write(row)
                        filecnt += 1
                d.write(row)
                while True:
                    line = s.readline()
                    if not line:
                        break
                    ts = re.search(r'Updated: (.+) - Files:', line)
                    if ts:
                        ts = ts.group(1).replace('+', '\\+')
                        line = re.sub(ts, time.asctime(), line)
                    line = re.sub(r'Files:\s+\d+', f'Files: {filecnt-2}', line)
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
    def __init__(self, repo_id, repo_name, arch='ppc64le', rhel_ver='7'):
        super(PowerupPypiRepoFromRepo, self).__init__(repo_id, repo_name, arch, rhel_ver)
        self.repo_type = 'pypi'

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
                if 'functools32' in resp and 'for Python 2.7 only' in resp:
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
    def __init__(self, repo_id, repo_name, arch='ppc64le', proc_family='family',
                 rhel_ver='7'):
        super(PowerupRepoFromDir, self).__init__(repo_id, repo_name, arch,
                                                 proc_family, rhel_ver)

    def copy_dirs(self, src_dir=None):
        if os.path.exists(self.repo_dir):
            if get_yesno(f'Directory {self.repo_dir} already exists.\nOK to replace it? '):
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
#            ver1 = ver.split('.')[1]
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
