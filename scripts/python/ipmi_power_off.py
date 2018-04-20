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

from lib.inventory import Inventory
from lib.ipmi_power import IpmiPower
import lib.logger as logger
from lib.exception import UserException


def ipmi_power_off(time_out, wait):
    inv = Inventory()
    log = logger.getlogger()
    ipmi_power = IpmiPower()

    bmcs = []
    for index, hostname in enumerate(inv.yield_nodes_hostname()):
        bmc = {}
        bmc['rack_id'] = inv.get_nodes_rack_id(index)
        bmc['ipv4'] = inv.get_nodes_ipmi_ipaddr(0, index)
        bmc['userid'] = inv.get_nodes_ipmi_userid(index)
        bmc['password'] = inv.get_nodes_ipmi_password(index)

        _rc, _ = ipmi_power.is_power_off(bmc)
        if _rc:
            log.info(
                'Already powered off - Rack: %s - IP: %s' %
                (bmc['rack_id'], bmc['ipv4']))
        else:
            bmcs.append(bmc)
            ipmi_power.set_power_off(bmc)

    start_time = time.time()
    attempt = 1
    while bmcs:
        if time.time() > start_time + time_out:
            break
        time.sleep(wait)
        bmcs[:] = [
            bmc
            for bmc in bmcs
            if _is_not_power_off(ipmi_power, bmc, attempt) is not None]
        attempt += 1

    for bmc in bmcs:
        msg = ('Power off unsuccessful - Rack: %s - IP: %s - State: %s' %
               (bmc['rack_id'], bmc['ipv4'], bmc['power_state']))
        log.error(msg)
        raise UserException(msg)


def _is_not_power_off(ipmi_power, bmc, attempt):
    log = logger.getlogger()
    _rc, power_state = ipmi_power.is_power_off(bmc)
    if _rc:
        log.info(
            'Power off successful - Rack: %s - IP: %s' %
            (bmc['rack_id'], bmc['ipv4']))
        return None
    bmc['power_state'] = power_state
    log.debug(
        'Power off pending - Rack: %s - IP: %s - State: %s - Attempt: %s' %
        (bmc['rack_id'], bmc['ipv4'], bmc['power_state'], attempt))
    return bmc


if __name__ == '__main__':
    """
    Arg1: time out
    Arg2: wait time
    """
    logger.create()
    LOG = logger.getlogger()

    if len(sys.argv) != 3:
        try:
            raise Exception()
        except Exception:
            LOG.error('Invalid argument count')
            sys.exit(1)

    TIME_OUT = int(sys.argv[1])
    WAIT = int(sys.argv[2])

    ipmi_power_off(TIME_OUT, WAIT)
