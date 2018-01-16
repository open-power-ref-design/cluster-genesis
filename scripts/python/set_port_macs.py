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

import lib.logger as logger
from lib.config import Config
from lib.inventory import Inventory
from lib.switch import SwitchFactory


def main():
    log = logger.getlogger()
    cfg = Config()
    inv = Inventory()

    macs = {}
    for sw_info in cfg.yield_sw_data_access_info():
        switch = SwitchFactory.factory(
            sw_info[1],
            sw_info[2],
            sw_info[3],
            sw_info[4],
            mode='active')
        port_to_macs = switch.show_mac_address_table(format='std')
        log.debug(
            (
                "Data switch port to MAC mapping - "
                "Switch: '{}', Class: '{}' - IP: '{}' - {}").format(
                    sw_info[0], sw_info[1], sw_info[2], port_to_macs))
        macs.update({sw_info[0]: port_to_macs})
    inv.add_macs_data(macs)


if __name__ == '__main__':
    logger.create()
    main()
