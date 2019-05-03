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

import argparse
import os
import re
import lib.genesis as gen
import yaml
# import code

import lib.logger as logger


def ipmi_fru2dict(fru_str):
    """Convert the ipmitool fru output to a dictionary. The function first
        convert the input string to yaml, then yaml load is used to create a
        dictionary.
    Args:
        fru_str (str): Result of running 'ipmitool fru'
    returns: A dictionary who's keys are the FRUs
    """
    yaml_data = []
    lines = string.splitlines()
    for i, line in enumerate(lines):
        # Strip out any excess white space (including tabs) around the ':'
        line = re.sub(r'\s*:\s*', ': ', line)
        # Check for blank lines
        if re.search(r'^\s*$', line):
            yaml_data.append(line)
            continue
        if i < len(lines) - 1:
            # If indentation is increasing on the following line, then convert
            # the current line to a dictionary key.
            indent = re.search(r'[ \t]*', line).span()[1]
            next_indent = re.search(r'[ \t]*', lines[i + 1]).span()[1]
            if next_indent > indent:
                line = re.sub(r'\s*:\s*', ':', line)
                # if ':' in middle of line take the second half, else
                # take the beginning
                if line.split(':')[1]:
                    line = line.split(':')[1]
                else:
                    line = line.split(':')[0]
                yaml_data.append(line + ':')
            else:
                split = line.split(':', 1)
                # Add quotes around the value to handle non alphanumerics
                line = split[0] + ': "' + split[1] + '"'
                yaml_data.append(line)
    yaml_data = '\n'.join(yaml_data)
    return yaml.full_load(yaml_data)


def _get_system_sn_pn(ipmi_fru_str):
    fru_item = _get_system_info(ipmi_fru_str)
    fru_item = fru_item[list(fru_item.keys())[0]]

    return (fru_item['Chassis Serial'].strip(),
            fru_item['Chassis Part Number'].strip())


def _get_system_info(ipmi_fru_str):
    yaml_dict = ipmi_fru2dict(string)
    fru_item = ''
    for item in yaml_dict:
        for srch_item in ['NODE', 'SYS', 'Backplane', 'MP', 'Mainboard']:
            # code.interact(banner='There', local=dict(globals(), **locals()))
            if srch_item in item:
                fru_item = yaml_dict[item]
                break
        if fru_item:
            fru_item = {item: fru_item}
            break
    if not fru_item:
        fru_item = yaml_dict
        # fru_item = yaml_dict[list(yaml_dict.keys())[0]]
    return fru_item


def main(string):

    sys_info = _get_system_info(string)

#    print(sys_info)
#    print()

    for item in sys_info:
        print(item)
        for thing in sys_info[item]:
            print(f'{thing}: {sys_info[item][thing]}')

    print()
    sn, pn = _get_system_sn_pn(string)
    print(sn, pn)


if __name__ == '__main__':
    """Simple python template
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('arg1', help='Help me Rhonda')
#    parser.add_argument('arg2', choices=['apple', 'banana', 'peach'],
#                        help='Pick a fruit')
    parser.add_argument('--print', '-p', dest='log_lvl_print',
                        help='print log level', default='info')
    parser.add_argument('--file', '-f', dest='log_lvl_file',
                        help='file log level', default='info')
    args = parser.parse_args()

    logger.create('nolog', 'info')
    log = logger.getlogger()

    if args.log_lvl_print == 'debug':
        print(args)

    path = os.path.join(gen.GEN_PATH, args.arg1)

    with open(path, 'r') as f:
        string = f.read()

    main(string)
