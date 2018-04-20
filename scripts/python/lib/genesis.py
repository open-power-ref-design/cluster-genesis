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


PROJECT_NAME = "power-up"
HOME = os.path.expanduser('~')
GEN_PATH = (os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../")) + "/")
GEN_SCRIPTS_PATH = os.path.join(GEN_PATH, 'scripts', '')
GEN_SCRIPTS_PYTHON_PATH = os.path.join(GEN_SCRIPTS_PATH, 'python', '')
GEN_PLAY_PATH = os.path.join(GEN_PATH, 'playbooks', '')
GEN_PASSIVE_PATH = os.path.join(GEN_PATH, 'passive', '')
GEN_LOGS_PATH = os.path.join(GEN_PATH, 'logs', '')
OPSYS = platform.dist()[0]
DEFAULT_CONTAINER_NAME = PROJECT_NAME
CONTAINER_PACKAGE_PATH = '/opt/' + PROJECT_NAME
CONTAINER_ID_FILE = 'container'
VENV_DIR = 'pup-venv'
DEPLOYER_VENV_DIR = 'pup-venv'
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
COBBLER_INSTALL_DIR = '/opt/cobbler'
COBBLER_USER = 'cobbler'
COBBLER_PASS = 'cobbler'
DHCP_POOL_START = 21


class Color:
    black = '\033[90m'
    red = '\033[91m'
    green = '\033[92m'
    yellow = '\033[93m'
    blue = '\033[94m'
    purple = '\033[95m'
    cyan = '\033[96m'
    white = '\033[97m'
    bold = '\033[1m'
    underline = '\033[4m'
    sol = '\033[1G'
    clr_to_eol = '\033[K'
    clr_to_bot = '\033[J'
    scroll_five = '\n\n\n\n\n'
    scroll_ten = '\n\n\n\n\n\n\n\n\n\n'
    up_one = '\033[1A'
    up_five = '\033[5A'
    up_ten = '\033[10A'
    header1 = '          ' + bold + underline
    endc = '\033[0m'


def load_localhost(filename):
    try:
        return yaml.safe_load(open(filename))
    except:
        sys.exit('Could not load file: ' + filename)


def get_symlink_path():
    from lib.config import Config
    cfg = Config()
    cont_vlan = str(cfg.get_depl_netw_client_vlan(if_type='pxe')[0])
    file_name = INV_FILE_NAME.replace('.', cont_vlan + '.')
    return os.path.join(GEN_PATH, file_name)


def get_symlink_realpath():
    return os.path.realpath(get_symlink_path())


def get_inventory_realpath():
    # If called inside a POWER_Up container, return the path to the inventory.yml
    # file.  If callled outside the container, returns the realpath of the
    # inventory.yml file corresponding to the active container.
    if is_container():
        return INV_FILE
    return os.path.realpath(get_symlink_path())


def get_container_name():
    from lib.config import Config
    cfg = Config()
    cont_vlan = str(cfg.get_depl_netw_client_vlan(if_type='pxe')[0])
    return DEFAULT_CONTAINER_NAME + '-pxe' + cont_vlan


def is_container_running():
    cont_running = False
    lxc_ls_output = subprocess.check_output(['bash', '-c', 'lxc-ls -f'])
    lxc_ls_output_search = re.search('^%s\d+\s+RUNNING' %
                                     (DEFAULT_CONTAINER_NAME + '-pxe'),
                                     lxc_ls_output, re.MULTILINE)
    if lxc_ls_output_search is not None:
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


def get_project_name():
    return PROJECT_NAME


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


def get_cobbler_install_dir():
    return COBBLER_INSTALL_DIR


def get_cobbler_user():
    return COBBLER_USER


def get_cobbler_pass():
    return COBBLER_PASS


def get_dhcp_pool_start():
    return DHCP_POOL_START


def check_os_profile(profile):
    ubuntu_lts_pointers = {
        "ubuntu-14.04-server-amd64": "ubuntu-14.04.5-server-amd64",
        "ubuntu-14.04-server-ppc64el": "ubuntu-14.04.5-server-ppc64el",
        "ubuntu-16.04-server-amd64": "ubuntu-16.04.4-server-amd64",
        "ubuntu-16.04-server-ppc64el": "ubuntu-16.04.4-server-ppc64el"}
    if profile in list(ubuntu_lts_pointers):
        return ubuntu_lts_pointers[profile]
    else:
        return profile


if os.path.isfile(GEN_PATH + "playbooks/host_vars/localhost"):
    localhost_content = load_localhost(GEN_PATH + "playbooks/host_vars/localhost")
    container_name = localhost_content['container_name']
