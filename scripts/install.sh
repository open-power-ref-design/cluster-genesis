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
source /etc/os-release
arch=$(uname -m)
is_p9=$(lscpu|grep POWER9) || true

add_message () {
    echo "$@"
    if [[ $MESSAGES != '' ]]; then
        MESSAGES+=$'\n'
    fi
    MESSAGES+="$@"
}

PIP_SOURCE=""
while getopts p: option; do
    case "${option}" in
        p) PIP_SOURCE="-p ${OPTARG}";;
    esac
done

if [[ $ID == "ubuntu" ]]; then
    # Needs update for Python36
    sudo apt-get update
    sudo apt-get -y install libffi-dev libssl-dev python3-dev \
        python-netaddr ipmitool aptitude vim vlan bridge-utils gcc cpp \
        python-tabulate fping g++ make unzip libncurses5 libncurses5-dev \
        sshpass dnsmasq nmap xorriso

elif [[ $ID == "rhel" ]]; then
    sudo yum --setopt=skip_missing_names_on_install=False -y install \
        $(cat yum-requirements.txt)

    # Needed for OSinstall, but not currently available on P9
    # if [[ -z "$is_p9" ]]; then
    #     sudo yum -y install syslinux-tftpboot
    # fi

    sudo python36 -m ensurepip --default-pip
fi

/bin/bash -c "${BASH_SOURCE%/*}/venv_install.sh $PIP_SOURCE"

# Create empty log file to ensure user is owner
if [ ! -d "logs" ]; then
    mkdir logs
    if [ ! -f logs/gen ]; then
        touch logs/gen
    fi
fi

# Create empty ansible.log file to ensure user is owner
if [ ! -f playbooks/ansible.log ]; then
    touch playbooks/ansible.log
fi

# Display any messages
if [[ $MESSAGES != '' ]]; then
    echo $'\nThe following issues were encountered during installation:'
    echo "$MESSAGES"
fi
