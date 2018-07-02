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
virtualenv --no-wheel --system-site-packages ${1}pup-venv
source ${1}pup-venv/bin/activate
pip install \
    'ansible==2.5.2' \
    'orderedattrdict==1.5' \
    'pyroute2==0.5.0' \
    'jsonschema==2.6.0' \
    'jsl==0.2.4' \
    'pyghmi==1.0.42' \
    'wget==3.2' \
    'pyasn1==0.4.2' \
    'pysnmp==4.4.4' \
    'pyaml==17.12.1' \
    'paramiko==2.4.1' \
    'tabulate==0.8.2' \
    'gitpython==2.1.9'
deactivate
