#!/usr/bin/env python3
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

import sys
import xmlrpc.client

from lib.logger import Logger
import lib.genesis as gen

COBBLER_USER = gen.get_cobbler_user()
COBBLER_PASS = gen.get_cobbler_pass()

COBBLER_NAME = 'default'
COBBLER_PROFILE = 'introspection'


class CobblerAddIntrospection(object):
    def __init__(self, log):
        cobbler_server = xmlrpc.client.Server("http://127.0.0.1/cobbler_api")
        token = cobbler_server.login(COBBLER_USER, COBBLER_PASS)

        new_system_create = cobbler_server.new_system(token)

        cobbler_server.modify_system(
            new_system_create,
            "name",
            COBBLER_NAME,
            token)
        cobbler_server.modify_system(
            new_system_create,
            "profile",
            COBBLER_PROFILE,
            token)

        cobbler_server.save_system(new_system_create, token)

        log.info(
            "Cobbler Add System: name=%s, profile=%s" %
            (COBBLER_NAME, COBBLER_PROFILE))

        cobbler_server.sync(token)
        log.info("Running Cobbler sync")


if __name__ == '__main__':
    """
    Arg1: log level
    """
    LOG = Logger(__file__)

    if len(sys.argv) != 2:
        try:
            raise Exception()
        except:
            LOG.error('Invalid argument count')
            sys.exit(1)

    LOG.set_level(sys.argv[1])

    CobblerAddIntrospection(LOG)
