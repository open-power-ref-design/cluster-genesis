#!/usr/bin/env python3
"""Validate config"""

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

from lib.logger import Logger
from lib.db import Database


class ValidateConfig(object):
    """Validate config

    Args:
        log (object): Log
    """

    def __init__(self, log=None):
        pass

    def validate_config(self):
        """Validate config"""

        dbase = Database()
        dbase.validate_config()


if __name__ == '__main__':
    VAL_CFG = ValidateConfig(Logger(Logger.LOG_NAME))
    VAL_CFG.validate_config()
