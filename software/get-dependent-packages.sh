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

set -e
cd ~
if [[ -z $1 || -z $2 ]]; then
    echo 'usage: get-dependent-packages userid host'
    exit
fi

#echo 'Enter password for '$1
read -sp 'Enter password for '$1': ' PASSWORD
echo
export SSHPASS=$PASSWORD

user=$(whoami)
sshpass -e ssh -t $1@$2 'sudo yum -y install yum-utils'

sshpass -e scp /home/$user/power-up/software/dependent-packages-paie11.list \
    $1@$2:/home/$1/dependent-packages-paie11.list

sshpass -e ssh -t $1@$2 'mkdir -p tempdl && sudo yumdownloader --archlist=ppc64le \
    --resolve --destdir tempdl $(tr "\n" " " < dependent-packages-paie11.list)'

sshpass -e scp -r $1@$2:/home/customer/tempdl/ ~

sshpass -e ssh $1@$2 'rm -rf tempdl/ && rm dependent-packages-paie11.list'
