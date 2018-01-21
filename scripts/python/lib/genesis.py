# copyright 2018 IBM Corp.
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

from __future__ import nested_scopes, generators, division, absolute_import, \
    with_statement, print_function, unicode_literals

import sys
import platform
import os.path
import subprocess
import re
import yaml


GENESIS_DIR = 'cluster-genesis'
FILE_PATH = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser('~')
GEN_PATH = FILE_PATH[:1 + len(GENESIS_DIR) + FILE_PATH.find(GENESIS_DIR)]
GEN_SCRIPTS_PATH = os.path.join(GEN_PATH, 'scripts', '')
GEN_SCRIPTS_PYTHON_PATH = os.path.join(GEN_SCRIPTS_PATH, 'python', '')
GEN_PLAY_PATH = os.path.join(GEN_PATH, 'playbooks', '')
GEN_PASSIVE_PATH = os.path.join(GEN_PATH, 'passive', '')
GEN_LOGS_PATH = os.path.join(GEN_PATH, 'logs', '')
OPSYS = platform.dist()[0]
DEFAULT_CONTAINER_NAME = 'cluster-genesis'
CONTAINER_PACKAGE_PATH = '/opt/' + GENESIS_DIR
CONTAINER_ID_FILE = 'container'
VENV_DIR = 'gen-venv'
DEPLOYER_VENV_DIR = 'deployenv'
PYTHON_EXE = 'bin/python'
SCRIPTS_DIR = 'scripts'
PYTHON_DIR = 'python'
OS_IMAGES_DIR = 'os-images'
PLAYBOOKS_DIR = 'playbooks'
CONFIG_FILE = 'config.yml'
LXC_CONF_FILE_PATH = 'playbooks/lxc-conf.yml'
SSH_PRIVATE_KEY_FILE = os.path.expanduser('~/.ssh/gen')
SSH_PRIVATE_KEY_FILE_CONTAINER = '/root/.ssh/gen'
SSH_PUBLIC_KEY_FILE = SSH_PRIVATE_KEY_FILE + '.pub'
CFG_FILE_NAME = 'config.yml'
CFG_FILE = GEN_PATH + CFG_FILE_NAME
INV_FILE_NAME = 'inventory.yml'
INV_FILE = GEN_PATH + INV_FILE_NAME
LXC_DIR = os.path.expanduser('~/.local/share/lxc/')
ANSIBLE_PLAYBOOK = 'ansible-playbook'
POWER_TIME_OUT = 60
POWER_WAIT = 5
POWER_SLEEP_TIME = 2 * 60


def load_localhost(filename):
    try:
        return yaml.safe_load(open(filename))
    except:
        sys.exit('Could not load file: ' + filename)


def is_container_running():
    cont_running = False
    lxc_ls_output = subprocess.check_output(['bash', '-c', 'lxc-ls -f'])
    cont_running = re.search('^%s\d+\s+RUNNING' % (DEFAULT_CONTAINER_NAME + '-pxe'),
                             lxc_ls_output, re.MULTILINE)
    if cont_running:
        cont_running = True
    return cont_running


def container_addr():
    cont_address = None
    lxc_ls_output = subprocess.check_output(['bash', '-c', 'sudo lxc-ls -f'])
    cont_address = re.search('(\S+),\s+(\S+),', lxc_ls_output, re.MULTILINE)
    if cont_address is None:
        return None
    return cont_address.group(2)


def is_container():
    return os.path.isfile(os.path.join(
        CONTAINER_PACKAGE_PATH, CONTAINER_ID_FILE))


def get_container_package_path():
    return CONTAINER_PACKAGE_PATH


def get_container_id_file():
    return os.path.join(CONTAINER_PACKAGE_PATH, CONTAINER_ID_FILE)


def get_container_venv_path():
    return os.path.join(CONTAINER_PACKAGE_PATH, VENV_DIR)


def get_container_venv_python_exe():
    return os.path.join(CONTAINER_PACKAGE_PATH, VENV_DIR, PYTHON_EXE)


def get_container_scripts_path():
    return os.path.join(CONTAINER_PACKAGE_PATH, SCRIPTS_DIR)


def get_container_python_path():
    return os.path.join(CONTAINER_PACKAGE_PATH, SCRIPTS_DIR, PYTHON_DIR)


def get_container_os_images_path():
    return os.path.join(CONTAINER_PACKAGE_PATH, OS_IMAGES_DIR)


def get_container_playbooks_path():
    return os.path.join(CONTAINER_PACKAGE_PATH, PLAYBOOKS_DIR)


def get_package_path():
    if is_container():
        return get_container_package_path()
    return GEN_PATH


def get_scripts_path():
    if is_container():
        return get_container_scripts_path()
    return os.path.join(GEN_PATH, SCRIPTS_DIR)


def get_python_path():
    if is_container():
        return get_container_python_path()
    return os.path.join(GEN_PATH, SCRIPTS_DIR, PYTHON_DIR)


def get_ansible_playbook_path():
    return os.path.join(get_venv_path(), 'bin', ANSIBLE_PLAYBOOK)


def get_os_images_path():
    if is_container():
        return get_container_os_images_path()
    return os.path.join(GEN_PATH, OS_IMAGES_DIR)


def get_playbooks_path():
    if is_container():
        return get_container_playbooks_path()
    return os.path.join(GEN_PATH, PLAYBOOKS_DIR)


def get_lxc_conf_file_path():
    return os.path.join(GEN_PATH, LXC_CONF_FILE_PATH)


def get_config_file_name():
    return CONFIG_FILE


def get_ssh_private_key_file():
    if is_container():
        return SSH_PRIVATE_KEY_FILE_CONTAINER
    return SSH_PRIVATE_KEY_FILE


def get_ssh_public_key_file():
    return SSH_PUBLIC_KEY_FILE


def get_venv_path():
    if is_container():
        return get_container_venv_path()
    return os.path.join(GEN_PATH, DEPLOYER_VENV_DIR)


def get_power_time_out():
    return POWER_TIME_OUT


def get_power_wait():
    return POWER_WAIT


def get_power_sleep_time():
    return POWER_SLEEP_TIME


if os.path.isfile(GEN_PATH + "playbooks/host_vars/localhost"):
    localhost_content = load_localhost(GEN_PATH + "playbooks/host_vars/localhost")
    container_name = localhost_content['container_name']
