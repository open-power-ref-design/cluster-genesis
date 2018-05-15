#!/bin/bash
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

sudo -E -H pip install --upgrade virtualenv
virtualenv -p /usr/bin/python36 --no-wheel --system-site-packages ${1}pup-venv
source ${1}pup-venv/bin/activate
sudo python36 -m pip install \
    'ansible' \
    'orderedattrdict' \
    'pyroute2' \
    'jsonschema' \
    'jsl' \
    'pyghmi' \
    'wget' \
    'pyasn1' \
    'pysnmp' \
    'pyaml' \
    'pylxd' \
    'paramiko' \
    'tabulate' \
    'gitpython' \
    'netaddr' \
    'click'
deactivate
