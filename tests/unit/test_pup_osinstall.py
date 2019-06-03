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


import unittest
from mock import patch as patch
from lib import utilities as util
GOOD_NMAP_OUTPUT = """[sudo] password for jja:
Starting Nmap 6.40 ( http://nmap.org ) at 2019-01-23 13:33 EST
Pre-scan script results:
| broadcast-dhcp-discover:
|   IP Offered: 192.168.12.249
|   DHCP Message Type: DHCPOFFER
|   Server Identifier: 192.168.12.2
|   IP Address Lease Time: 0 days, 0:02:00
|   Renewal Time Value: 0 days, 0:01:00
|   Rebinding Time Value: 0 days, 0:01:45
|   Subnet Mask: 255.255.255.0
|   Broadcast Address: 192.168.12.255
|   Domain Name Server: 192.168.12.2
|_  Router: 192.168.12.3
WARNING: No targets were specified, so 0 hosts scanned.
Nmap done: 0 IP addresses (0 hosts up) scanned in 3.07 seconds"""

BAD_NMAP_OUTPUT = """
Starting Nmap 6.40 ( http://nmap.org ) at 2019-01-23 15:17 EST
WARNING: No targets were specified, so 0 hosts scanned.
Nmap done: 0 IP addresses (0 hosts up) scanned in 10.15 seconds
"""


class TestScript(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestScript, self).__init__(*args, **kwargs)

    def setUp(self):
        super(TestScript, self).setUp()
        self.root_p = patch('os.geteuid')
        self.root = self.root_p.start()
        # Pass future root checks
        self.root.return_value = 0

    def tearDown(self):
        self.root_p.stop()

    @patch("lib.utilities.get_dhcp_servers")
    @patch("lib.utilities.bash_cmd")
    def test_has_dhcp_servers(self, mock_get, mock_cmd):
        mock_cmd.return_value = GOOD_NMAP_OUTPUT
        device = "ent1"
        # good path
        dct = util.parse_dhcp_servers(GOOD_NMAP_OUTPUT)
        assert "DHCP Message Type" in dct and dct["DHCP Message Type"] == "DHCPOFFER"
        dct = util.parse_dhcp_servers(BAD_NMAP_OUTPUT)
        assert "DHCP Message Type" not in dct
        # bad path
        dct = util.get_dhcp_servers(device)
        assert mock_cmd.called_once_with(device)
        # erroneous device ... not found
        util.has_dhcp_servers(device)
        assert mock_get.called_once_with(device)
