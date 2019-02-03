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
from tests.unit import (TOP_DIR, SCRIPT_DIR)
import lib.logger as logger
import shutil
import tarfile as t
import os
from archive.bundle import bundle_this, bundle_extract, archive_this, unarchive_this
import tempfile

LOG = logger.getlogger()
COMPRESS_FORMAT = "gz"
COMPRESS_DIR = [TOP_DIR + '/' "scripts/", TOP_DIR + '/' "docs/"]
OUTPUT_DIR = "/tmp/823fFFAREa_1928/"
if os.path.isdir(OUTPUT_DIR):
    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)

os.makedirs(OUTPUT_DIR)
OUTPUT_FILE = "/tmp/somefile"


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

    def test_tar_files(self):
        exclude = ['scripts/python/lib/db.py',
                   "scripts/python/lib/lenovo.py"]

        # Good path
        fileobj = tempfile.NamedTemporaryFile()
        try:
            LOG.info(fileobj.name)
            fileobj = archive_this(SCRIPT_DIR, fileObj=fileobj,
                                   exclude=exclude, compress=True)
            with tempfile.TemporaryDirectory() as tmpdirname:
                # make sure exclude files does not exist
                with t.open(fileobj.name, "r:gz") as tar:
                    assert tar.name not in exclude
                try:
                    unarchive_this(fileobj.name, tmpdirname)
                except Exception as e:
                    LOG.error("Uncaught exception as e {0}".format(e))
                    raise e
        except Exception as e:
            LOG.error("Uncaught exception: {0}".format(e))
            raise e
        finally:
            if fileobj is not None:
                fileobj.close()

        fileobj = tempfile.NamedTemporaryFile()
        try:
            cmd = "python {0} bundle --to {1}".format(SCRIPT_DIR + "/archive/bundle.py", fileobj.name)
            output = util.bash_cmd(cmd)
            LOG.info(output)
            with tempfile.TemporaryDirectory() as tmpdirname:
                with t.open(fileobj.name, "r") as tar:
                    assert tar.name
                try:
                    unarchive_this(fileobj.name, tmpdirname)
                except Exception as e:
                    LOG.error("Uncaught exception as e {0}".format(e))
                    raise e
        except Exception as e:
            LOG.error("{0}".format(e))
            raise e
        finally:
            if fileobj is not None:
                fileobj.close()
        fileobj = tempfile.NamedTemporaryFile()
        try:
            LOG.info(fileobj.name)
            bundle_this(SCRIPT_DIR, fileobj.name)
            with tempfile.TemporaryDirectory() as tmpdirname:
                # make sure exclude files does not exist
                with t.open(fileobj.name, "r") as tar:
                    assert tar.name not in exclude
                try:
                    bundle_extract(fileobj.name, tmpdirname)
                except Exception as e:
                    LOG.error("Uncaught exception as e {0}".format(e))
                    raise e
        except Exception as e:
            LOG.error("Uncaught exception: {0}".format(e))
            raise e
        finally:
            if fileobj is not None:
                fileobj.close()

        #  Bad path
