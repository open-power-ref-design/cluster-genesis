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

import sys
import os.path
# import code
import yaml

import lib.logger as logger
import lib.genesis as gen


def main():
    log = logger.getlogger()
    log.debug('log this')
    dep_path = gen.get_dependencies_path()

    pip_pre_files = ['client_pip_pre_install.txt',
                     'dlipy3_pip_pre_install.txt',
                     'dlipy2_pip_pre_install.txt',
                     'dlinsights_pip_pre_install.txt',
                     ]

    pip_post_files = ['client_pip_post_install.txt',
                      'dlipy3_pip_post_install.txt',
                      'dlipy2_pip_post_install.txt',
                      'dlinsights_pip_post_install.txt',
                      ]

    conda_pre_files = ['dlipy3_conda_pre_install.txt',
                       'dlipy2_conda_pre_install.txt',
                       'dlinsights_conda_pre_install.txt',
                       ]

    conda_post_files = ['dlipy3_conda_post_install.txt',
                        'dlipy2_conda_post_install.txt',
                        'dlinsights_conda_post_install.txt',
                        ]

    yum_pre_files = ['client_yum_pre_install.txt']

    yum_post_files = ['client_yum_post_install.txt']

    def file_check(pre_files):
        for f in pre_files:
            pre_file_path = os.path.join(dep_path, f)
            my_file = os.path.isfile(pre_file_path)
            if my_file:
                pass
            else:
                menu = True
                while menu:
                    opt = input(f'INFO - Would you like to recover "{f}" ?\n 1 - Yes \n 2 - No \n')
                    if opt == '1':
                        print(f'\nINFO - Located new pre path for "{f}"\n')
                        menu = False
                    elif opt == '2':
                        menu = False
                        sys.exit()
                    else:
                        print('\nPlese select a valid option')

    def format_pkg_name(pkg, pkg_type):
        if pkg_type == 'yum':
            pkg_items = pkg.split()
            pkg_repo = pkg.split()[2]
            pkg_fmt_name = (pkg_items[0].rsplit('.', 1)[0] + '-' +
                            pkg_items[1] + '.' + pkg_items[0].rsplit('.', 1)[1])

        elif pkg_type == 'conda':
            pkg_fmt_name = pkg.rpartition('/')[-1]
            if '/linux-ppc64le' in pkg:
                pkg_repo = pkg[:pkg.find('/linux-ppc64le')]
            elif '/linux-64' in pkg:
                pkg_repo = pkg[:pkg.find('/linux-64')]
            elif '/noarch' in pkg:
                pkg_repo = pkg[:pkg.find('/noarch')]
            elif 'file://' in pkg:
                pkg_repo = '/file'
            pkg_repo = pkg_repo.rpartition('/')[-1]

        elif pkg_type == 'pip':
            pkg_items = pkg.split()
            pkg_repo = 'pip'
            version = pkg_items[1].replace('(', '')
            version = version.replace(')', '')
            pkg_fmt_name = pkg_items[0] + '=' + version

        return pkg_fmt_name, pkg_repo

    def write_merged_files(merged_sets, pkg_type):
        if pkg_type == 'yum':
            for repo in merged_sets:
                file_name = repo.replace('/', '')
                file_name = file_name.replace('@', '')
                file_name = f'{pkg_type}-{file_name}.yml'
                file_path = os.path.join(dep_path, file_name)
                with open(file_path, 'w') as f:
                    d = {file_name: sorted(merged_sets[repo])}
                    yaml.dump(d, f, indent=4, default_flow_style=False)

        elif pkg_type == 'conda':
            for repo in merged_sets:
                file_name = f'{pkg_type}-{repo}.yml'
                file_path = os.path.join(dep_path, file_name)
                with open(file_path, 'w') as f:
                    d = {file_name: sorted(list(merged_sets[repo]))}
                    yaml.dump(d, f, indent=4, default_flow_style=False)

        elif pkg_type == 'pip':
            for repo in merged_sets:
                file_name = f'{pkg_type}.yml'
                file_path = os.path.join(dep_path, file_name)
                with open(file_path, 'w') as f:
                    d = {file_name: sorted(merged_sets[repo])}
                    yaml.dump(d, f, indent=4, default_flow_style=False)

    def get_repo_list(pkgs, pkg_type):
        repo_list = []
        if pkg_type == 'yum':
            for pkg in pkgs:
                pkg_items = pkg.split()
                repo = pkg_items[2]
                if repo not in repo_list:
                    repo_list.append(repo)

        if pkg_type == 'conda':
            for pkg in pkgs:
                if '/linux-ppc64le' in pkg:
                    repo = pkg[:pkg.find('/linux-ppc64le')]
                elif '/linux-64' in pkg:
                    repo = pkg[:pkg.find('/linux-64')]
                else:
                    repo = pkg[:pkg.find('/noarch')]
                repo = repo.rpartition('/')[-1]

                if repo not in repo_list:
                    repo_list.append(repo)

        if pkg_type == 'pip':
            for pkg in pkgs:
                # pkg_items = pkg.split()
                repo = 'pip'
                if repo not in repo_list:
                    repo_list.append(repo)

        return repo_list

    def merge_function(pre_files, post_files, pkg_type):

        # generate pre paths
        pre_paths = []
        for file in pre_files:
            pre_paths.append(os.path.join(dep_path, file))

        # Generate post paths
        post_paths = []
        for file in post_files:
            post_paths.append(os.path.join(dep_path, file))

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

    file_check(pip_pre_files)
    file_check(pip_post_files)
    merge_function(yum_pre_files, yum_post_files, 'yum')
    merge_function(conda_pre_files, conda_post_files, 'conda')
    merge_function(pip_pre_files, pip_post_files, 'pip')


if __name__ == '__main__':
    """Simple python template
    """

    logger.create('nolog', 'info')
    log = logger.getlogger()

    main()
    print("\nINFO - Process Completed\n")
