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
import subprocess
from datetime import datetime
import re


def get_changed_files():
    return subprocess.check_output(['git', 'diff', 'HEAD~', '--name-only',
                                    '--diff-filter=d']).decode("utf-8")


current_year = str(datetime.today().year)

no_errors = True
errors = []

for changed_file in get_changed_files().splitlines():
    with open(changed_file, 'r') as f:
        for line in f:
            match = re.search(r"Copyright (\d{4}) IBM", line)
            if match:
                if match and match.group(1) != current_year:
                    no_errors = False
                    errors.append("%s: \"%s\"" % (changed_file, line.rstrip()))

if no_errors:
    sys.exit(0)
else:
    for error in errors:
        print("Outdated copyright year in file %s" % error)
    sys.exit(1)
