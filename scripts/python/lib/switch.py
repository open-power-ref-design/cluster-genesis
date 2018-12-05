"""Switch configuration."""

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

from lib import lenovo
from lib import mellanox
from lib import cisco
from lib.exception import UserException
import lib.logger as logger

LOG = logger.getlogger()


class SwitchFactory(object):
    """Common switch configuration."""
    def __init__(self, switch_type=None, host=None, userid=None, password=None,
                 mode=None, outfile=None):
        pass

    @staticmethod
    def factory(switch_type=None, host=None, userid=None, password=None,
                mode='active', outfile='switch_cmds.txt'):
        """Return management switch model object.

        Args:
            inv (:obj:`Inventory`): Inventory object.
            switch_type (enum): Switch type.
            host (str): Switch ipv4 address
            userid (str): Switch userid. (This user must have configuration
                authority on the switch)
            password (str): Switch password.

        Raises:
            Exception: If management switch class is invalid.
        """
        if switch_type in 'lenovo Lenovo LENOVO':
            return lenovo.switch.factory(host, userid, password, mode, outfile)
        if switch_type in 'mellanox Mellanox MELLANOX':
            return mellanox.switch.factory(host, userid, password, mode, outfile)
        if switch_type in 'cisco Cisco CISCO':
            return cisco.switch.factory(host, userid, password, mode, outfile)
        msg = 'Invalid switch class'
        LOG.error(msg)
        raise UserException(msg)
