#!/bin/bash
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

set -e

PIP_SOURCE=""
INSTALL_DIR=""
while getopts d:p: option; do
    case "${option}" in
        d) INSTALL_DIR="${OPTARG}";;
        p) PIP_SOURCE="--no-index --find-links=file://${OPTARG} ";;
    esac
done

python3.6 -m venv ${INSTALL_DIR}pup-venv
source ${INSTALL_DIR}pup-venv/bin/activate
python3.6 -m pip install $PIP_SOURCE --upgrade pip
python3.6 -m pip install $PIP_SOURCE --upgrade setuptools==41.1.0
python3.6 -m pip install $PIP_SOURCE -r ${INSTALL_DIR}requirements.txt
deactivate
