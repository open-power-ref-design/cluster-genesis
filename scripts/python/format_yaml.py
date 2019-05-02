#!/usr/bin/env python3
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
import os.path
import yaml
from orderedattrdict.yamlutils import AttrDictYAMLLoader


def abs_path(file_):
    return os.path.abspath(
        os.path.dirname(os.path.abspath(file_)) +
        os.path.sep +
        os.path.basename(file_))


if len(sys.argv) != 3:
    try:
        raise Exception()
    except:
        print('Invalid argument count')
        sys.exit(1)

YAML_IN_FILE = abs_path(sys.argv[1])
YAML_OUT_FILE = abs_path(sys.argv[2])

try:
    CONTENT = yaml.full_load(open(YAML_IN_FILE), Loader=AttrDictYAMLLoader)
except:
    print('Could not load file: ' + YAML_IN_FILE)
    sys.exit(1)

try:
    yaml.safe_dump(
        CONTENT,
        open(YAML_OUT_FILE, 'w'),
        indent=4,
        default_flow_style=False)
except:
    print('Could not dump file: ' + YAML_OUT_FILE)
    sys.exit(1)
