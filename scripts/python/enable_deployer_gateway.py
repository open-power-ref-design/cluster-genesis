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

import argparse
import os.path
import sys
import subprocess
from netaddr import IPNetwork

import lib.logger as logger
from lib.config import Config
from lib.genesis import GEN_PATH


def enable_deployer_gateway(config_path=None, remove=False):
    """Configure or remove NAT record for PXE Network gateway
    Args:
        remove (bool, optional): True(default)= configure NAT record
                                     if it does not already exist.
                                 False = Remove NAT record if it
                                     exists.
    """

    cfg = Config(config_path)
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
    output = subprocess.check_output(['bash', '-c',
                                      'iptables -L POSTROUTING -t nat']
                                     ).decode("utf-8").splitlines()
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
    parser = argparse.ArgumentParser()
    parser.add_argument('config_path', default='config.yml',
                        help='Config file path.  Absolute path or relative '
                        'to power-up/')

    parser.add_argument('--print', '-p', dest='log_lvl_print',
                        help='print log level', default='info')

    parser.add_argument('--file', '-f', dest='log_lvl_file',
                        help='file log level', default='info')

    args = parser.parse_args()

    if not os.path.isfile(args.config_path):
        args.config_path = GEN_PATH + args.config_path
        print('Using config path: {}'.format(args.config_path))
    if not os.path.isfile(args.config_path):
        sys.exit('{} does not exist'.format(args.config_path))

    logger.create(args.log_lvl_print, args.log_lvl_file)
    enable_deployer_gateway(args.config_path)
