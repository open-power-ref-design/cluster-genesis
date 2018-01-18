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

from time import sleep

from cobbler_set_netboot_enabled import cobbler_set_netboot_enabled
from ipmi_power_off import ipmi_power_off
from ipmi_set_bootdev import ipmi_set_bootdev
from ipmi_power_on import ipmi_power_on
import lib.logger as logger
import lib.genesis as gen

POWER_TIME_OUT = gen.get_power_time_out()
POWER_WAIT = gen.get_power_wait()
SLEEP_TIME = gen.get_power_sleep_time()


def install_client_os():
    log = logger.getlogger()
    cobbler_set_netboot_enabled(True)
    ipmi_power_off(POWER_TIME_OUT, POWER_WAIT)
    ipmi_set_bootdev('network', False)
    ipmi_power_on(POWER_TIME_OUT, POWER_WAIT)
    log.info('Sleeping for %d seconds...' % SLEEP_TIME)
    sleep(SLEEP_TIME)
    ipmi_set_bootdev('default', True)


if __name__ == '__main__':
    logger.create()
    install_client_os()
