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
import pexpect
CMD = "pup software wmla120.py"
ALT_REPO = "NO_REPO"
YOURPASSWORD = "someveryimportantpassword"


class TestScript(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestScript, self).__init__(*args, **kwargs)
        logger.create('nolog', 'info')
        self.logger = logger.getlogger()
        self.arches = ("ppc64le", "x86_64")

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
        self.softwarename = "wmla120"
        # good path
        if gen.GEN_SOFTWARE_PATH not in sys.path:
            sys.path.append(gen.GEN_SOFTWARE_PATH)
        try:
            software_module = importlib.import_module(self.softwarename)
        except ImportError as exc:
            print(exc)
            sys.exit(1)
        for arch in self.arches:
            soft = software_module.software(False, False, arch)
            assert soft.arch == arch

    def test_cmd_line_prep_software(self):
        if YOURPASSWORD != "someveryimportantpassword":
            steps = ['conda_content_repo', 'ibmai_repo', 'conda_main_repo', 'conda_free_repo']
            tries = ("P")
            phase = " --prep "
            what_to_expect = ["password", "Sync Repo", "Create Repo", "Choice",
                              pexpect.EOF, "Recopy Anaconda content", "U: Copy from URL",
                              "Enter a selection"]
            # good path
            if gen.GEN_SOFTWARE_PATH not in sys.path:
                sys.path.append(gen.GEN_SOFTWARE_PATH)
            for step in steps:
                for arch in self.arches:
                    for _try in tries:
                        cmd = CMD + phase + " --arch {0} --step {1}".format(arch, step)
                        self.logger.info(cmd)
                        expect = pexpect.spawn(cmd, timeout=3600, maxread=10000)
                        i = expect.expect(what_to_expect)
                        if i == 0:
                            self.logger.info(expect.before)
                            expect.sendline(YOURPASSWORD)
                            i = expect.expect(what_to_expect)
                        if i == 1 or i == 2 or i == 5:
                            self.logger.info(expect.before)
                            sendthis = "y" if i == 5 else "Y"
                            self.logger.info("Sending: " + sendthis)
                            expect.sendline(sendthis)
                            i = expect.expect(what_to_expect)
                        if i == 6:
                            sendthis = "U"
                            self.logger.info("Sending: " + sendthis)
                            expect.sendline(sendthis)
                            i = expect.expect(what_to_expect)
                        if i == 3:
                            self.logger.info(expect.before)
                            self.logger.info("Sending: " + _try)
                            expect.sendline(_try)
                            i = expect.expect(what_to_expect)
                        if i == 7:
                            self.logger.info(expect.before)
                            sendthis = "1"
                            self.logger.info("Sending: " + sendthis)
                            expect.sendline(sendthis)
                            i = expect.expect(what_to_expect)
                        if i == 4:
                            self.logger.info(expect.before)
                            #  if _try == "A": # noqa: E116
                                #  expect.sendline('\x01\x011') # noqa: E116
                                #  i = expect.expect(["Enter URL:", "Sync Repo", "Choice"]) # noqa: E116
                                #  if i == 0: # noqa: E116
                                    #  expect.sendline(ALT_REPO) # noqa: E116
