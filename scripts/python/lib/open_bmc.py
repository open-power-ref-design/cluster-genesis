#!/usr/bin/python3
# Copyright 2019 IBM Corporation
#
# All Rights Reserved.
##
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import requests
import json
from enum import Enum

import lib.logger as logger


def login(host, username, pw, timeout=10):
    """
         Logs into the BMC and creates a session

         @param host: string, the hostname or IP address of the bmc to log into
         @param username: The user name for the bmc to log into
         @param pw: The password for the BMC to log into
         @return: Session object
    """
    log = logger.getlogger()
    requests.packages.urllib3.disable_warnings(
        requests.packages.urllib3.exceptions.InsecureRequestWarning)
    httpHeader = {'Content-Type': 'application/json'}
    mysess = requests.session()
    try:
        r = mysess.post(f'https://{host}/login', headers=httpHeader,
                        json={"data": [username, pw]}, verify=False,
                        timeout=timeout)
    except(requests.exceptions.Timeout) as err:
        log.debug(f'BMC login session request timout error {err}')
        mysess = None
    except(requests.exceptions.ConnectionError) as err:
        log.debug(f'BMC login session request connect error {err}')
        mysess = None
    else:
        try:
            loginMessage = json.loads(r.text)
        except json.JSONDecodeError as exc:
            log.debug(f'Error decoding JSON response from BMC {host}')
            log.debug(exc)
            mysess = None
        else:
            if (loginMessage['status'] != "ok"):
                log.debug(loginMessage["data"]["description"].encode('utf-8'))
                mysess = None
    return mysess


def logout(host, username, pw, session, timeout=10):
    """
         Logs out of the bmc and terminates the session

         @param host: string, the hostname or IP address of the bmc to log
                              out of
         @param username: The user name for the bmc to log out of
         @param pw: The password for the BMC to log out of
         @param session: the active session to use
    """
    log = logger.getlogger()
    httpHeader = {'Content-Type': 'application/json'}
    try:
        r = session.post(f'https://{host}/logout', headers=httpHeader,
                         json={"data": [username, pw]}, verify=False,
                         timeout=timeout)
    except(requests.exceptions.Timeout) as err:
        log.debug(f'BMC session request timout error {err}')
    except(requests.exceptions.ConnectionError) as err:
        log.debug(f'BMC logout session request connect error {err}')
    else:
        if('"message": "200 OK"' in r.text):
            log.debug(f'Host {host}, user {username} has been logged out')
            return True


def hostBootMode(host, mode, session, timeout=5):
    """Gets or sets the host boot mode.
    @param host: string, the hostname or IP address of the bmc
    @param source: (str) The mode to boot.
        If empty, returns the boot source.
    """
    log = logger.getlogger()
    mode = mode.title()

    class BootMode(Enum):
        Regular = 'Regular'
        Setup = 'Setup'
        Bios = 'Setup'
        Safe = 'Safe'

    if mode:
        try:
            BootMode[mode]
        except KeyError as exc:
            log.error(f'Invalid Boot mode: {mode} Key error {exc}')
            raise

        url = (f"https://{host}/xyz/openbmc_project/control/host0/boot/"
               "one_time/attr/BootMode")
        httpHeader = {'Content-Type': 'application/json'}
        data = ('xyz.openbmc_project.Control.Boot.Mode.Modes.'
                f'{BootMode[mode].value}')
        data = '{"data":"' + data + '"}'
        try:
            res = session.put(url, headers=httpHeader, data=data, verify=False,
                              timeout=timeout)
        except(requests.exceptions.Timeout) as exc:
            log.error('BMC request timeout error.')
            log.debug(exc)
        else:
            if res.status_code == 200:
                return BootMode[mode].value.lower()
            else:
                log.error(f'Error setting boot source. rc: {res.status_code} '
                          f'reason: {res.reason}')
                return

    else:
        url = (f"https://{host}/xyz/openbmc_project/control/host0/boot/"
               "one_time/attr/BootMode")
        httpHeader = {'Content-Type': 'application/json'}
        try:
            res = session.get(url, headers=httpHeader, verify=False,
                              timeout=timeout)
        except(requests.exceptions.Timeout) as exc:
            log.error(f'BMC request timeout error. {exc}')
        else:
            bootMode = json.loads(res.text)['data'].split('.')[-1]
            return bootMode.lower()


def hostBootSource(host, source, session, timeout=5):
    """Gets or sets the host boot source.
    @param host: string, the hostname or IP address of the bmc
    @param source: (str) The source to boot from.
        If empty, returns the boot source.
    """
    log = logger.getlogger()
    source = source.title()

    class BootSource(Enum):
        Default = 'Default'
        Network = 'Network'
        Pxe = 'Network'
        Disk = 'Disk'

    if source:
        try:
            BootSource[source]
        except KeyError as exc:
            log.error(f'Invalid Boot source: {source} Key error {exc}')
            raise
        url = (f"https://{host}/xyz/openbmc_project/control/host0/boot/"
               "one_time/attr/BootSource")
        httpHeader = {'Content-Type': 'application/json'}
        data = ('xyz.openbmc_project.Control.Boot.Source.Sources.'
                f'{BootSource[source].value}')
        data = '{"data":"' + data + '"}'
        try:
            res = session.put(url, headers=httpHeader, data=data, verify=False,
                              timeout=timeout)
        except(requests.exceptions.Timeout) as exc:
            log.error(f'BMC request timeout error. {exc}')
        else:
            if res.status_code == 200:
                return BootSource[source].value.lower()
            else:
                log.error(f'Error setting boot source. rc: {res.status_code} '
                          f'reason: {res.reason}')
                return
    else:
        url = (f"https://{host}/xyz/openbmc_project/control/host0/boot/"
               "one_time/attr/BootSource")
        httpHeader = {'Content-Type': 'application/json'}
        try:
            res = session.get(url, headers=httpHeader, verify=False,
                              timeout=timeout)
        except(requests.exceptions.Timeout) as exc:
            log.error(f'BMC request timeout error. {exc}')
        else:
            bootSource = json.loads(res.text)['data'].split('.')[-1]
            return bootSource.lower()


def chassisPower(host, op, session, timeout=5):
    """  called by the chassis function. Controls the power state of the
         chassis, or gets the status

         @param host: string, the hostname or IP address of the bmc
         @param args: contains additional arguments used by the fru sub command
         @param session: the active session to use
         @param args.json: boolean, if this flag is set to true, the output
            will be provided in json format for programmatic consumption
    """
    log = logger.getlogger()
    op = op.lower()

    class PowerOp(Enum):
        status = 'status'
        state = 'status'
        on = 'On'
        softoff = 'Off'
        hardoff = 'Off'
        off = 'Off'
        bmcstatus = 'bmcstatus'

    msg = {
        'status': f'Getting power status for {host}',
        'state': f'Getting power status for {host}',
        'on': f'Attempting Power on for {host}',
        'softoff': f'Attempting gracefull power off for {host}',
        'hardoff': f'Attempting immediate power off for {host}',
        'off': f'Attempting immediate power off for {host}',
        'bmcstatus': f'Getting BMC status for {host}'
    }

    try:
        PowerOp[op]
    except KeyError as exc:
        log.error(f'Invalid chassis power operation: {op} Key error {exc}')
        raise

    httpHeader = {'Content-Type': 'application/json'}

    if PowerOp[op].value not in ('status', 'bmcstatus'):
        if checkFWactivation(host, session):
            log.debug("Chassis Power control disabled during firmware "
                      "activation")
            return

            log.debug(msg[op])
        url = (f"https://{host}/xyz/openbmc_project/state/host0/attr/"
               "RequestedHostTransition")
        data = ('"xyz.openbmc_project.State.Host.Transition.'
                f'{PowerOp[op].value}"')
        data = '{"data":' + data + '}'
        try:
            res = session.put(url, headers=httpHeader, data=data, verify=False,
                              timeout=timeout)
        except(requests.exceptions.Timeout) as exc:
            log.debug(f'BMC request timeout error. Host: {host}')
            log.debug(exc)
            res = None
        except(requests.exceptions.ConnectionError) as exc:
            log.debug(f'BMC request connection error. Host: {host}')
            log.debug(exc)
            res = None
        else:
            log.debug(f'Set power result: {res.text.lower()}')
            if '200 ok' in res.text.lower():
                res = op
            else:
                res = None

    elif PowerOp[op].value in ('bmcstatus', 'status'):
        if PowerOp[op].value == 'bmcstatus':
            url = (f"https://{host}/xyz/openbmc_project/state/bmc0/attr/"
                   "CurrentBMCState")
        else:
            url = (f"https://{host}/xyz/openbmc_project/state/chassis0/attr/"
                   "CurrentPowerState")
        try:
            res = session.get(url, headers=httpHeader, verify=False,
                              timeout=timeout)
        except(requests.exceptions.Timeout) as exc:
            log.debug(f'BMC request timeout error. Host: {host}')
            log.debug(exc)
            res = None
        except(requests.exceptions.ConnectionError) as exc:
            log.debug(f'BMC request connection error. Host: {host}')
            log.debug(exc)
            res = None
        else:
            try:
                res = json.loads(res.text)['data'].split('.')[-1].lower()
            except (json.JSONDecodeError, AttributeError) as exc:
                log.debug(f'Error in JSON response from BMC {host}')
                log.debug(exc)
                res = None
            # Make sure the BMC is in ready state or chassis power status
            # can report incorrectly
            else:
                bmc_status = bmcPowerState(host, session, timeout)
                if bmc_status != 'ready':
                    res = None
    return res

#        url=("https://"+host+"/xyz/openbmc_project/state/host0/attr/"
#             "CurrentHostState")
#        try:
#            res = session.get(url, headers=httpHeader, verify=False,
#                              timeout=30)
#        except(requests.exceptions.Timeout):
#            return(connectionErrHandler(args.json, "Timeout", None))
#        hostState = json.loads(res.text)['data'].split('.')[-1]
#        url=("https://"+host+"/xyz/openbmc_project/state/bmc0/attr/"
#             "CurrentBMCState")
#        try:
#            res = session.get(url, headers=httpHeader, verify=False,
#                              timeout=30)
#        except(requests.exceptions.Timeout):
#            return(connectionErrHandler(args.json, "Timeout", None))
#        bmcState = json.loads(res.text)['data'].split('.')[-1]
#
#        return ("Chassis Power State: " +chassisState +
#                 "\nHost Power State: " + hostState + "\nBMC Power State: " +
#                 bmcState)
#    else:
#        return "Invalid chassis power command"
#
#    return res


def checkFWactivation(host, session):
    """
        Checks the software inventory for an image that is being activated.

        @return: True if an image is being activated,
                 false is no activations are happening
    """
    log = logger.getlogger()
    url = f"https://{host}/xyz/openbmc_project/software/enumerate"
    httpHeader = {'Content-Type': 'application/json'}
    try:
        resp = session.get(url, headers=httpHeader, verify=False, timeout=5)
    except(requests.exceptions.Timeout) as exc:
        log.error(f'BMC request timeout error. {exc}')
        return True
    except(requests.exceptions.ConnectionError) as exc:
        log.error(f'BMC connection error. {exc}')
        return True
    fwInfo = json.loads(resp.text)['data']
    for key in fwInfo:
        if 'Activation' in fwInfo[key]:
            if 'Activating' in (fwInfo[key]['Activation'],
                                fwInfo[key]['RequestedActivation']):
                return True
    return False


def get_system_info(host, session, timeout=5):
    log = logger.getlogger()

    url = (f"https://{host}/xyz/openbmc_project/inventory/system")
    httpHeader = {'Content-Type': 'application/json'}
    try:
        res = session.get(url, headers=httpHeader, verify=False,
                          timeout=timeout)
    except(requests.exceptions.Timeout) as exc:
        log.debug('BMC request timeout error. Host: {host}')
        log.debug(exc)
        res = None
    except(requests.exceptions.ConnectionError) as exc:
        log.debug('BMC request connection error. Host: {host}')
        log.debug(exc)
        res = None
    else:
        try:
            res = json.loads(res.text)
            # res = (res['data']['Model'], res['data']['SerialNumber'])
        except (json.JSONDecodeError, AttributeError) as exc:
            log.error(f'Error in JSON response from BMC {host}')
            log.debug(exc)
            res = None
    log.debug(f'BMC PN and SN: {res}')
    return res


def get_system_sn_pn(host, session, timeout=5):
    """Get the sn and pn for a host
    Args:
        host(str): host ip or name
        session(session object instance)
    returns: tuple with sn and pn
    """
    log = logger.getlogger()

    url = (f"https://{host}/xyz/openbmc_project/inventory/system")
    httpHeader = {'Content-Type': 'application/json'}
    try:
        res = session.get(url, headers=httpHeader, verify=False,
                          timeout=timeout)
    except(requests.exceptions.Timeout) as exc:
        log.debug('BMC request timeout error. Host: {host}')
        log.debug(exc)
        res = None
    except(requests.exceptions.ConnectionError) as exc:
        log.debug('BMC request connection error. Host: {host}')
        log.debug(exc)
        res = None
    else:
        try:
            res = json.loads(res.text)
            res = (res['data']['SerialNumber'], res['data']['Model'])
        except (json.JSONDecodeError, AttributeError) as exc:
            log.error(f'Error in JSON response from BMC {host}')
            log.debug(exc)
            res = None
    log.debug(f'BMC SN and PN: {res}')
    return res


def bmcPowerState(host, session, timeout):
    log = logger.getlogger()

    url = f"https://{host}/xyz/openbmc_project/state/bmc0/attr/CurrentBMCState"
    httpHeader = {'Content-Type': 'application/json'}
    try:
        res = session.get(url, headers=httpHeader, verify=False,
                          timeout=timeout)
    except(requests.exceptions.Timeout) as exc:
        log.debug('BMC request timeout error. Host: {host}')
        log.debug(exc)
        res = None
    except(requests.exceptions.ConnectionError) as exc:
        log.debug('BMC request connection error. Host: {host}')
        log.debug(exc)
        res = None
    else:
        try:
            res = json.loads(res.text)['data'].split('.')[-1].lower()
        except (json.JSONDecodeError, AttributeError) as exc:
            log.error(f'Error in JSON response from BMC {host}')
            log.debug(exc)
            res = None
    log.debug(f'BMC Power state: {res}')
    return res


def bmcReset(host, op, session):
    """
         controls resetting the bmc. warm reset reboots the bmc, cold reset
         removes the configuration and reboots.

         @param host: string, the hostname or IP address of the bmc
         @param args: contains additional arguments used by the bmcReset sub
                      command
         @param session: the active session to use
         @param args.json: boolean, if this flag is set to true, the output
                                    will be provided in json format for
                                    programmatic consumption
         @return : response from BMC if reset accepted, else None
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

    if checkFWactivation(host, session):
        log.error("BMC reset control disabled during firmware activation")

    if(BmcOp[op].value == "cold"):
        url = (f"https://{host}/xyz/openbmc_project/state/bmc0/attr/"
               "RequestedBMCTransition")
        httpHeader = {'Content-Type': 'application/json'}
        data = '{"data":"xyz.openbmc_project.State.BMC.Transition.Reboot"}'
        try:
            res = session.put(url, headers=httpHeader, data=data, verify=False,
                              timeout=5)
        except(requests.exceptions.Timeout) as exc:
            log.error(f'BMC request timeout error. Host: {host}')
            log.debug(exc)
            res = None
        except(requests.exceptions.ConnectionError) as exc:
            log.error(f'BMC request connection error. Host: {host}')
            log.debug(exc)
            res = None
        else:
            try:
                res = json.loads(res.text)['status'].lower()
            except json.JSONDecodeError as exc:
                log.error(f'Error decoding JSON response from BMC {host}')
                log.error(exc)
                res = None
            except KeyError as exc:
                log.error(f'Error in response from BMC {host}.'
                          'Status key not found {exc}')
                log.error(exc)
                res = None
    return res
