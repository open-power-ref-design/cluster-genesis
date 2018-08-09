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
cd ~
if [[ -z $1 || -z $2 ]]; then
    echo 'usage: get-dependent-packages userid host'
    exit
fi

echo 'Enter password for '$1
read -s PASSWORD

export SSHPASS=$PASSWORD

sshpass -e ssh -t $1@$2 'ls'

user=$(whoami)
sshpass -e ssh -t $1@$2 'sudo yum install yum-utils'

sshpass -e scp /home/$user/power-up/software/dependent-packages-paie11.list $1@$2:/home/$1/dependent-packages-paie11.list

sshpass -e ssh -t customer@9.3.3.47 'mkdir -p tempdl && sudo yumdownloader --resolve --archlist=ppc64le --destdir tempdl $(tr "\n" " " < dependent-packages-paie11.list)'

sshpass -e scp -r customer@9.3.3.47:/home/customer/tempdl/ .
