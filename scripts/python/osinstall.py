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

import sys

import lib.logger as logger
from lib.utilities import Color

def osinstall(profile):
    c = Color()
    log = logger.getlogger()
    print(f'{c.blue}Installing OS{c.endc}')
    print(profile)
    log.info('log this')


if __name__ == '__main__':
    """Show status of the Cluster Genesis environment
    Args:
        INV_FILE (string): Inventory file.
        LOG_LEVEL (string): Log level.

    Raises:
       Exception: If parameter count is invalid.
    """

    logger.create('nolog', 'info')
    log = logger.getlogger()
    ARGV_MAX = 3
    ARGV_COUNT = len(sys.argv)
    if ARGV_COUNT > ARGV_MAX:
        try:
            raise Exception()
        except:
            log.error('Invalid argument count')
            sys.exit('Invalid argument count')

    osinstall()
