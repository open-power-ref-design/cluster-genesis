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
sudo yum -y install python36
sudo python36 -m ensurepip --default-pip
source /etc/os-release

if [[ $ID == "ubuntu" ]]; then
    # Needs update for Python36
    sudo apt-get update
    sudo apt-get -y install python-pip python-dev libffi-dev libssl-dev \
    # sudo apt-get -y install python36-dev libffi-dev libssl-dev \
        python-netaddr ipmitool aptitude lxc vim vlan bridge-utils gcc cpp \
        python-tabulate fping g++ make unzip libncurses5 libncurses5-dev \
        sshpass

    if [[ $VERSION_ID == "14.04" ]]; then
        sudo apt-get -y install lxc-dev liblxc1
    elif [[ $VERSION_ID == "16.04" ]]; then
        sudo apt-get -y install python-lxc
    fi

elif [[ $ID == "rhel" ]]; then
    sudo yum -y install python2-pip python36-devel libffi-devel openssl-devel \
        lxc lxc-devel lxc-extra lxc-templates libvirt ipmitool \
        debootstrap gcc vim vlan bridge-utils cpp flex bison unzip cmake \
        fping gcc-c++ patch perl-ExtUtils-MakeMaker perl-Thread-Queue \
        ncurses-devel bash-completion yum-utils createrepo sshpass
    sudo systemctl start lxc.service
    sudo systemctl start libvirtd


else
    echo "Unsupported OS"
    exit 1
fi

sudo -E -H pip install --upgrade pip==18.0
sudo -E -H pip install --upgrade setuptools
sudo -E -H pip install --upgrade wheel

/bin/bash "${BASH_SOURCE%/*}/venv_install.sh"

# Create empty log file to ensure user is owner
if [ ! -d "logs" ]; then
    mkdir logs
    if [ ! -f logs/gen ]; then
        touch logs/gen
    fi
fi
