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
import os
from shutil import move
from shutil import Error as shutil_Error
from glob import glob

import lib.logger as logger
from lib.utilities import sub_proc_exec, get_selection, get_yesno


def create_base_dir(base_dir):
    log = logger.getlogger()
    print('\nMove or Copy the existing software server directories?')
    ch, action = get_selection('move\ncopy', ('m', 'c'))
    if action == 'copy':
        statvfs = os.statvfs(base_dir)
        freespace = statvfs.f_frsize * statvfs.f_bavail
        if freespace < 18000000000:
            sys.exit('Insufficient space on disk')
    arch = ''
    exists = glob('/srv/repos/dependencies/rhel7/*')
    if not exists:
        log.error('\nNo dependencies folder found. Unable to perform move.\n')
        sys.exit()
    for path in exists:
        if 'p8' in path or 'p9' in path:
            arch = 'ppc64le'
            break
        elif 'x86_64' in path:
            arch = 'x86_64'
            break
    if not arch:
        log.error('\nUnable to determine architecture. Unable to perform move.\n')
        sys.exit()
    if os.path.exists(f'{base_dir}/wmla120-{arch}'):
        print(f'Destination path {base_dir}/wmla120-{arch} already exists.')
        if action == 'copy':
            if not get_yesno('Okay to proceed with force copy? '):
                sys.exit('Exit at user request')
    else:
        os.mkdir(f'{base_dir}/wmla120-{arch}/')
    for _dir in (('repos', 'anaconda', 'spectrum-conductor', 'spectrum-dli',
                  'wmla-license',)):
        path = os.path.join('/srv/', _dir, '')

        if os.path.isdir(path):
            print(f'Found dir: {path}')
            if action == 'move':
                try:
                    move(path, f'{base_dir}/wmla120-{arch}/')
                except shutil_Error as exc:
                    print(exc)
            elif action == 'copy':
                cmd = f'cp -rf {path} {base_dir}/wmla120-{arch}/'
                try:
                    _, err, rc = sub_proc_exec(cmd)
                except:
                    pass
                if rc != 0:
                    log.error('Copy error {err}')
        else:
            log.error(f'Path {path} missing')
    print('Done')


if __name__ == '__main__':
    """Simple python template
    """

    create_base_dir()
