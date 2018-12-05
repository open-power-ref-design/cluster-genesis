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
import re
from orderedattrdict import AttrDict
from pysnmp.hlapi import *

from lib.utilities import *

SNMP_PORT = 161
PUBLIC = 'public'
BRIDGE_MIB = 'BRIDGE-MIB'
DOT_1D_TP_FDB_PORT = 'dot1dTpFdbPort'


class GetMgmtSwitchConfig(object):
    def __init__(self, log):
        self.log = log

    def get_port_mac(self, rack, switch_mgmt_ipv4):
        self.mac_port = []
        for (
                error_indication,
                error_status,
                error_index,
                var_binds) in nextCmd(
                    SnmpEngine(),
                    CommunityData(PUBLIC),
                    UdpTransportTarget((switch_mgmt_ipv4, SNMP_PORT)),
                    ContextData(),
                    ObjectType(ObjectIdentity(BRIDGE_MIB, DOT_1D_TP_FDB_PORT)),
                    lexicographicMode=False):

            if error_indication:
                self.log.error(error_indication)
                sys.exit(1)
            elif error_status:
                self.log.error('%s at %s' % (
                    error_status.prettyPrint(),
                    error_index and var_binds[int(error_index) - 1][0] or '?'))
                sys.exit(1)
            else:
                _dict = AttrDict()
                for var_bind in var_binds:
                    match = re.search(
                        (r'^%s::%s\.(' +
                         '(%s)' +
                         ' = ' +
                         r'(\d+)$') % (
                             BRIDGE_MIB, DOT_1D_TP_FDB_PORT, PATTERN_MAC),
                        str(var_bind))
                    mac = match.group(1)
                    port = str(match.group(3))
                    _dict[port] = mac
                    self.log.info(
                        'Rack: %s - MAC: %s - port: %s' % (rack, mac, port))
                    self.mac_port.append(_dict)
        return self.mac_port
