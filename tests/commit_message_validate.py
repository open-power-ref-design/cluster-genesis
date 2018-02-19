#!/usr/bin/env python
# Copyright 2017 IBM Corp.
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

import sys
import subprocess


def get_head_commit_message():
    return subprocess.check_output(['git', 'log', '-1', '--pretty=%B'])


valid_subject_tags = [
    'feat:', 'fix:', 'docs:', 'style:', 'refactor:', 'test:', 'chore:',
    'Revert', 'Merge']
no_errors = True
errors = []

for i, line in enumerate(get_head_commit_message().splitlines()):
    if i == 0:
        if line.split()[0] not in valid_subject_tags:
            no_errors = False
            errors.append("Subject line does not start with valid tag")
        if line.split()[0] not in ['Revert', 'Merge']:
            if line.split()[1][0].islower():
                no_errors = False
                errors.append("Subject line first word after tag is not "
                              "capitalized")
            if line.split()[-1][-1] == ".":
                no_errors = False
                errors.append("Subject line should not end with \".\"")
            if len(line) > 50:
                no_errors = False
                errors.append("Subject line > 50 characters long")
    elif i == 1:
        if line.strip() != '':
            no_errors = False
            errors.append("Line after subject should be blank")
    elif i > 1:
        if b".  " in line:
            no_errors = False
            errors.append("Body line #%d - period should be followed by "
                          "single space" % (i + 1))
        if len(line) > 72:
            no_errors = False
            errors.append("Body line #%d > 72 characters long" % (i + 1))

if no_errors:
    sys.exit(0)
else:
    for error in errors:
        print("Commit Message Style Error: %s" % error)
    sys.exit(1)
