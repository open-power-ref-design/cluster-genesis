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

import argparse
import sys
import os
import platform
from distro import linux_distribution

import lib.logger as logger
from lib.utilities import sub_proc_exec, nginx_modify_conf, line_in_file
from repos import PowerupRepo


def setup_nginx_yum_repo(root_dir='/srv', repo_id='nginx'):
    """Install and setup nginx http server

    Args:
        root_dir (str): Path to root directory for requests
        repo_id (str): Name of nginx yum repository

    Returns:
        int: Return code from 'yum makecache'
    """

    log = logger.getlogger()

    baseurl = 'http://nginx.org/packages/rhel/7/' + platform.machine()
    repo_file = os.path.join('/etc/yum.repos.d', repo_id + '.repo')

    if os.path.isfile(repo_file):
        with open(repo_file, 'r') as f:
            content = f.read()
        if baseurl in content:
            rc = 0
        else:
            line_in_file(repo_file, r'^baseurl=.+', f'baseurl={baseurl}')
            for cmd in ['yum clean all', 'yum makecache']:
                resp, err, rc = sub_proc_exec(cmd)
                if rc != 0:
                    log.error(f"A problem occured while running '{cmd}'")
                    log.error(f'Response: {resp}\nError: {err}\nRC: {rc}')
    else:
        repo_name = 'nginx.org public'
        repo = PowerupRepo(repo_id, repo_name, root_dir)
        content = repo.get_yum_dotrepo_content(baseurl, gpgcheck=0)
        repo.write_yum_dot_repo_file(content)
        cmd = 'yum makecache'
        resp, err, rc = sub_proc_exec(cmd)
        if rc != 0:
            log.error('A problem occured while creating the yum '
                      'caches')
            log.error(f'Response: {resp}\nError: {err}\nRC: {rc}')

    return rc


def nginx_setup(root_dir='/srv', repo_id='nginx'):
    """Install and setup nginx http server

    Args:
        root_dir (str): Path to root directory for requests
        repo_id (str): Name of nginx yum repository

    Returns:
        int: Return code from 'systemctl restart nginx.service'
    """

    log = logger.getlogger()

    # Check if nginx installed. Install if necessary.
    cmd = 'nginx -v'
    try:
        resp, err, rc = sub_proc_exec(cmd)
    except OSError:
        if 'rhel' in linux_distribution(full_distribution_name=False):
            cmd = 'yum -y install nginx'
            resp, err, rc = sub_proc_exec(cmd)
            if rc != 0:
                setup_nginx_yum_repo(root_dir, repo_id)
                cmd = 'yum -y install nginx'
                resp, err, rc = sub_proc_exec(cmd)
                if rc != 0:
                    log.error('Failed installing nginx')
                    log.error(resp)
                    sys.exit(1)
        elif 'ubuntu' in linux_distribution(full_distribution_name=False):
            for cmd in ['apt-get update', 'apt-get install -y nginx']:
                resp, err, rc = sub_proc_exec(cmd)
                if rc != 0:
                    log.error(f"A problem occured while running '{cmd}'")
                    log.error(f'Response: {resp}\nError: {err}\nRC: {rc}')

    cmd = 'systemctl enable nginx.service'
    resp, err, rc = sub_proc_exec(cmd)
    if rc != 0:
        log.error('Failed to enable nginx service')

    cmd = 'systemctl start nginx.service'
    resp, err, rc = sub_proc_exec(cmd)
    if rc != 0:
        log.error('Failed to start nginx service')

    if os.path.isfile('/etc/nginx/conf.d/default.conf'):
        try:
            os.rename('/etc/nginx/conf.d/default.conf',
                      '/etc/nginx/conf.d/default.conf.bak')
        except OSError:
            log.warning('Failed renaming /etc/nginx/conf.d/default.conf')

    nginx_location = {'/': [f'root {root_dir}', 'autoindex on']}
    nginx_directives = {'listen': '80', 'server_name': 'powerup'}

    rc = nginx_modify_conf('/etc/nginx/conf.d/server1.conf',
                           directives=nginx_directives,
                           locations=nginx_location)

    return rc


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('--print', '-p', dest='log_lvl_print',
                        help='print log level', default='info')

    parser.add_argument('--file', '-f', dest='log_lvl_file',
                        help='file log level', default='info')

    args = parser.parse_args()

    if args.log_lvl_print == 'debug':
        print(args)

    logger.create(args.log_lvl_print, args.log_lvl_file)

    nginx_setup()
