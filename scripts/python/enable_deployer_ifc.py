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
import os.path
import netaddr
from pyroute2 import IPRoute

from lib.inventory import Inventory
from lib.logger import Logger

FILE_PATH = os.path.dirname(os.path.abspath(__file__))


class EnableDeployerIfc(object):
    BRIDGE = 'bridge'
    LOCAL = 'lo'

    def __init__(self, log, inv_file):
        inv = Inventory(log, inv_file)
        self.log = log
        self.ext_label_dev = inv.get_mgmt_switch_external_dev_label()

        if inv.is_passive_mgmt_switches():
            if self.ext_label_dev:
                self.log.info('Passive Management Switch(es) Detected')
                print(self.ext_label_dev)
                sys.exit(0)
            else:
                self.log.error('Management switch not found')
                sys.exit(1)

        for self.ipv4 in inv.yield_mgmt_switch_ip():
            pass
        mgmt_network = inv.get_ipaddr_mgmt_network()
        self.broadcast = str(netaddr.IPNetwork(mgmt_network).broadcast)
        self.mask = str(netaddr.IPNetwork(mgmt_network).netmask)

        if self.ext_label_dev:
            self.log.debug(
                'External dev label %s was specified' % self.ext_label_dev)
        else:
            self.log.debug('External dev label was not specified')
        self.ext_ip_dev = inv.get_mgmt_switch_external_dev_ip()
        self.ext_prefix = inv.get_mgmt_switch_external_prefix()
        for self.ext_ip_switch in inv.yield_mgmt_switch_external_switch_ip():
            pass

        self.ext_broadcast = str(netaddr.IPNetwork(
            self.ext_ip_dev + '/' + self.ext_prefix).broadcast)
        self.ext_mask = str(netaddr.IPNetwork(
            self.ext_ip_dev + '/' + self.ext_prefix).netmask)

        self.ipr = IPRoute()
        for link in self.ipr.get_links():
            kind = None
            try:
                self.label = (link.get_attr('IFLA_IFNAME'))
                kind = (link.get_attr('IFLA_LINKINFO').get_attr(
                    'IFLA_INFO_KIND'))
            except:
                pass
            if kind == self.BRIDGE:
                if self.ipr.get_addr(
                        label=self.label, broadcast=self.broadcast):
                    self.log.info(
                        'Bridge %s on management subnet %s found' %
                        (self.label, mgmt_network))
                    if self._ping(self.ipv4, self.label):
                        self.log.info(
                            'Management switch found on %s' %
                            self.label)
                        sys.exit(0)
                    else:
                        self.log.debug(
                            'Management switch not found on %s' %
                            self.label)

        if self.ext_label_dev:
            self.dev = self.ipr.link_lookup(ifname=self.ext_label_dev)[0]
            self._add_ip()

            # Print to stdout for Ansible playbook to register
            print(self.ext_label_dev)
        else:
            switch_found = False
            for link in self.ipr.get_links():
                kind = None
                try:
                    self.label = (link.get_attr('IFLA_IFNAME'))
                    kind = (link.get_attr('IFLA_LINKINFO').get_attr(
                        'IFLA_INFO_KIND'))
                except:
                    pass
                if self.label != self.LOCAL and not kind:
                    self.dev = self.ipr.link_lookup(ifname=self.label)[0]
                    self._add_ip()

                    if self._ping(self.ext_ip_switch, self.label):
                        switch_found = True
                        self.log.info(
                            'Management switch found on %s' %
                            self.label)
                        self._configure_switch()
                    else:
                        self.log.debug(
                            'Management switch not found on %s' % self.label)

                    self._del_ip()

                    if switch_found:
                        break

            if not switch_found:
                self.log.error('Management switch not found')
                sys.exit(1)

            # Print to stdout for Ansible playbook to register
            print(self.label)

    def _add_ip(self):
        if self.ext_label_dev:
            label = self.ext_label_dev
        else:
            label = self.label
        if self.ipr.get_addr(label=label, address=self.ext_ip_dev):
            self._is_add_ext_ip = False
            self.log.debug(
                '%s was already configured on %s' %
                (self.ext_ip_dev, label))
        else:
            self._is_add_ext_ip = True
            self.log.debug(
                'Add %s to interface %s' % (self.ext_ip_dev, label))
            self.ipr.addr(
                'add',
                index=self.dev,
                address=self.ext_ip_dev,
                mask=int(self.ext_prefix),
                broadcast=self.ext_broadcast)

    def _ping(self, ipaddr, dev):
        if os.system('ping -c 1 -I %s %s > /dev/null' % (dev, ipaddr)):
            self.log.info(
                'Ping via %s to management switch at %s failed' %
                (dev, ipaddr))
            return False
        self.log.info(
            'Ping via %s to management switch at %s passed' %
            (dev, ipaddr))
        return True


if __name__ == '__main__':
    """
    Arg1: inventory file
    Arg2: log level
    """
    LOG = Logger(__file__)

    if len(sys.argv) != 3:
        try:
            raise Exception()
        except Exception:
            LOG.error('Invalid argument count')
            sys.exit(1)

    INV_FILE = sys.argv[1]
    LOG.set_level(sys.argv[2])

    EnableDeployerIfc(LOG, INV_FILE)
