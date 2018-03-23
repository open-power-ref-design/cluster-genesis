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

import sys
from subprocess import Popen, PIPE

from lib.config import Config
from lib.exception import UserException
from lib.genesis import DEFAULT_CONTAINER_NAME
import lib.logger as logger


def _sub_proc_exec(cmd):
    data = Popen(cmd.split(), stdout=PIPE, stderr=PIPE)
    stdout, stderr = data.communicate()
    return stdout, stderr


def teardown_deployer_container():
    """Teardown the Cluster Genesis container on the deployer.
    This function is idempotent.
    """
    log = logger.getlogger()
    try:
        cfg = Config()
    except UserException:
        log.error('Unable to open Cluster Genesis config.yml file')
        sys.exit(1)

    for vlan in cfg.yield_depl_netw_client_vlan('pxe'):
        break
    name = '{}-pxe{}'.format(DEFAULT_CONTAINER_NAME, vlan)
    container_list, stderr = _sub_proc_exec('lxc-ls')
    log.info('Found containers: {}'.format(container_list))
    if name not in container_list:
        log.info('container name: {} does not exist.'.format(name))
    else:
        log.info('Destroying container: {}'.format(name))
        result, stderr = _sub_proc_exec('lxc-stop -n {}'.format(name))
        result, stderr = _sub_proc_exec('lxc-destroy -s -n {}'.format(name))


if __name__ == '__main__':
    logger.create('nolog', 'info')
    teardown_deployer_container()
