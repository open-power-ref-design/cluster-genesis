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
import argparse
import lib.logger as logger
import lib.genesis as gen
from lib.genesis import GEN_SOFTWARE_PATH
from lib.utilities import get_selection, sub_proc_exec, backup_file
if gen.GEN_SOFTWARE_PATH not in sys.path:
    sys.path.append(gen.GEN_SOFTWARE_PATH)
from yamlvault import YAMLVault
DEF_PKGS = ["ntp", "nfs-utils", "wget"]
#  RC_SUCCESS = 0
#  RC_ERROR = 99  # generic failure
RC_ARGS = 2  # failed to parse args given
PKG_LIST_TEMPLATE = '''
ibmai_linux{0}:
    accept_list: all
    reject_list: null
ibmai_noarch:
    accept_list:
    reject_list:
anaconda_free_linux{0}:
  accept_list:
  reject_list:
anaconda_free_noarch:
  accept_list:
  reject_list: all
anaconda_main_linux{0}:
  accept_list:
  reject_list:
anaconda_main_noarch:
  accept_list:
  reject_list:
pypi_3:
    - deprecation==2.0.5
    - docutils>=0.10
    - enum34==1.1.6
    - futures==3.1.1
pypi_2:
epel{2}:
dependencies{1}:
- wget
- ntp
- nfs-utils
cuda:
'''
PKG_SHORT = "pkg-lists"
SOFT_FILE = "software-vars.yml"

yaml.FullLoader.add_constructor(YAMLVault.yaml_tag,
                                YAMLVault.from_yaml)


def load_from_template(arch, proc_family):
    return yaml.safe_load(PKG_LIST_TEMPLATE.format(arch, proc_family, arch.replace("_", "-")))


def load_yamlfile(yamlfile):
    log = logger.getlogger()
    try:
        yaml_file = yaml.full_load(open(yamlfile, 'r'))
    except yaml.YAMLError as e:
        log.error("unable to open file: {0}\n error: {1}".format(yamlfile, e))
        raise e
    return yaml_file


def parse_input(args):
    parser = argparse.ArgumentParser(description="Utility for getting dependent packages")
    parser.add_argument('-f', '--first', action='store_true',
                        help='Set the first directory to parse', required=True)
    parser.add_argument('-s', '--software', type=str,
                        help='Set the software directory', required=True)
    if not args:
        parser.print_help()
        sys.exit(RC_ARGS)
    args = parser.parse_args(args)
    return args


def get_arch(repo_list):
    for key, val in repo_list.items():
        for i in val:
            for k, v in i["hash"].items():
                if "ppc64le" in k:
                    return "ppc64le"
                elif "x86_64" in k:
                    return "x86_64"


def parse_pkg_list(repo_list, software_type, proc_family=""):
    arch = get_arch(repo_list)
    fromTemplate = True
    try:
        a = "_" + arch if arch == "x86_64" else ""
        file_path = GEN_SOFTWARE_PATH + get_file_name(software_type, a)
        lists = load_yamlfile(file_path)
        fromTemplate = False
        print(yaml.dump(lists, indent=4, default_flow_style=False))
    except:
        input(f"Error loading pkg list file {file_path}.")
    for key, val in repo_list.items():
        #  load the file
        for i in val:
            for k, v in i["hash"].items():
                key_string = os.path.splitext(k)[0].replace("-powerup", "")
                if "epel" in key_string.lower():
                    lists[key_string] = v
                    for i in DEF_PKGS:
                        if i not in lists[key_string]:
                            lists[key_string].append(i)
                elif "cuda" in key_string:
                    lists[key_string] = v
                elif "anaconda_" in key_string or "ibmai" in key_string:
                    lists[key_string] = {}
                    lists[key_string]['accept_list'] = v
                    lists[key_string]['reject_list'] = None
                elif "pypi" in key_string:
                    lists["pypi"] = v
                    if "pypi_3" not in lists:
                        lists["pypi_3"] = ["deprecation==2.0.5", "docutils>=0.10", "enum34==1.1.6",
                                           '"futures>=2.2.0,<4.0.0"', "os_service_types==1.2.0"]
                elif "anaconda" in key_string or "install" in key_string:
                    continue
                else:
                    if "ppc64le" == arch:
                        key_string = f"dependencies{proc_family}"
                    elif "x86_64" == arch:
                        key_string = f"dependencies_{arch}"
                    else:
                        key_string = "dependencies"
                    print(key_string)
                    if not fromTemplate:
                        print(key_string)
                        lists[key_string] = []
                        fromTemplate = True
                    if key_string not in lists:
                        lists[key_string] = []
                    for _v in v:
                        lists[key_string].append(_v)
                print(key_string)

    return lists, arch


def generate_pkg_list(repo_list, software_type, arch, dep_dir):
    log = logger.getlogger()
    log.debug('log this')
    if software_type is None:
        software_type = ""
        file_name = get_file_name(software_type, arch)
        file_path = dep_dir + "/" + file_name
    else:
        file_path = GEN_SOFTWARE_PATH + get_file_name(software_type, arch)
        if os.path.exists(file_path):
            log.warn("File exists: " + file_path)
            log.info(f"Making backup to {file_path}.orig.n")
            backup_file(file_path)

    with open(file_path, 'w') as f:
        yaml.dump(repo_list, f, indent=4, default_flow_style=False)
    log.info("Wrote to file :" + file_path)

    return


def get_file_name(software_type, arch):
    arch = "_" + arch if arch == "x86_64" else ""
    software_type = "" if software_type == "" else "-" + software_type
    return PKG_SHORT + software_type + arch + ".yml"


def main(args):
    log = logger.getlogger()
    log.debug('log this')
    user_input = len(args) > 0
    if user_input:
        args = parse_input(args)

    dep_base_path = gen.get_dependencies_path()
    dirs = [d for d in os.listdir(dep_base_path) if
            os.path.isdir(os.path.join(dep_base_path, d))]
    dirs = [os.path.join(dep_base_path, _dir) for _dir in dirs]
    dep_dir = ""
    if user_input:
        dep_dir = dirs[0]

    if not user_input:
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

    #  # Change file ownership to current user
    # if not os.access(dep_dir, os.W_OK):
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
                elif 'x86_64' in pkg:
                    repo = 'ibmai_linux_x86_64'
                else:
                    repo = 'ibm_ai_unresolved_reponame'
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
        repo_list = {
        }
        if pkg_type == 'yum':
            repo_list[pkg_type] = []
            for repo in merged_sets:
                file_name = repo.replace('/', '')
                file_name = file_name.replace('@', '')
                file_name = f'{file_name}.yml'
                file_path = os.path.join(dep_dir, file_name)
                with open(file_path, 'w') as f:
                    d = {file_name: sorted(merged_sets[repo], key=str.lower)}
                    repo_list[pkg_type].append({"path": file_path, "filename": file_name, "hash": d})
                    yaml.dump(d, f, indent=4, default_flow_style=False)

        elif pkg_type == 'conda':
            repo_list[pkg_type] = []
            for repo in merged_sets:
                file_name = f'{repo}.yml'
                file_path = os.path.join(dep_dir, file_name)
                with open(file_path, 'w') as f:
                    d = {file_name: sorted(list(merged_sets[repo]), key=str.lower)}
                    repo_list[pkg_type].append({"path": file_path, "filename": file_name, "hash": d})
                    yaml.dump(d, f, indent=4, default_flow_style=False)

        elif pkg_type == 'pip':
            repo_list[pkg_type] = []
            for repo in merged_sets:
                file_name = 'pypi.yml'
                file_path = os.path.join(dep_dir, file_name)
                with open(file_path, 'w') as f:
                    d = {file_name: sorted(merged_sets[repo], key=str.lower)}
                    repo_list[pkg_type].append({"path": file_path, "filename": file_name, "hash": d})
                    yaml.dump(d, f, indent=4, default_flow_style=False)

        return repo_list

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

        return write_merged_files(merged_sets, pkg_type)

    file_check(yum_pre_files)
    file_check(yum_post_files)
    main_repo_list = merge_function(yum_pre_files, yum_post_files, 'yum')
    file_check(conda_pre_files)
    file_check(conda_post_files)
    conda_repo_list = merge_function(conda_pre_files, conda_post_files, 'conda')
    merge_dicts(conda_repo_list, main_repo_list)
    file_check(pip_pre_files)
    file_check(pip_post_files)
    pip_repo_list = merge_function(pip_pre_files, pip_post_files, 'pip')
    merge_dicts(pip_repo_list, main_repo_list)
    software_type = args.software if user_input else None
    proc_family = ""
    if software_type:
        try:
            file_path = GEN_SOFTWARE_PATH + SOFT_FILE
            yaml_file = load_yamlfile(file_path)
            proc_family = "_" + yaml_file["proc_family"]
        except:
            proc_family = ""
            pass
    lists, arch = parse_pkg_list(main_repo_list, software_type, proc_family)
    generate_pkg_list(lists, software_type, arch, dep_dir)


def merge_dicts(dict1, dict2):
    return (dict2.update(dict1))


if __name__ == '__main__':
    """Simple python template
    """

    logger.create('nolog', 'info')
    log = logger.getlogger()

    main(sys.argv[1:])
    print("\nINFO - Process Completed\n")
