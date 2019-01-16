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

from pyghmi import exceptions as pyghmi_exception
from pyghmi.ipmi import command
from pyghmi.ipmi.private import session
from enum import Enum

import lib.logger as logger


def login(host, username, pw, timeout=None):
    """
         Logs into the BMC and creates a session
    Args:
         host: (str), the hostname or IP address of the bmc to log into
         username: (str) The user name for the bmc to log into
         pw: (str) The password for the BMC to log into
         timeout (None) : Does nothing. Provides compatibility with open_bmc args
         return: Session object
    """
    log = logger.getlogger()

    if timeout:
        log.warning('Timeout has now affect for ipmi hostBootSource')

    session.Session.initting_sessions = {}
    try:
        mysess = command.Command(host, username, pw)
    except pyghmi_exception.IpmiException as exc:
        log.error(f'Failed IPMI login to BMC {host}')
        log.error(exc)
        mysess = None
    return mysess


def logout(host, user, pw, bmc):
    """Logout and close IPMI connection

    Args:
        host, user, pw (str): Mostly for compatability with open_bmc
        bmc (pyghmi.ipmi.command object): command instance to logout
    """
    log = logger.getlogger()
    res = bmc.ipmi_session.logout()
    if isinstance(res, dict):
        res = res["success"]
    else:
        res = False
    log.debug(f'Closing IPMI connection to: {host} result: {res}')
    del bmc.ipmi_session.initialized
    return res


def chassisPower(host, op, bmc, timeout=6):
    log = logger.getlogger()
    op = op.lower()

    class PowerOp(Enum):
        status = 'status'
        state = 'status'
        on = 'on'
        off = 'off'
        softoff = 'softoff'
        hardoff = 'off'
        reset = 'reset'
        cycle = 'reset'
        shutdown = 'softoff'
        diag = 'diag'

    msg = {
        'status': f'Getting power status for {host}',
        'state': f'Getting power status for {host}',
        'on': f'Attempting Power on for {host}',
        'softoff': f'Attempting gracefull power off for {host}',
        'hardoff': f'Attempting immediate power off for {host}',
        'off': f'Attempting immediate power off for {host}'
    }

    try:
        PowerOp[op]
    except KeyError as exc:
        log.error(f'Invalid chassis power operation: {op} Key error {exc}')
        raise

    log.debug(msg[PowerOp[op].value])

    if PowerOp[op].value in ('status', 'state'):
        try:
            res = bmc.get_power()
        except pyghmi_exception.IpmiException as exc:
            log.error(f'Failed IPMI get power from BMC {host}')
            log.error(exc)
            res = None
        else:
            res = res['powerstate']
    elif PowerOp[op].value in ('on', 'off', 'hardoff', 'softoff', 'cycle'):
        try:
            res = bmc.set_power(PowerOp[op].value, timeout)
        except pyghmi_exception.IpmiException as exc:
            log.error(f'Failed IPMI set power state {PowerOp[op].value} from BMC {host}')
            log.error(exc)
            res = None
        else:
            res = res['powerstate']
    return res


def hostBootSource(host, source, bmc, timeout=None):
    """Gets or sets the host boot source.
    Args:
        host: string, the hostname or IP address of the bmc
        source: (str) The source to boot from.
            If empty, returns the boot source.
        timeout (None) : Does nothing. Provides compatibility with open_bmc args
    returns: (str) boot source
    """
    log = logger.getlogger()

    class BootSource(Enum):
        default = 'default'
        none = 'default'
        network = 'network'
        pxe = 'network'
        disk = 'hd'
        hd = 'hd'
        setup = 'setup'
        bios = 'setup'
        safe = 'safe'

    if timeout:
        log.warning('Timeout has now affect for ipmi hostBootSource')

    if source:
        try:
            BootSource[source]
        except KeyError as exc:
            log.error(f'Invalid boot source: {source} Key error {exc}')
            raise

        try:
            res = bmc.set_bootdev(BootSource[source].value, persist=False)
        except pyghmi_exception.IpmiException as exc:
            log.error(f'Failed IPMI set boot device {BootSource[source].value} '
                      f'from BMC {host}. {exc} ')
            res = None
        else:
            res = res['bootdev']
    else:
        try:
            res = bmc.get_bootdev()
        except pyghmi_exception.IpmiException as exc:
            log.error(f'Failed IPMI get boot device from BMC {host}')
            log.error(exc)
            res = None
        else:
            res = res['bootdev']
    return res


def hostBootMode(host, mode, bmc, timeout=None):
    """Gets or sets the host boot mode. For an ipmi device the
    set_bootdev and get_bootdev  functions are called.
    Args:
        host: string, the hostname or IP address of the bmc
        source: (str) The source to boot from.
        If empty, returns the boot source.
        timeout (None) : Does nothing. Provides compatibility with open_bmc args
    returns (str) : boot mode
    """
    log = logger.getlogger()

    class BootMode(Enum):
        default = 'default'
        safe = 'safe'
        setup = 'setup'
        bios = 'setup'

    if timeout:
        log.warning('Timeout has now affect for ipmi hostBootMode')

    if mode:
        try:
            BootMode[mode]
        except KeyError as exc:
            log.error(f'Invalid host boot mode: {mode} Key error {exc}')
            raise

        try:
            res = bmc.set_bootdev(BootMode[mode].value, persist=False)
        except pyghmi_exception.IpmiException as exc:
            log.error(f'Failed IPMI set boot device {BootMode[mode].value} '
                      f'from BMC {host}')
            log.error(exc)
            res = None
        else:
            res = res['bootdev']
    else:
        try:
            res = bmc.get_bootdev()
        except pyghmi_exception.IpmiException as exc:
            log.error(f'Failed IPMI get boot device from BMC {host}')
            log.error(exc)
            res = None
        else:
            res = res['bootdev']
    return res


def bmcReset(host, op, bmc):
    """
         controls resetting the bmc. warm reset reboots the bmc, cold reset removes
         the configuration and reboots.
         Args:
            host: string, the hostname or IP address of the bmc
            args: contains additional arguments used by the bmcReset sub command
            bmc: the active bmc connection to use
         returns : True if reset accepted, else False
    """
    log = logger.getlogger()
    op = op.lower()

    class BmcOp(Enum):
        # warm = 'warm'  # implemention in openbmctool is same as 'warm'
        cold = 'cold'

    try:
        BmcOp[op]
    except KeyError as exc:
        log.error(f'Invalid bmc operation: {op} Key error {exc}')
        raise

    if(BmcOp[op].value == "cold"):
        try:
            # 'raw_command used here instead of reset_bmc so as to get the response
            res = bmc.reset_bmc()
        except pyghmi_exception.IpmiException:
            log.error(f'Failed cold reboot of BMC {host}')
            res = False
        else:
            res = True
    return res
