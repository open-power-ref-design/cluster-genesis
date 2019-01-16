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

import sys
import xmlrpc.client

import lib.logger as logger
import lib.genesis as gen

COBBLER_USER = gen.get_cobbler_user()
COBBLER_PASS = gen.get_cobbler_pass()


def cobbler_set_netboot_enabled(netboot_enabled_value):
    log = logger.getlogger()
    cobbler_server = xmlrpc.client.Server("http://127.0.0.1/cobbler_api")
    token = cobbler_server.login(COBBLER_USER, COBBLER_PASS)

    for system in cobbler_server.get_systems():
        name = system['name']

        handle = cobbler_server.get_system_handle(name, token)
        cobbler_server.modify_system(
            handle, "netboot_enabled", netboot_enabled_value, token)
        cobbler_server.save_system(handle, token)

        log.debug(
            "Cobbler Modify System: name=%s netboot_enabled=%s" %
            (name, netboot_enabled_value))


if __name__ == '__main__':
    """
    Arg1: netboot_enabled value
    """
    logger.create()
    LOG = logger.getlogger()

    if len(sys.argv) != 2:
        try:
            raise Exception()
        except:
            LOG.error('Invalid argument count')
            sys.exit(1)

    NETBOOT_ENABLED_VALUE = sys.argv[1]

    cobbler_set_netboot_enabled(NETBOOT_ENABLED_VALUE)
