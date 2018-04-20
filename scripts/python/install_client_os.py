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

import re
import sys
from subprocess import Popen, PIPE
from time import sleep

from cobbler_set_netboot_enabled import cobbler_set_netboot_enabled
from ipmi_power_off import ipmi_power_off
from ipmi_set_bootdev import ipmi_set_bootdev
from ipmi_power_on import ipmi_power_on
from lib.config import Config
from lib.inventory import Inventory
import lib.logger as logger
import lib.genesis as gen

POWER_TIME_OUT = gen.get_power_time_out()
POWER_WAIT = gen.get_power_wait()
IS_CONTAINER = gen.is_container()


def _sub_proc_exec(cmd):
    data = Popen(cmd.split(), stdout=PIPE, stderr=PIPE)
    stdout, stderr = data.communicate()
    return stdout, stderr


def _get_lists(latest_list, handled_list):
    """Keeps track of clients which have had their bootdev reset to 'default'
    inputs:
        latest_list: (list) List of ip addresses from the latest cobbler status
    returns: those client ip addreses that are newly found in new_list, and the
        cumulative list of those clients which have been handled in handled_list
    """
    new_list = []
    for item in latest_list:
        if item in handled_list:
            pass
        else:
            handled_list.append(item)
            new_list.append(item)
    return new_list, handled_list


def install_client_os():
    log = logger.getlogger()
    cobbler_set_netboot_enabled(True)
    ipmi_power_off(POWER_TIME_OUT, POWER_WAIT)
    ipmi_set_bootdev('network', False)
    ipmi_power_on(POWER_TIME_OUT, POWER_WAIT)
    cfg = Config()
    inv = Inventory()

    client_list = inv.get_nodes_ipmi_ipaddr(0)
    client_cnt = len(client_list)

    for vlan in cfg.yield_depl_netw_client_vlan('pxe'):
        break
    cont_name = '{}-pxe{}'.format(gen.DEFAULT_CONTAINER_NAME, vlan)
    if IS_CONTAINER:
        cmd = 'cobbler status'
    else:
        cmd = 'lxc-attach -n {} cobbler status'.format(cont_name)

    cnt = 60
    handled_list = []
    log.info('Waiting for installation to begin.  Polling on 10 sec intervals')
    while cnt > 0:
        stdout, stderr = _sub_proc_exec(cmd)
        latest_list = re.findall(r'(?:\d{1,3}\.){3}\d{1,3}.+installing', stdout)
        latest_list = re.findall(r'(?:\d{1,3}\.){3}\d{1,3}', ''.join(latest_list))
        new_list, handled_list = _get_lists(latest_list, handled_list)
        installing_cnt = len(handled_list)
        print('Nodes installing: {} of {}. Remaining polls: {}{}'.
              format(installing_cnt, client_cnt, cnt, gen.Color.up_one))
        sys.stdout.flush()
        if new_list:
            ipmi_set_bootdev('default', True, new_list)
        else:
            sleep(10)
        if installing_cnt == client_cnt:
            break
        cnt -= 1
    print('\n')
    log.info(stdout)
    msg = ('\nNot all cluster nodes have started installation.  Genesis is\n'
           'continuing with the installation. Clients that have not begun\n'
           'installing after an extended period of time have likely \n'
           'encountered a problem.  You may be able to interact with each\n'
           'clients installer via IPMI SOL console to resolve the problem\n'
           'manually.\n')
    if installing_cnt != client_cnt:
        log.info('\n{}{}{}'.format(gen.Color.red, msg, gen.Color.endc))


if __name__ == '__main__':
    logger.create()
    install_client_os()
