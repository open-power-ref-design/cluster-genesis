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
source /etc/os-release
arch=$(uname -m)
rhel_docker_ce_repo="[docker]
name=Docker
baseurl=http://ftp.unicamp.br/pub/ppc64el/rhel/7/docker-ppc64el/
enabled=1
gpgcheck=0"

if [[ $ID == "ubuntu" ]]; then
    # Needs update for Python36
    sudo apt-get update
    sudo apt-get -y install libffi-dev libssl-dev python3-dev \
        python-netaddr ipmitool aptitude vim vlan bridge-utils gcc cpp \
        python-tabulate fping g++ make unzip libncurses5 libncurses5-dev \
        sshpass

    if ! type "docker"; then
        sudo apt-get -y install \
        apt-transport-https ca-certificates curl software-properties-common
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
            sudo apt-key add -
        sudo apt-key fingerprint 0EBFCD88
        if [ $(uname -m) = "x86_64" ]; then
            sudo add-apt-repository \
                "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
                $(lsb_release -cs) \
                stable"
        elif [ $(uname -m) = "ppc64le" ]; then
            sudo add-apt-repository \
                "deb [arch=ppc64el] https://download.docker.com/linux/ubuntu \
                $(lsb_release -cs) \
                stable"
        fi
        sudo apt-get update
        sudo apt-get -y install docker-ce
    fi

elif [[ $ID == "rhel" ]]; then
    sudo yum -y install python36-devel libffi-devel ipmitool debootstrap gcc \
        vim bridge-utils cpp flex bison unzip cmake fping gcc-c++ patch \
        perl-ExtUtils-MakeMaker perl-Thread-Queue ncurses-devel \
        bash-completion yum-utils createrepo sshpass python-tabulate \
        openssl-devel tcpdump
    sudo python36 -m ensurepip --default-pip

    if ! type "docker"; then
        sudo yum -y install device-mapper-persistent-data lvm2
        if [ $(uname -m) = "x86_64" ]; then
            sudo yum-config-manager \
                --add-repo \
                https://download.docker.com/linux/centos/docker-ce.repo
            sudo yum -y install container-selinux
        elif [ $(uname -m) = "ppc64le" ]; then
            echo "$rhel_docker_ce_repo" | \
                sudo tee /etc/yum.repos.d/docker.repo > /dev/null
        fi
        sudo yum makecache fast
        sudo yum -y install docker-ce
        sudo systemctl start docker.service
        sudo systemctl enable docker.service
    fi
fi

if ! docker container ls &> /dev/null; then
    sudo usermod -aG docker $USER  # user needs to logout & login
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
