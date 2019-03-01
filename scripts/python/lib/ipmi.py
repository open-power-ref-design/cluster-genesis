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
import re
from enum import Enum
import yaml
import code

import lib.logger as logger
import lib.utilities as u


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
        log.debug('Timeout has no affect for ipmi hostBootSource')

    session.Session.initting_sessions = {}
    try:
        mysess = command.Command(host, username, pw)
        #mysess = Ipmi_cmd(host, username, pw)
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


def ipmi_fru2dict(fru_str):
    """Convert the ipmitool fru output to a dictionary. The function first
        converts the input string to yaml, then yaml load is used to create a
        dictionary.
    Args:
        fru_str (str): Result of running 'ipmitool fru'
    returns: A dictionary who's keys are the FRUs
    """
    yaml_data = []
    #code.interact(banner='ipmi.ipmi_fru2dict', local=dict(globals(), **locals()))
    lines = fru_str.splitlines()
    for i, _line in enumerate(lines):
        # Strip out any excess white space (including tabs) around the ':'
        line = re.sub(r'\s*:\s*', ': ', _line)
        # Check for blank lines
        if re.search(r'^\s*$', line):
            yaml_data.append(line)
            continue
        if i < len(lines) - 1:
            # If indentation is increasing on the following line, then convert the
            # current line to a dictionary key.
            indent = re.search(r'[ \t]*', line).span()[1]
            next_indent = re.search(r'[ \t]*', lines[i + 1]).span()[1]
            if next_indent > indent:
                line = re.sub(r'\s*:\s*', ':', line)
                # if ':' in middle of line take the second half, else
                # take the beginning
                if line.split(':')[1]:
                    line = line.split(':')[1]
                else:
                    line = line.split(':')[0]
                yaml_data.append(line + ':')
            else:
                if ':' not in line:
                    line += ':'
                split = line.split(':', 1)
                # Add quotes around the value to handle non alphanumerics
                line = split[0] + ': "' + split[1] + '"'
                yaml_data.append(line)
    yaml_data = '\n'.join(yaml_data)
    return yaml.load(yaml_data)


def extract_system_sn_pn(ipmi_fru_str):
    fru_item = extract_system_info(ipmi_fru_str)
    fru_item = fru_item[list(fru_item.keys())[0]]

    return fru_item['Chassis Serial'].strip(), fru_item['Chassis Part Number'].strip()


def extract_system_info(ipmi_fru_str):
    """ Extract the system information from the ipmitool fru result.
    The fru string is search for keywords to try to locate the system info.
    Args:
        ipmi_fru_str (str) : result of ipmitool fru command
    returns:
        dictionary with system fru info
    """
    #code.interact(banner='extract_system_info', local=dict(globals(), **locals()))
    yaml_dict = ipmi_fru2dict(ipmi_fru_str)
    fru_item = ''
    for item in yaml_dict:
        for srch_item in ['NODE', 'SYS', 'Backplane', 'MP', 'Mainboard']:
            #code.interact(banner='There', local=dict(globals(), **locals()))
            if srch_item in item:
                fru_item = yaml_dict[item]
                break
        if fru_item:
            fru_item = {item: fru_item}
            break
    if not fru_item:
        fru_item = yaml_dict
        #fru_item = yaml_dict[list(yaml_dict.keys())[0]]
    return fru_item


def get_system_inventory(host, user, pw):
    log = logger.getlogger()
    cmd = f'ipmitool -I lanplus -H {host} -U {user} -P {pw} fru'
    #code.interact(banner='ipmi.get_system_info', local=dict(globals(), **locals()))
    res, err, rc = u.sub_proc_exec(cmd)
    if rc == 0:
        return res
    else:
        log.debug(f'Unable to read system information from {host}, rc: {rc}')


def get_system_info(host, user, pw):
    log = logger.getlogger()
    #cmd = f'ipmitool -I lanplus -H {host} -U {user} -P {pw} fru'
    #code.interact(banner='ipmi.get_system_info', local=dict(globals(), **locals()))
    #res, err, rc = u.sub_proc_exec(cmd)
    inv = get_system_inventory(host, user, pw)

    if inv:
        sys_info = extract_system_info(inv)
        return sys_info
    else:
        log.debug(f'Unable to read system information from {host}')


def get_system_sn_pn(host, user, pw):
    log = logger.getlogger()
    sys_info = get_system_info(host, user, pw)
    if not sys_info:
        return
    else:
        #code.interact(banner='ipmi.get_system_sn_pn', local=dict(globals(), **locals()))
        key = list(sys_info.keys())[0]
        return (sys_info[key]['Chassis Serial'], sys_info[key]['Chassis Part Number'])


def get_system_inventory_in_background(host, user, pw):
    """ Launches a background subprocess (using Popen) to gather fru information from
    a target node. The reference to the subprocess class is returned. The background
    subprocess can be polled for completion using process.poll
    Fru information can be read using process.communicate

    example:
    p = get_system_inventory_in_background('192.168.36.21', 'ADMIN', 'admin')
    ready = False
    while not ready:
        if p.poll():
            ready = True
    sys_inv = p.communicate()
    sys_info = extract_system_info_from_inventory(sys_inv)  # returns dict
    sn, pn = extract_system_sn_pn_from_inventory(sys_inv)
    """
    log = logger.getlogger()
    cmd = f'ipmitool -I lanplus -H {host} -U {user} -P {pw} fru'
    #code.interact(banner='ipmi.get_system_info', local=dict(globals(), **locals()))
    try:
        process = u.sub_proc_launch(cmd)
    except OSError:
        log.error('An OS error occurred while attempting to run ipmitool fru cmd')
    except ValueError:
        log.error('An incorrect argument was passed to the subprocess running ipmitool')

    return process


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
        log.debug('Timeout has no affect for ipmi hostBootSource')

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
        log.debug('Timeout has no affect for ipmi hostBootMode')

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
