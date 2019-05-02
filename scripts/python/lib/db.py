#!/usr/bin/env python3
"""Database"""

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

import os
import yaml
from orderedattrdict.yamlutils import AttrDictYAMLLoader

import lib.logger as logger
from lib.validate_config_schema import ValidateConfigSchema
from lib.validate_config_logic import ValidateConfigLogic
from lib.exception import UserException
import lib.genesis as gen


class DatabaseConfig(object):
    """Database """

    FILE_MODE = 0o666

    def __init__(self, cfg_file):
        self.log = logger.getlogger()

        self.cfg_file = cfg_file

        self.cfg = None
        self.inv = None

    def _is_config_file(self, config_file):
        """ Check if config file exists

        Exception:
            If config file does not exist
        """

        if not os.path.isfile(config_file):
            if os.path.isfile(os.path.join(gen.GEN_PATH, config_file)):
                self.cfg = os.path.join(gen.GEN_PATH, config_file)
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
            return yaml.full_load(open(yaml_file), Loader=AttrDictYAMLLoader)
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

    def validate_config(self):
        """Validate config"""

        self._is_config_file(self.cfg_file)
        self.cfg = self._load_yaml_file(self.cfg_file)

        schema = ValidateConfigSchema(self.cfg)
        schema.validate_config_schema()
        logic = ValidateConfigLogic(self.cfg)
        logic.validate_config_logic()


class DatabaseInventory(object):
    """Database """

    FILE_MODE = 0o666

    def __init__(self, inv_file=None, cfg_file=None):
        self.log = logger.getlogger()

        if inv_file:
            self.inv_file = os.path.realpath(inv_file)
        else:
            symlink_path = gen.get_symlink_path(cfg_file)
            if os.path.islink(symlink_path):
                if not os.path.exists(os.readlink(symlink_path)):
                    os.unlink(symlink_path)
            self.inv_file = gen.get_inventory_realpath(cfg_file)

        self.inv = None

        # Create inventory file if it does not exist
        if not os.path.isfile(self.inv_file):
            os.mknod(self.inv_file, self.FILE_MODE)

    def _load_yaml_file(self, yaml_file):
        """Load from YAML file

        Exception:
            If load from file fails
        """

        msg = "Failed to load '{}'".format(yaml_file)
        try:
            return yaml.full_load(open(yaml_file), Loader=AttrDictYAMLLoader)
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

    def __del__(self):
        if (os.path.isfile(self.inv_file) and
                os.stat(self.inv_file).st_size == 0):
            os.remove(self.inv_file)
