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

import subprocess
from netaddr import IPNetwork

import lib.logger as logger
from lib.config import Config


def enable_deployer_gateway(remove=False):
    """Configure or remove NAT record for PXE Network gateway
    Args:
        remove (bool, optional): True(default)= configure NAT record
                                     if it does not already exist.
                                 False = Remove NAT record if it
                                     exists.
    """

    cfg = Config()
    log = logger.getlogger()

    if not remove:
        log.info('Configure NAT record for PXE network gateway')
    else:
        log.info('Remove NAT record for PXE network gateway')

    type_ = cfg.get_depl_netw_client_type()
    dev_label = cfg.get_depl_netw_client_device()
    bridge_ipaddr = cfg.get_depl_netw_client_brg_ip()
    netprefix = cfg.get_depl_netw_client_prefix()

    for i, dev in enumerate(dev_label):
        if cfg.get_depl_gateway() and type_[i] == "pxe":
            _create_nat_gateway_rule(bridge_ipaddr[i] + "/" +
                                     str(netprefix[i]), remove)


def _create_nat_gateway_rule(network, remove=False):
    log = logger.getlogger()
    network = str(IPNetwork(network).cidr)
    # Check if POSTROUTING nat rule already exists for client network
    output = subprocess.check_output(
        ['bash', '-c', 'iptables -L POSTROUTING -t nat']).splitlines()
    for line in output:
        if "MASQUERADE" in line and network in line:
            log.debug('Found existing MASQUERADE NAT rule for {}: {}'.
                      format(network, line))
            if remove:
                cmd = ("iptables -t nat -D POSTROUTING -p all -s {0} ! -d {0} "
                       "-j MASQUERADE").format(network)
                output = subprocess.check_output(['bash', '-c', cmd])
                log.debug('Removed MASQUERADE NAT rule for {}: {}'.
                          format(network, output))
            else:
                break
    else:
        if not remove:
            # If no existing rules are found for network create one
            cmd = ("iptables -t nat -A POSTROUTING -p all -s {0} ! -d {0} "
                   "-j MASQUERADE").format(network)
            output = subprocess.check_output(['bash', '-c', cmd])
            log.debug('Created new MASQUERADE NAT rule for {}: {}'.
                      format(network, output))


if __name__ == '__main__':
    logger.create()
    enable_deployer_gateway()
