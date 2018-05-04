#!/usr/bin/env python
"""Cluster Genesis 'teardown' command"""

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
import os.path

import teardown_deployer_container
import enable_deployer_gateway
import teardown_deployer_networks
import lib.argparse_teardown as argparse_teardown
import lib.logger as logger
import configure_data_switches
from lib.genesis import GEN_PATH


class Teardown(object):
    """Cluster Genesis 'teardown' command

    Args:
        log(object): log
    """

    def __init__(self, args):
        self.config_file_path = GEN_PATH
        self.args = args

    def _destroy_deployer_container(self):
        teardown_deployer_container.teardown_deployer_container(self.config_file_path)

    def _teardown_deployer_gateway(self):
        enable_deployer_gateway.enable_deployer_gateway(self.config_file_path,
                                                        remove=True)

    def _teardown_deployer_networks(self):
        teardown_deployer_networks.teardown_deployer_network(self.config_file_path)

    def _teardown_switch_data(self):
        configure_data_switches.deconfigure_data_switch(self.config_file_path)

    def _teardown_switch_mgmt(self):
        sys.exit('Teardown Mgmt switch not yet implemented')

    def launch(self):
        """Launch actions"""
        path = self.args.config_file_name
        if os.path.dirname(self.args.config_file_name) == '':
            path = os.path.join(os.getcwd(), self.args.config_file_name)

        if os.path.isfile(path):
            self.config_file_path = path
        else:
            self.config_file_path += self.args.config_file_name

        if not os.path.isfile(self.config_file_path):
            print('{} not found. Please specify a config file'.format(
                self.config_file_path))
            sys.exit(1)

        self.config_file_path = os.path.abspath(self.config_file_path)

        print('\nUsing {}'.format(self.config_file_path))
        resp = raw_input('Enter to continue. "T" to terminate ')
        if resp == 'T':
            sys.exit('POWER-Up stopped at user request')

        # Determine which subcommand was specified
        try:
            if self.args.deployer:
                if self.args.container:
                    self._destroy_deployer_container()
                if self.args.gateway:
                    self._teardown_deployer_gateway()
                if self.args.networks:
                    self._teardown_deployer_networks()
        except AttributeError:
            pass
        try:
            if self.args.switches:
                if self.args.data:
                    self._teardown_switch_data()
                if self.args.mgmt:
                    self._teardown_switch_mgmt()
        except AttributeError:
            pass


if __name__ == '__main__':
    args = argparse_teardown.get_parsed_args()
    logger.create(
        args.log_level_file[0],
        args.log_level_print[0])
    TEARDOWN = Teardown(args)
    TEARDOWN.launch()
