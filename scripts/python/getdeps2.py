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

import getpass
import glob
import sys
import os
import yaml

import lib.logger as logger
import lib.genesis as gen
from lib.utilities import get_selection, sub_proc_exec


def main():
    log = logger.getlogger()
    log.debug('log this')
    dep_base_path = gen.get_dependencies_path()
    dirs = [d for d in os.listdir(dep_base_path) if
            os.path.isdir(os.path.join(dep_base_path, d))]
    dirs = [os.path.join(dep_base_path, _dir) for _dir in dirs]
    ch, dep_dir = get_selection(dirs, prompt='Select a directory to aggregate '
                                'dependencies from: ')

    dep_files = {}

    pip_pre_files = ['client_pip_pre_install.txt',
                     'dlipy3_pip_pre_install.txt',
                     'dlipy2_pip_pre_install.txt',
                     'dlinsights_pip_pre_install.txt',
                     ]
    dep_files['pip_pre_files'] = pip_pre_files

    pip_post_files = ['client_pip_post_install.txt',
                      'dlipy3_pip_post_install.txt',
                      'dlipy2_pip_post_install.txt',
                      'dlinsights_pip_post_install.txt',
                      ]
    dep_files['pip_post_files'] = pip_post_files

    conda_pre_files = ['dlipy3_conda_pre_install.txt',
                       'dlipy2_conda_pre_install.txt',
                       'dlinsights_conda_pre_install.txt',
                       ]
    dep_files['conda_pre_files'] = conda_pre_files

    conda_post_files = ['dlipy3_conda_post_install.txt',
                        'dlipy2_conda_post_install.txt',
                        'dlinsights_conda_post_install.txt',
                        ]
    dep_files['conda_post_files'] = conda_post_files

    yum_pre_files = ['client_yum_pre_install.txt']
    dep_files['yum_pre_files'] = yum_pre_files

    yum_post_files = ['client_yum_post_install.txt']
    dep_files['yum_post_files'] = yum_post_files

    exists = glob.glob(f'{dep_dir}/**/{yum_pre_files[0]}', recursive=True)
    if exists:
        dep_dir = os.path.dirname(exists[0])
    else:
        log.error('No client yum pre file found')
        sys.exit()

    # Change file ownership to current user
    username = getpass.getuser()
    cmd = f'sudo chown -R {username}:{username} {dep_dir}'
    sub_proc_exec(cmd, shell=True)

    # Clear comments and other known header content from files
    for item in dep_files:
        for _file in dep_files[item]:
            _file_path = os.path.join(dep_dir, _file)
            with open(_file_path, 'r') as f:
                lines = f.read().splitlines()
            with open(_file_path, 'w') as f:
                for line in lines:
                    if line.startswith('#') or line.startswith('@'):
                        continue
                    else:
                        f.write(line + '\n')

    def file_check(file_list):
        for f in file_list:
            file_path = os.path.join(dep_dir, f)
            my_file = os.path.isfile(file_path)
            print(file_path)
            if my_file:
                pass
            else:
                input(f'\nINFO - {f} Does not exist\n')

    def get_pkg_repo(pkg, pkg_type):
        if pkg_type == 'yum':
            pkg_items = pkg.split()
            repo = pkg_items[2]
            if repo.endswith('-powerup'):
                repo = repo[:-8]

        elif pkg_type == 'pip':
            pkg_items = pkg.split()
            repo = pkg_items[2]
            if pkg_type in repo:
                repo = 'pypi'

        elif pkg_type == 'conda':
            pkg_dir = pkg.rpartition('/')[0]
            if 'ibm-ai' in pkg or 'ibmai' in pkg:
                if 'linux-ppc64le' in pkg:
                    repo = 'ibmai_linux_ppc64le'
                elif 'noarch' in pkg:
                    repo = 'ibmai_noarch'
                else:
                    repo = 'ibmai_unresolved_reponame'
            elif 'repo.anaconda' in pkg:
                repo = '-'.join(pkg_dir.rsplit('/', 2)[-2:])
                repo = 'anaconda_' + repo.replace('-', '_')
            else:
                pkg_dir = pkg.rpartition('/')[0]
                repo = '_'.join(pkg_dir.rsplit('/', 2)[-2:])
        return repo

    def format_pkg_name(pkg, pkg_type):
        if pkg_type == 'yum':
            pkg_items = pkg.split()
            pkg_repo = get_pkg_repo(pkg, pkg_type)
            pkg_fmt_name = (pkg_items[0].rsplit('.', 1)[0] + '-' +
                            pkg_items[1] + '.' + pkg_items[0].rsplit('.', 1)[1])

        elif pkg_type == 'conda':
            pkg_fmt_name = pkg.rpartition('/')[-1]
            pkg_repo = get_pkg_repo(pkg, pkg_type)

        elif pkg_type == 'pip':
            pkg_items = pkg.split()
            pkg_repo = get_pkg_repo(pkg, pkg_type)
            version = pkg_items[1].replace('(', '')
            version = version.replace(')', '')
            pkg_fmt_name = pkg_items[0] + '==' + version

        return pkg_fmt_name, pkg_repo

    def write_merged_files(merged_sets, pkg_type):
        if pkg_type == 'yum':
            for repo in merged_sets:
                file_name = repo.replace('/', '')
                file_name = file_name.replace('@', '')
                file_name = f'{file_name}.yml'
                file_path = os.path.join(dep_dir, file_name)
                with open(file_path, 'w') as f:
                    d = {file_name: sorted(merged_sets[repo], key=str.lower)}
                    yaml.dump(d, f, indent=4, default_flow_style=False)

        elif pkg_type == 'conda':
            for repo in merged_sets:
                file_name = f'{repo}.yml'
                file_path = os.path.join(dep_dir, file_name)
                with open(file_path, 'w') as f:
                    d = {file_name: sorted(list(merged_sets[repo]), key=str.lower)}
                    yaml.dump(d, f, indent=4, default_flow_style=False)

        elif pkg_type == 'pip':
            for repo in merged_sets:
                file_name = 'pypi.yml'
                file_path = os.path.join(dep_dir, file_name)
                with open(file_path, 'w') as f:
                    d = {file_name: sorted(merged_sets[repo], key=str.lower)}
                    yaml.dump(d, f, indent=4, default_flow_style=False)

    def get_repo_list(pkgs, pkg_type):
        repo_list = []
        if pkg_type == 'yum':
            for pkg in pkgs:
                repo = get_pkg_repo(pkg, pkg_type)
                if repo not in repo_list:
                    repo_list.append(repo)

        if pkg_type == 'conda':
            for pkg in pkgs:
                repo = get_pkg_repo(pkg, pkg_type)

                if repo not in repo_list:
                    repo_list.append(repo)

        if pkg_type == 'pip':
            for pkg in pkgs:
                if '<pip>' in pkg:
                    repo = get_pkg_repo(pkg, pkg_type)
                    if repo not in repo_list:
                        repo_list.append(repo)

        return repo_list

    def merge_function(pre_files, post_files, pkg_type):
        """ Merges packages of a given type listed in a collection of files
        collected 'post' installation and 'pre' installation for various
        environments.
        The merged set of 'pre' packages is removed from the merge set of
        'post' packages to arrive at the list of installed packages across
        all environments.
        """

        # generate pre paths
        pre_paths = []
        for file in pre_files:
            pre_paths.append(os.path.join(dep_dir, file))

        # Generate post paths
        post_paths = []
        for file in post_files:
            post_paths.append(os.path.join(dep_dir, file))

        # Loop through the files
        pkgs = {}  # # {file:{repo:{pre:[], post: []}
        for i, pre_file in enumerate(pre_paths):
            file_name = os.path.basename(pre_file)
            file_key = file_name.split('_')[0] + '_' + file_name.split('_')[1]
            pkgs[file_key] = {}
            post_file = post_paths[i]
            try:
                with open(pre_file, 'r') as f:
                    pre_pkgs = f.read().splitlines()
            except FileNotFoundError as exc:
                print(f'File not found: {pre_file}. Err: {exc}')

            try:
                with open(post_file, 'r') as f:
                    post_pkgs = f.read().splitlines()
            except FileNotFoundError as exc:
                print(f'File not found: {post_file}. Err: {exc}')

            # Get the repo list
            repo_list = get_repo_list(post_pkgs, pkg_type)
            for repo in repo_list:
                pkgs[file_key][repo] = {}
                pkgs[file_key][repo]['pre'] = []
                pkgs[file_key][repo]['post'] = []
                for pkg in pre_pkgs:
                    pkg_fmt_name, pkg_repo = format_pkg_name(pkg, pkg_type)
                    if pkg_repo == repo:
                        pkgs[file_key][repo]['pre'].append(pkg_fmt_name)

                for pkg in post_pkgs:
                    # Format the name
                    pkg_fmt_name, pkg_repo = format_pkg_name(pkg, pkg_type)
                    if pkg_repo == repo:
                        pkgs[file_key][repo]['post'].append(pkg_fmt_name)

        diff_sets = {}

        # Post - pre pkg sets. (may need adjustment for different repo type)
        for _file in pkgs:
            diff_sets[_file] = {}
            for repo in pkgs[_file]:
                post_minus_pre = set(pkgs[_file][repo]['post'])  # -
                # set(pkgs[_file][repo]['pre']))
                diff_sets[_file][repo] = post_minus_pre

        # Merge by repository
        merged_sets = {}

        for _file in diff_sets:
            for repo in diff_sets[_file]:
                if repo not in merged_sets:
                    merged_sets[repo] = set()
                merged_sets[repo] = merged_sets[repo] | diff_sets[_file][repo]

        write_merged_files(merged_sets, pkg_type)

    file_check(yum_pre_files)
    file_check(yum_post_files)
    merge_function(yum_pre_files, yum_post_files, 'yum')
    file_check(conda_pre_files)
    file_check(conda_post_files)
    merge_function(conda_pre_files, conda_post_files, 'conda')
    file_check(pip_pre_files)
    file_check(pip_post_files)
    merge_function(pip_pre_files, pip_post_files, 'pip')


if __name__ == '__main__':
    """Simple python template
    """

    logger.create('nolog', 'info')
    log = logger.getlogger()

    main()
    print("\nINFO - Process Completed\n")
