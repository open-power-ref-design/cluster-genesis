#!/usr/bin/env python
"""Database"""

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

import os
import yaml
from orderedattrdict.yamlutils import AttrDictYAMLLoader

import lib.logger as logger
from lib.validate_config_schema import ValidateConfigSchema
from lib.validate_config_logic import ValidateConfigLogic
from lib.genesis import CFG_FILE
from lib.genesis import INV_FILE
from lib.exception import UserException


class Database(object):
    """Database """

    FILE_MODE = 0o666

    def __init__(self):
        self.log = logger.getlogger()
        self.cfg_file = os.path.realpath(CFG_FILE)
        self.cfg = None
        self.inv = None

        # If inventory file is broken link remove it
        if os.path.islink(INV_FILE):
            if not os.path.exists(os.readlink(INV_FILE)):
                os.unlink(INV_FILE)

        # Set 'inv_file' attribute after checking link
        self.inv_file = os.path.realpath(INV_FILE)

        # Create inventory file if it does not exist
        if not os.path.isfile(INV_FILE):
            os.mknod(INV_FILE, self.FILE_MODE)

    def _is_config_file(self, config_file):
        """ Check if config file exists

        Exception:
            If config file does not exist
        """

        if not os.path.isfile(config_file):
            msg = 'Could not find config file: ' + config_file
            self.log.error(msg)
            raise UserException(msg)

    def _load_yaml_file(self, yaml_file):
        """Load from YAML file

        Exception:
            If load from file fails
        """

        msg = "Failed to load '{}'".format(yaml_file)
        try:
            return yaml.load(open(yaml_file), Loader=AttrDictYAMLLoader)
        except yaml.parser.ParserError as exc:
            self.log.error("Failed to parse JSON '{}' - {}".format(
                yaml_file, exc))
            raise UserException(msg)
        except Exception as exc:
            self.log.error("Failed to load '{}' - {}".format(yaml_file, exc))
            raise UserException(msg)

    def _dump_yaml_file(self, yaml_file, content):
        """Dump to YAML file

        Exception:
            If dump to file fails
        """

        try:
            yaml.safe_dump(
                content,
                open(yaml_file, 'w'),
                indent=4,
                default_flow_style=False)
        except Exception as exc:
            self.log.error("Failed to dump inventory to '{}' - {}".format(
                yaml_file, exc))
            raise UserException("Failed to dump inventory to '{}'".format(
                yaml_file))

    def load_config(self):
        """Load config from database

        Returns:
            object: Config
        """

        self._is_config_file(self.cfg_file)
        self.cfg = self._load_yaml_file(self.cfg_file)
        return self.cfg

    def load_inventory(self):
        """Load inventory from database

        Returns:
            object: Inventory
        """

        self.inv = self._load_yaml_file(self.inv_file)
        return self.inv

    def dump_inventory(self, inv):
        """Dump inventory to database"""

        self.inv = inv
        self._dump_yaml_file(self.inv_file, inv)

    def validate_config(self, config_file):
        """Validate config"""

        if config_file is None:
            cfg_file = self.cfg_file
        else:
            cfg_file = os.path.realpath(config_file)

        self._is_config_file(cfg_file)
        self.cfg = self._load_yaml_file(cfg_file)

        schema = ValidateConfigSchema(self.cfg)
        schema.validate_config_schema()
        logic = ValidateConfigLogic(self.cfg)
        logic.validate_config_logic()
