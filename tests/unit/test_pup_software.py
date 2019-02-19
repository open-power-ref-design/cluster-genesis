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
import importlib
import sys
from mock import patch as patch
import lib.genesis as gen
import lib.logger as logger


class TestScript(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestScript, self).__init__(*args, **kwargs)
        logger.create('nolog', 'info')
        self.logger = logger.getlogger()

    def setUp(self):
        super(TestScript, self).setUp()
        self.root_p = patch('os.geteuid')
        self.root = self.root_p.start()
        # Pass future root checks
        self.root.return_value = 0

    def tearDown(self):
        self.root_p.stop()

    #  @patch("software.wmla120.software")
    def test_software(self):
        arches = ("ppc64le", "x86_64")
        self.softwarename = "wmla120"
        # good path
        if gen.GEN_SOFTWARE_PATH not in sys.path:
            sys.path.append(gen.GEN_SOFTWARE_PATH)
        try:
            software_module = importlib.import_module(self.softwarename)
        except ImportError as exc:
            print(exc)
            sys.exit(1)
        for arch in arches:
            soft = software_module.software(False, False, arch)
            assert soft.arch == arch
        # test command line
