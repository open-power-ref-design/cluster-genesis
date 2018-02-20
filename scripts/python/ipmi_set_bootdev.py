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
import time
from subprocess import Popen, PIPE
from pyghmi.ipmi import command as ipmi_command
from pyghmi import exceptions as pyghmi_exception

from lib.inventory import Inventory
import lib.logger as logger
from lib.exception import UserException


def _sub_proc_exec(cmd):
    data = Popen(cmd.split(), stdout=PIPE, stderr=PIPE)
    stdout, stderr = data.communicate()
    return stdout, stderr


def ipmi_set_bootdev(bootdev, persist=False, client_list=None):
    log = logger.getlogger()
    inv = Inventory()

    if type(persist) is not bool:
        persist = (persist == 'True')

    # if client list passed, then use the passed client list,
    # otherwise use the entire inventory list. This allows a
    # subset of nodes to have their bootdev updated during install
    if not client_list:
        client_list = inv.get_nodes_pxe_ipaddr(0)

    for index, hostname in enumerate(inv.yield_nodes_hostname()):
        rack_id = inv.get_nodes_rack_id(index)
        ipv4 = inv.get_nodes_ipmi_ipaddr(0, index)
        ipv4_pxe = inv.get_nodes_pxe_ipaddr(0, index)
        userid = inv.get_nodes_ipmi_userid(index)
        password = inv.get_nodes_ipmi_password(index)
        ipmi_cmd = ipmi_command.Command(
            bmc=ipv4,
            userid=userid,
            password=password)

        if ipv4_pxe in client_list:
            try:
                status = ipmi_cmd.set_bootdev(bootdev, persist)
            except pyghmi_exception.IpmiException as error:
                msg = (
                    'set_bootdev failed (device=%s persist=%s), retrying once - '
                    'Rack: %s - IP: %s, %s' %
                    (bootdev, persist, rack_id, ipv4, str(error)))
                log.warning(msg)
                del ipmi_cmd
                ipmi_cmd = ipmi_command.Command(
                    bmc=ipv4,
                    userid=userid,
                    password=password)
                try:
                    status = ipmi_cmd.set_bootdev(bootdev, persist)
                except pyghmi_exception.IpmiException as error:
                    msg = (
                        'set_bootdev failed (device=%s persist=%s) - '
                        'Rack: %s - IP: %s, %s' %
                        (bootdev, persist, rack_id, ipv4, str(error)))
                    log.error(msg)
                    raise UserException(msg)

            if 'error' in status:
                msg = (
                    'set_bootdev failed (device=%s persist=%s) - '
                    'Rack: %s - IP: %s, %s' %
                    (bootdev, persist, rack_id, ipv4, str(status['error'])))
                log.error(msg)
                raise UserException(msg)

            time.sleep(5)

            try:
                status = ipmi_cmd.get_bootdev()
            except pyghmi_exception.IpmiException as error:
                msg = (
                    'get_bootdev failed - '
                    'Rack: %s - IP: %s, %s' %
                    (rack_id, ipv4, str(error)))
                log.error(msg)
                raise UserException(msg)

            if 'error' in status:
                msg = (
                    'get_bootdev failed - '
                    'Rack: %s - IP: %s, %s' %
                    (rack_id, ipv4, str(status['error'])))
                log.error(msg)
                raise UserException(msg)
            elif (status['bootdev'] == bootdev and
                  str(status['persistent']) == str(persist)):
                log.debug(
                    'set_bootdev successful (device=%s persist=%s) - '
                    'Rack: %s - IP: %s' %
                    (bootdev, persist, rack_id, ipv4))
            else:
                msg = (
                    'set_bootdev failed - set: (device=%s persist=%s) '
                    'but read: (device=%s persist=%s) - '
                    'Rack: %s - IP: %s' %
                    (bootdev, persist, status['bootdev'], status['persistent'],
                     rack_id, ipv4))
                log.error(msg)
                raise UserException(msg)


if __name__ == '__main__':
    """
    Arg1: boot device
    Arg2: persistence (boolean)
    Arg3: client list (specify None to use the entire client list)
    """
    logger.create()
    LOG = logger.getlogger()

    if len(sys.argv) != 4:
        try:
            raise Exception()
        except:
            LOG.error('Invalid argument count')
            sys.exit(1)

    BOOTDEV = sys.argv[1]
    PERSIST = sys.argv[2]
    CLIENT_LIST = sys.argv[3]

    ipmi_set_bootdev(BOOTDEV, PERSIST, CLIENT_LIST)
