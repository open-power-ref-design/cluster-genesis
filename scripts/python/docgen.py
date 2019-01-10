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
import yaml


def load_yaml(yaml_file):
    try:
        yaml_content = yaml.safe_load(open(yaml_file))
    except:
        print('Could not load file: ' + yaml_file)
        sys.exit(1)
    return yaml_content


def print_tasks(task_list, indent):
    for task in task_list:
        if 'name' in task:
            print("%s#. %s " % (indent, task['name']), end="")
        elif 'command' in task:
            print("%s#. " % indent, end="")
        elif 'shell' in task:
            print("%s#. " % indent, end="")
        else:
            print("%s#. Unnamed task " % indent, end="")
        if 'include' in task:
            print("")
            print("%s    * Include: %s" % (indent, task['include']))
            print_tasks(load_yaml(task['include']), "        ")
        else:
            for key in task:
                if type(task[key]) is dict:
                    print("\[%s]" % key)
                elif key in ("shell", "command"):
                    print("\[%s: %s]" % (key, task[key].rstrip()))


def print_play(yaml_file):
    yaml_content = load_yaml(yaml_file)

    for play in yaml_content:
        if 'include' in play:
            print("Include: %s" % play['include'])
            print("-" * (len(play['include']) + 9))
            print_play(play['include'].split()[0])
        else:
            if 'name' in play:
                print("Play: %s" % play['name'])
                print("-" * (len(play['name']) + 6))
            if 'hosts' in play:
                print("* Hosts: %s " % play['hosts'], end="")
            if 'gather_facts' in play:
                print("\[gather_facts: %s]" % play['gather_facts'])
            else:
                print("")
            if 'tasks' in play:
                print("")
                print_tasks(play['tasks'], "")
        print("")


for yaml_file in sys.argv[1:]:
    print("----\n")
    print("File: %s" % yaml_file)
    print("=" * (len(yaml_file) + 6))
    print_play(yaml_file)
