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
rhel_docker_ce_repo="[docker]
name=Docker
baseurl=http://ftp.unicamp.br/pub/ppc64el/rhel/7/docker-ppc64el/
enabled=1
gpgcheck=0"
MESSAGES=''

add_message () {
    echo "$@"
    if [[ $MESSAGES != '' ]]; then
        MESSAGES+=$'\n'
    fi
    MESSAGES+="$@"
}


if [[ $ID == "ubuntu" ]]; then
    # Needs update for Python36
    sudo apt-get update
    sudo apt-get -y install libffi-dev libssl-dev python3-dev \
        python-netaddr ipmitool aptitude vim vlan bridge-utils gcc cpp \
        python-tabulate fping g++ make unzip libncurses5 libncurses5-dev \
        sshpass dnsmasq nmap

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
        openssl-devel tcpdump dnsmasq nmap
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
    MESSAGE="WARNING: User '$USER' was added to the 'docker' group. Please "
    MESSAGE+="logout and log back in to enable access to Docker services."
    add_message $MESSAGE
fi

net_ipv4_conf='net.ipv4.conf.all.forwarding'
ipv4_forwarding=$(/sbin/sysctl $net_ipv4_conf)
sysctl_docker='/usr/lib/sysctl.d/99-docker.conf'

if [[ $ipv4_forwarding == "net.ipv4.conf.all.forwarding = 0" ]]; then
    echo "IPV4 forwarding OFF"

    if ! ls $sysctl_docker &>/dev/null; then
        echo "Creating $sysctl_docker"
        touch $sysctl_docker
        chmod 644 $sysctl_docker
    fi

    if ! grep $net_ipv4_conf $sysctl_docker &>/dev/null; then
        echo "Adding '$net_ipv4_conf=1' to $sysctl_docker"
        echo "$net_ipv4_conf=1" >> $sysctl_docker
    elif grep "$net_ipv4_conf=0" $sysctl_docker &>/dev/null; then
        echo -n "Replacing '$net_ipv4_conf=0' with '$net_ipv4_conf=1' in "
        echo "$sysctl_docker"
        sed -i "s/$net_ipv4_conf=0/$net_ipv4_conf=1/" $sysctl_docker
    fi

    docker_ps=$(docker ps)
    if [[ "$docker_ps" = *$'\n'* ]]; then
        echo
        echo    "The following Docker containers are running:"
        echo    "$docker_ps"
        echo
        echo    "Is it OK to stop all containers and restart Docker service?"
        read -p "(y/n)? " -r
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            restart_docker=true
        else
            restart_docker=false
        fi
    else
        restart_docker=true
    fi
    if [ "$restart_docker" = true ]; then
        sudo systemctl restart docker
    else
        MESSAGE="WARNING: Docker service needs to be restarted to enable IPV4"
        MESSAGE+=" forwarding!"
        add_message $MESSAGE
    fi

    ipv4_forwarding=$(/sbin/sysctl $net_ipv4_conf)
    if [[ $ipv4_forwarding == "net.ipv4.conf.all.forwarding = 0" ]]; then
        MESSAGE="ERROR: Unable to enable IPV4 forwarding! Ensure '/sbin/sysctl"
        MESSAGE+=" $net_ipv4_conf' is set to '1'"
        add_message $MESSAGE
    fi
fi

/bin/bash "${BASH_SOURCE%/*}/venv_install.sh"

# Create empty log file to ensure user is owner
if [ ! -d "logs" ]; then
    mkdir logs
    if [ ! -f logs/gen ]; then
        touch logs/gen
    fi
fi

# Display any messages
if [[ $MESSAGES != '' ]]; then
    echo $'\nThe following issues were encountered during installation:'
    echo "$MESSAGES"
fi
