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

# This script uses a remote proxy node to download RPM packages. It
# facilitates downloading of Red Hat packages for an architecture
# other than the machine you're running the script on. Repo access
# must already be enabled on the remote machine. This script
# does not set up repo access on the remote machine.
#
#  Usage: get-dependent-packages.sh [userid] [host]
#
# This scripts creates the ~/puptempdl directory on the remote node
# and installs the yum-utils utilities. Packages are downloaded
# to the ~/puptempdl directory and then scp copied to the ~/tempdl
# directory on this node. The ~/puptempdl directory and it's
# contents are removed from the remote node after copying.

set -e
cd "$(dirname "$0")"

if [[ -z $1 || -z $2 || -z $3 ]]; then
    echo 'usage: get-dependent-packages userid host arch'
    echo '       userid: username on remote node'
    echo '       host:   hostname of remote node'
    echo '       arch:   archtecture of remote node (p8/p9/x86_64)'
    exit
fi

if [[ "$3" == "p8" || "$3" == "p9" ]]; then
    pkglistfile='pkg-lists-wmla120.yml'
elif [[  "$3" == "x86_64" ]]; then
    pkglistfile='pkg-lists-wmla120_x86_64.yml'
fi

pkglist=$(python -c \
"import yaml;\
pkgs = yaml.full_load(open('$pkglistfile'));\
print(' '.join(pkgs['yum_pkgs_$3']))")

if [[ "$3" == "p8" ]]; then
versionless_pkglist=$(python - << "EOF"
import yaml
import re
pattern_basename = r'([-_+\w.]+)(?=-(\d+[:.]\d+){1,3}).+'
pkgs = yaml.full_load(open('pkg-lists-wmla120.yml'))
pkg_list = pkgs['yum_pkgs_p8']
pkg_basename = []
for pkg_name in pkg_list:
    res = re.search(pattern_basename, pkg_name)
    if res:
        bn = res.group(1)
        pkg_basename.append(bn)
print(' '.join(pkg_basename))
EOF
)
elif [[ "$3" == "p9" ]]; then
versionless_pkglist=$(python - << "EOF"
import yaml
import re
pattern_basename = r'([-_+\w.]+)(?=-(\d+[:.]\d+){1,3}).+'
pkgs = yaml.full_load(open('pkg-lists-wmla120.yml'))
pkg_list = pkgs['yum_pkgs_p9']
pkg_basename = []
for pkg_name in pkg_list:
    res = re.search(pattern_basename, pkg_name)
    if res:
        bn = res.group(1)
        pkg_basename.append(bn)
print(' '.join(pkg_basename))
EOF
)
elif [[ "$3" == "x86_64" ]]; then
versionless_pkglist=$(python - << "EOF"
import yaml
import re
pattern_basename = r'([-_+\w.]+)(?=-(\d+[:.]\d+){1,3}).+'
pkgs = yaml.full_load(open('pkg-lists-wmla120_x86_64.yml'))
pkg_list = pkgs['yum_pkgs_x86_64']
pkg_basename = []
for pkg_name in pkg_list:
    res = re.search(pattern_basename, pkg_name)
    if res:
        bn = res.group(1)
        pkg_basename.append(bn)
print(' '.join(pkg_basename))
EOF
)
fi

read -sp 'Enter password for '$1': ' PASSWORD
echo
export SSHPASS=$PASSWORD

if ! ssh-keygen -F $2 >/dev/null; then
    known_hosts="$HOME/.ssh/known_hosts"
    echo "Adding host key for '$2' to '$known_hosts'"
    ssh-keyscan $2 >> $known_hosts
fi

sshpass -e ssh -t $1@$2 'sudo yum -y install yum-utils'
echo
# Packages are saved to a different directory on this machine
# so that the packages are still present if you execute this
# script against the machine it's running on.

# Remove ~/tempdl to remove stray content and cause scp to copy
# files to it directly without creating puptempdl dir under it.
rm -rf ~/tempdl

sshpass -e ssh -t $1@$2 'mkdir -p ~/puptempdl && sudo yumdownloader \
    --archlist=`arch` --destdir ~/puptempdl '$pkglist

sshpass -e ssh -t $1@$2 'mkdir -p ~/puptempdl && sudo yumdownloader \
    --archlist=`arch` --destdir ~/puptempdl '$versionless_pkglist

echo Retrieving packages
sshpass -e scp -r $1@$2:~/puptempdl/ ~/tempdl

echo Remove remote directory
sshpass -e ssh $1@$2 'rm -rf ~/puptempdl'
