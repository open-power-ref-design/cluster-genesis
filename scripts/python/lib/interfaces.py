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
import time
from pyroute2 import IPRoute
import re

import lib.logger as logger
from lib.utilities import is_overlapping_addr, add_offset_to_address,\
    get_network_size, sub_proc_exec


class Interfaces(IPRoute):
    def __init__(self, *args, **kwargs):
        super(Interfaces, self).__init__(*args, **kwargs)
        """Subclass of IPRoute2. Several convenience classes added. None of
        IPRoutes methods are overwritten.
        """
        self.log = logger.getlogger()
        self.link_indcs = ()
        for link in self.get_links():
            self.link_indcs += (link['index'],)
        # NOTE self.ifcs is static. Active methods in this Interfaces class
        # update the self.ifcs dict.  If you make interface changes using parent
        # IPRoute methods, self.ifcs will not reflect the changes unless you
        # refresh it as below.
        self.ifcs = self.get_interfaces_dict()

    def get_interfaces_dict(self):
        """Get a 'flattened' dictionary of interfaces information.
        Top level ifcs keys are interface names. Second level key contain; state (UP/DOWN),
        type (type of interface (phys/vlan/bridge/veth/tun)), vlan (number or None),
        and addrs (tuple of addresses).
        """
        ifcs = {}
        for link in self.get_links():
            link_name = link.get_attr('IFLA_IFNAME')
            ifcs[link_name] = {}
            ifcs[link_name]['addrs'] = []
            # If this link has a slave (eg a tagged vlan ifc)
            # thats in the host namespace then the value of the 'slave' key
            # is the ifc name.  If the slave is not in the host namespace (ie
            # a container, then set 'slave' to the index number.
            if link.get_attr('IFLA_LINK'):
                link_idx = link.get_attr('IFLA_LINK')
                if link_idx in self.link_indcs:
                    ifcs[link_name]['slave'] = (self.get_links(link_idx)[0].
                                                get_attr('IFLA_IFNAME'))
                else:
                    ifcs[link_name]['slave'] = link_idx
            else:
                ifcs[link_name]['slave'] = None

            # Get list of ipv4  addresses
            if self.get_addr(label=link_name):
                for idx, item in enumerate(self.get_addr(label=link_name)):
                    ifcs[link_name]['addrs'].append(self.get_addr(label=link_name)
                                                    [idx].get_attr('IFA_ADDRESS'))
            ifcs[link_name]['state'] = link.get_attr('IFLA_OPERSTATE')
            ifcs[link_name]['mac'] = link.get_attr('IFLA_ADDRESS')
            if not link.get_attr('IFLA_LINKINFO'):
                ifcs[link_name]['type'] = 'phys'
                ifcs[link_name]['vlan'] = None
            else:
                ifcs[link_name]['type'] = link.get_attr('IFLA_LINKINFO')\
                    .get_attr('IFLA_INFO_KIND')
                if link.get_attr('IFLA_LINKINFO').get_attr('IFLA_INFO_KIND') == 'vlan':
                    ifcs[link_name]['vlan'] = link.get_attr('IFLA_LINKINFO')\
                        .get_attr('IFLA_INFO_DATA').get_attr('IFLA_VLAN_ID')
                else:
                    ifcs[link_name]['vlan'] = None
        return ifcs

    def find_unused_addr_and_add_to_ifc(self, ifc, cidr, offset=4, loc='top'):
        """ Finds an available address in the given subnet. nmap -PR is used to
        scan the subnet on the specified interface. Searching starts at either the
        top or the bottom of the subnet at an offset specified by offset.
        """
        status = False
        mult = 1 if loc == 'bot' else -1
        # check for an existing address on the interface in the subnet
        for addr in self.get_interface_addresses(ifc):
            if is_overlapping_addr(addr, cidr):
                status = True
                break

        if not status:
            # Find an available address on the subnet.
            # if no route exists, add one temporarily so the subnet can be scanned
            routes = self.get_interfaces_routes()
            if ifc not in routes or cidr not in routes[ifc]:
                self.route('add', dst=cidr,
                           oif=self.link_lookup(ifname=ifc)[0])
            # Get an address near the top of the subnet
            if loc == 'top':
                st_addr = add_offset_to_address(cidr, get_network_size(cidr) - offset)
            else:
                st_addr = add_offset_to_address(cidr, offset)
            for i in range(get_network_size(cidr) - offset):
                addr = add_offset_to_address(st_addr, mult * i)
                cmd = f'nmap -PR {addr}'
                res, err, rc = sub_proc_exec(cmd)
                if not re.search(r'\d+\.\d+\.\d+\.\d+', res, re.DOTALL):
                    # Found an unused address
                    # First remove the temp route
                    res = self.route('del', dst=cidr,
                                     oif=self.link_lookup(ifname=ifc)[0])
                    if res[0]['header']['error']:
                        self.log.error(f'Error occurred removing route from {ifc}')
                    # Add the address to the BMC interface
                    self.log.info(f'Adding address {addr} to ifc {ifc}')
                    idx = self.link_lookup(ifname=ifc)[0]
                    self.addr('add', index=idx, address=addr,
                              mask=int(cidr.rsplit('/')[1]))
                    status = True
                    break
        # Update self.ifcs
        self.ifcs = self.get_interfaces_dict()
        return status

    def get_interface_addresses(self, ifc):
        if ifc in self.ifcs:
            return self.ifcs[ifc]['addrs']
        else:
            return []

    def get_interface_for_route(self, route):
        """ Returns the interface which contains the specified route if it exists.
            else returns None.
        """
        routes = self.get_interfaces_routes()
        for ifc in routes:
            if route in routes[ifc]:
                return ifc

    def get_interfaces_routes(self):
        """ Get dictionary of ipv4 routes by interface. Keys are ifc names and values
        are tuple of routes in cidr format.
        """
        rts = {}
        routes = self.get_routes(family=2)  # get ipv4 routes
        for route in routes:
            if not route.get_attr('RTA_GATEWAY'):  # ipv4
                ifc_name = self.get_links(route.get_attr('RTA_OIF'))[0]\
                    .get_attr('IFLA_IFNAME')
                if ifc_name not in rts:
                    rts[ifc_name] = ()
                if route['dst_len'] != 32:
                    rts[ifc_name] += (route.get_attr('RTA_DST') +
                                      '/' + str(route['dst_len']),)
        return rts

    def is_route_overlapping(self, route_cidr, ifc_name):
        """ Returns the first found overlapping route if route_cidr overlaps
        any route on any interface excepting if the route already exists on ifc_name
        otherwise returns None
        """
        ifcs_routes = self.get_interfaces_routes()
        for ifc in ifcs_routes:
            for route in ifcs_routes[ifc]:
                if is_overlapping_addr(route_cidr, route):
                    if not (ifc_name == ifc and route_cidr == route):
                        return ifc

    def get_interfaces_names(self, _type='all', exclude=''):
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

    def get_up_interfaces_names(self, _type='all', exclude=''):
        """ Get list of interface names for 'UP' interfaces.
        Inputs:
            type (str): Interface type (ie 'phys', 'vlan', 'bridge', 'veth', 'tun')
            exclude (str): Name of an interface to exclude from the dictionary. This is
                           convienent when you want to check if another interface
                           is already using vlan number.
        """
        ifcs = []
        for ifc in self.ifcs:
            if ifc == exclude:
                continue
            if _type == 'all' or self.ifcs[ifc]['type'] == _type:
                if self.ifcs[ifc]['state'] == 'UP':
                    ifcs.append(ifc)
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
        try:
            vlan = int(vlan)
        except (ValueError, TypeError):
            return

        vlan_ifcs = self.get_vlan_interfaces(exclude=ifc)
        conflict_ifc = ''
        for _ifc in vlan_ifcs:
            if int(vlan) == vlan_ifcs[_ifc]:
                conflict_ifc = _ifc
                break
        return conflict_ifc

    def create_tagged_ifc(self, ifc, vlan):
        passed = True
        tagged_ifc_name = ifc + '.' + vlan
        if ifc not in self.ifcs.keys():
            self.log.error(f'Unable to create tagged interface {tagged_ifc_name} '
                           f'Non-existing interface: {ifc}')
            return False

        if not self.link_lookup(ifname=tagged_ifc_name):
            self.log.debug(f'Creating vlan interface: {tagged_ifc_name}')
            res = self.link("add", ifname=tagged_ifc_name, kind="vlan",
                            link=self.link_lookup(ifname=ifc)[0],
                            vlan_id=int(vlan))
            if res[0]['header']['error']:
                self.log.error(f'Error creating vlan interface: {ifc} {res}')
                passed = False
        if passed:
            self.link("set", index=self.link_lookup(ifname=tagged_ifc_name)[0],
                      state="up")
            if not self._wait_for_ifc_up(tagged_ifc_name):
                self.log.error('Failed to bring up interface {ifc} ')
                passed = False
        # Update the interfaces dict
        self.ifcs = self.get_interfaces_dict()
        return passed

    def _is_ifc_up(self, ifname):
        if 'UP' == self.get_links(
                self.link_lookup(ifname=ifname))[0].get_attr('IFLA_OPERSTATE'):
            return True
        return False

    def _wait_for_ifc_up(self, ifname, timespan=10):
        """ Waits up to timespan seconds for the specified interface to be up.
        Prints a message if the interface is not up in 2 seconds.
        Args:
            ifname (str) : Name of the interface
            timespan (int) : length of time to wait in seconds
        Returns:
            True if interface is up, False if not.
        """
        for t in range(2 * timespan):
            if t == 4:
                print(f'Waiting for interface {ifname} to come up.')
            if self._is_ifc_up(ifname):
                self.log.debug(f'Interface {ifname} is up.')
                return True
            time.sleep(0.5)
        self.log.info(f'Timeout waiting for interface {ifname} to come up.')
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
