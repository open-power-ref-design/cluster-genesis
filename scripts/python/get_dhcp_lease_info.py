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

import os.path
import re
from orderedattrdict import AttrDict

import lib.logger as logger
from lib.exception import UserException


class GetDhcpLeases(object):
    def __init__(self, dhcp_leases_file):
        dhcp_leases_file = os.path.abspath(
            os.path.dirname(os.path.abspath(dhcp_leases_file)) +
            os.path.sep +
            os.path.basename(dhcp_leases_file))
        log = logger.getlogger()

        try:
            fds = open(dhcp_leases_file, 'r')
        except:
            msg = 'DHCP leases file not found: %s'
            log.error(msg % (dhcp_leases_file))
            raise UserException(msg % dhcp_leases_file)
        self.mac_ip = AttrDict()
        for line in fds:
            match = re.search(
                r'^\S+\s+(\S+)\s+(\S+)',
                line)
            mac = match.group(1)
            ipaddr = match.group(2)
            self.mac_ip[mac] = ipaddr
            log.debug('Lease found - MAC: %s - IP: %s' % (mac, ipaddr))

    def get_mac_ip(self):
        return self.mac_ip
