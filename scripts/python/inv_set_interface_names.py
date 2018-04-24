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

import sys

from lib.inventory import Inventory


def inv_set_interface_name(set_mac, set_name, config_path=None):
    """Set physical interface name

    Args:
        macs (str): Interface MAC address
        name (str): Device name
    """
    inv = Inventory(config_path)
    inv.set_interface_name(set_mac, set_name)


if __name__ == '__main__':
    """
    Arg1: Interface MAC address
    Arg2: Device name
    Arg3: config file path
    """

    if len(sys.argv) != 4:
        sys.exit('Invalid number of arguments.')

    inv_set_interface_name(sys.argv[1], sys.argv[2], sys.argv[3])
