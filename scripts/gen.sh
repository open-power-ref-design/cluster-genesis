#!/bin/bash
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

if [[ "$1" == "setup" ]] && [[ "$2" == "--bridges" ]]; then
    sudo env "PATH=$PATH" gen.py $@
    exit
fi

if [[ "$1" == "validate" ]] && [[ "$2" == "--cluster-hardware" ]]; then
    sudo env "PATH=$PATH" gen.py $@
    exit
fi

if [[ "$1" == "deploy" ]]; then
    gen.py validate --config-file
    if [ $? -ne 0 ]; then
        exit
    fi
    sudo env "PATH=$PATH" gen.py setup --bridges
    if [ $? -ne 0 ]; then
        exit
    fi
    gen.py config --mgmt-switches
    if [ $? -ne 0 ]; then
        exit
    fi
    # sudo env "PATH=$PATH" gen.py validate --cluster-hardware
    gen.py config --create-container cluster-genesis
    if [ $? -ne 0 ]; then
        exit
    fi
    exit
fi

gen.py $@
