#!/usr/bin/env python
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
import sys
from pyroute2 import IPRoute
import code

import lib.logger as logger
from lib.utilities import Color


class Interfaces(object):
    def __init__(self):
        """ Get instance of IPRoute and initialize a 'flattened' dictionary of
        interfaces information.
        Top level ifcs keys are interface names. Second level key contain; state (UP/DOWN),
        type (type of interface (phys/vlan/bridge/veth/tun)), vlan (number or None),
        and addrs (tuple of addresses).
        """
        self.ipr = IPRoute()
        # get list of link indecis in the host namespace
        self.link_indcs = ()
        for link in self.ipr.get_links():
            self.link_indcs += (link['index'],)
        #code.interact(banner='here', local=dict(globals(), **locals()))
        self.ifcs = {}
        for link in self.ipr.get_links():
            link_name = link.get_attr('IFLA_IFNAME')
            self.ifcs[link_name] = {}
            #code.interact(banner='here', local=dict(globals(), **locals()))
            self.ifcs[link_name]['addrs'] = []
            # If this link has a slave (eg a tagged vlan ifc)
            # thats in the host namespace then the value of the 'slave' key
            # is the ifc name.  If the slave is not in the host namespace (ie
            # a container, then set 'slave' to the index number.
            if link.get_attr('IFLA_LINK'):
                link_idx = link.get_attr('IFLA_LINK')
                if link_idx in self.link_indcs:
                    #code.interact(banner='There', local=dict(globals(), **locals()))
                    self.ifcs[link_name]['slave'] = self.ipr.get_links\
                        (link_idx)[0].get_attr('IFLA_IFNAME')
                else:
                    self.ifcs[link_name]['slave'] = link_idx
            else:
                self.ifcs[link_name]['slave'] = None


            # Get list of ipv4  addresses
            if self.ipr.get_addr(label=link_name):
                for idx, item in enumerate(self.ipr.get_addr(label=link_name)):
                    self.ifcs[link_name]['addrs'].append(self.ipr.get_addr\
                        (label=link_name)[idx].get_attr('IFA_ADDRESS'))
            self.ifcs[link_name]['state'] = link.get_attr('IFLA_OPERSTATE')
            self.ifcs[link_name]['mac'] = link.get_attr('IFLA_ADDRESS')
            if not link.get_attr('IFLA_LINKINFO'):
                self.ifcs[link_name]['type'] = 'phys'
                self.ifcs[link_name]['vlan'] = None
            else:
                self.ifcs[link_name]['type'] = link.get_attr('IFLA_LINKINFO')\
                    .get_attr('IFLA_INFO_KIND')
                #code.interact(banner='here', local=dict(globals(), **locals()))
                if link.get_attr('IFLA_LINKINFO').get_attr('IFLA_INFO_KIND') == 'vlan':
                    self.ifcs[link_name]['vlan'] = link.get_attr('IFLA_LINKINFO')\
                        .get_attr('IFLA_INFO_DATA').get_attr('IFLA_VLAN_ID')
                else:
                    self.ifcs[link_name]['vlan'] = None

    def get_interfaces(self, _type='all', exclude=''):
        """ Get tuple of interface names.
        Inputs:
            type (str): Interface type (ie 'phys', 'vlan', 'bridge', 'veth', 'tun')
            exclude (str): Name of an interface to exclude from the dictionary. This is
                           convienent when you want to check if another interface
                           is already using vlan number.
        """
        ifcs = ()
        for ifc in self.ifcs:
            if ifc == exclude:
                continue
            if _type == 'all' or self.ifcs[ifc]['type'] == _type:
                ifcs += (ifc,)
        return ifcs

    def get_up_interfaces(self, _type='all', exclude=''):
        """ Get tuple of interface names for 'UP' interfaces.
        Inputs:
            type (str): Interface type (ie 'phys', 'vlan', 'bridge', 'veth', 'tun')
            exclude (str): Name of an interface to exclude from the dictionary. This is
                           convienent when you want to check if another interface
                           is already using vlan number.
        """
        ifcs = ()
        for ifc in self.ifcs:
            if ifc == exclude:
                continue
            if _type == 'all' or self.ifcs[ifc]['type'] == _type:
                if self.ifcs[ifc]['state'] == 'UP':
                    ifcs += (ifc,)
        return ifcs

    def get_vlan_interfaces(self, exclude=''):
        """ Get dictionary of vlan interfaces and their vlan number.
        Inputs:
            exclude (str): Name of an interface to exclude from the dictionary. This is
                           convienent when you want to check if another interface
                           is already using vlan number.
        """
        vlan_ifcs = {}
        for ifc in self.ifcs:
            if ifc == exclude:
                continue
            if self.ifcs[ifc]['type'] == 'vlan':
                vlan_ifcs[ifc] = self.ifcs[ifc]['vlan']
        return vlan_ifcs

    def is_vlan_used_elsewhere(self, vlan, ifc):
        """ Checks to see if a given vlan number is already in use.
        Inputs:
            vlan (int or str): vlan number.
            ifc (str): Name of the interface to exclude from the check.
        Returns: True or False
        """
        vlan_ifcs = self.get_vlan_interfaces(exclude=ifc)
        #code.interact(banner='here', local=dict(globals(), **locals()))
        if int(vlan) in vlan_ifcs.values():
            return True
        else:
            return False


if __name__ == '__main__':
    """Simple python template
    """

    parser = argparse.ArgumentParser()
    parser.add_argument('arg1', help='Help me Rhonda', nargs='?')
#    parser.add_argument('arg2', choices=['apple', 'banana', 'peach'],
#                        help='Pick a fruit')
    parser.add_argument('--print', '-p', dest='log_lvl_print',
                        help='print log level', default='info')
    parser.add_argument('--file', '-f', dest='log_lvl_file',
                        help='file log level', default='info')
    args = parser.parse_args()

    logger.create('nolog', 'info')
    log = logger.getlogger()

    if args.log_lvl_print == 'debug':
        print(args)

    i = Interfaces()
    print(i.ifcs)
