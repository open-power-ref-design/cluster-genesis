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

import os
import sys
import yaml
import json

import lib.logger as logger
from lib.genesis import GEN_SOFTWARE_PATH
from lib.utilities import sub_proc_display, sub_proc_exec


def main(name):
    """ Opens a yaml file in the power-up/software directory and reads the
    content which should contain a dictionary with a key of 'yum_pkgs'
    Input:
        name: (str) yaml file name
    Output: yaml file with the 'plus-deps' added to the name of the input file.
        The file contains a list with the original list plus it's first level
        dependencies.
    """
    log = logger.getlogger()
    path = os.path.join(GEN_SOFTWARE_PATH, name)
    if not name.endswith('.yml'):
        self.log.error('file must be of type yaml ending in ".yml"')
        sys.exit('Exit due to critical error')
    try:
        packages = yaml.load(open(path))
    except IOError:
        self.log.error(f'Error opening the pkg lists file {path}')
        sys.exit('Exit due to critical error')
    pkg_list = packages['yum_pkgs']

    pkg_list_str = ' '.join(pkg_list)
    # To generate the complete dependency list add --recursive
    cmd = ('repoquery  --archlist=ppc64le,noarch --requires --resolve '
           f'--recursive --pkgnarrow=all {pkg_list_str}')
    resp, err, rc = sub_proc_exec(cmd)
    pkgs = list(set(resp.splitlines()))
    pkgs = pkg_list + pkgs
    packages['yum_pkgs'] = pkgs

    try:
        with open(GEN_SOFTWARE_PATH + name.rstrip('.yml') + '-plus-deps.yml', 'w') as f:
            yaml.dump(packages, f, default_flow_style=False)
    except IOError:
        self.log.error(f'Error opening the pkg lists file {path}')
        sys.exit('Exit due to critical error')


if __name__ == '__main__':
    """Show status of the Cluster Genesis environment
    Args:
        INV_FILE (string): Inventory file.
        LOG_LEVEL (string): Log level.

    Raises:
       Exception: If parameter count is invalid.
    """

    logger.create('nolog', 'info')
    log = logger.getlogger()
    ARGV_MAX = 2
    ARGV_COUNT = len(sys.argv)
    if ARGV_COUNT > ARGV_MAX:
        try:
            raise Exception()
        except:
            log.error('Invalid argument count')
            sys.exit('Invalid argument count')
    name = sys.argv[1]

    main(name)
