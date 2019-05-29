#!/usr/bin/env python3
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

import argparse
from os import makedirs, listdir, path
from shutil import rmtree
from platform import machine

import lib.logger as logger
from lib.genesis import get_python_requirements_path, \
    get_yum_requirements_path, get_yum_depends_path, get_github_url
from lib.utilities import load_package_list_from_file, sub_proc_exec, \
    get_yesno, rlinput
from nginx_setup import setup_nginx_yum_repo
import repos


def create_pip_install_repo(repo_base_dir, arch='ppc64le', py_ver=36):
    """ Download Python packages into local repository formatted for
    air-gapped pip installs.

    Args:
        repo_base_dir (str): Base directory path
        arch (str, optional): Select package architecture to save
        py_ver (int, optional): Python version number
    """
    repo_name = 'pup_install_pip'
    repo_id = repo_name

    pipRepo = repos.PowerupPypiRepoFromRepo(repo_id,
                                            repo_name,
                                            repo_base_dir,
                                            arch=arch)

    makedirs(pipRepo.get_repo_dir(), exist_ok=True)

    pipRepo.sync(load_package_list_from_file(get_python_requirements_path()),
                 py_ver=36)


def create_yum_install_repo(repo_base_dir, arch='ppc64le', rhel_ver='7'):
    """ Download RHEL packages into local repository formatted for
    air-gapped um installs.

    Args:
        repo_base_dir (str): Base directory path
        arch (str, optional): Select package architecture to save
        rhel_ver (str, optional): RHEL major version number
    """
    setup_nginx_yum_repo()

    repo_name = 'pup_install_yum'
    repo_id = repo_name

    # TODO: is 'proc_famaily' kwarg needed here? scripts/python/repos.py:549
    yumRepo = repos.PowerupYumRepoFromRepoList(repo_id,
                                               repo_name,
                                               repo_base_dir,
                                               arch=arch,
                                               rhel_ver=rhel_ver)

    makedirs(yumRepo.get_repo_dir(), exist_ok=True)

    yumRepo.sync(load_package_list_from_file(get_yum_requirements_path()))
    yumRepo.sync(load_package_list_from_file(get_yum_depends_path()))
    yumRepo.create_meta()


def create_pup_repo_mirror(repo_base_dir):
    """ Download POWER-Up public repository in full

    Args:
        repo_base_dir (str): Base directory path
        arch (str, optional): Select package architecture to save
        py_ver (int, optional): Python version number
    """
    log = logger.getlogger()

    if not repo_base_dir.endswith('.git'):
        repo_base_dir = path.join(repo_base_dir, 'power-up.git')

    makedirs(repo_base_dir, exist_ok=True)

    if len(listdir(repo_base_dir)) != 0:
        log.info(f"The directory '{repo_base_dir}' already exists and is not"
                 " empty.")
        if get_yesno("Permanently remove existing contents and re-clone? "):
            rmtree(repo_base_dir)
            makedirs(repo_base_dir, exist_ok=True)
        else:
            log.debug("User selected to continue without re-cloning")
            return

    url_path = rlinput("POWER-Up Repository path/URL: ", get_github_url())

    resp, err, rc = sub_proc_exec(f'git clone --mirror {url_path} '
                                  f'{repo_base_dir}')
    if rc != 0:
        log.error('An error occurred while cloning mirror of power-up repo: '
                  f'{err}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('--repo-base-dir', '-r', dest='repo_base_dir',
                        help='Repository base directory', default='/srv/pup/')

    parser.add_argument('--arch', '-a', dest='arch',
                        help='Package architecture', default=None)

    parser.add_argument('--rhel-version', '-v', dest='rhel_ver',
                        help='RHEL major version', default='7')

    parser.add_argument('--print', '-p', dest='log_lvl_print',
                        help='print log level', default='info')

    parser.add_argument('--file', '-f', dest='log_lvl_file',
                        help='file log level', default='info')

    args = parser.parse_args()

    if args.log_lvl_print == 'debug':
        print(args)

    logger.create(args.log_lvl_print, args.log_lvl_file)

    if args.arch is None:
        arch = machine()

    create_pip_install_repo(args.repo_base_dir, arch=args.arch)
    create_yum_install_repo(args.repo_base_dir, arch=args.arch,
                            rhel_ver=args.rhel_ver)
    create_pup_repo_mirror(args.repo_base_dir)
