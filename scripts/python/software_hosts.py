#!/usr/bin/env python
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

from __future__ import nested_scopes, generators, division, absolute_import, \
    with_statement, print_function, unicode_literals

import click
import os.path
from os import listdir, getlogin, getuid
import filecmp
import json
import pwd
import grp
from shutil import copyfile
from pathlib import Path
import re
import netaddr
import socket
from subprocess import CalledProcessError
import sys
from getpass import getpass
from socket import gethostname, getfqdn

from inventory import generate_dynamic_inventory
from lib.exception import UserException
import lib.logger as logger
from lib.genesis import get_python_path, CFG_FILE, \
    get_dynamic_inventory_path, get_playbooks_path, get_ansible_path
from lib.utilities import bash_cmd, sub_proc_exec, heading1, get_selection, \
    bold, get_yesno, remove_line, append_line, rlinput


def _get_dynamic_inventory():
    log = logger.getlogger()
    dynamic_inventory = None
    config_pointer_file = get_python_path() + '/config_pointer_file'
    if os.path.isfile(config_pointer_file):
        with open(config_pointer_file) as f:
            config_path = f.read()
    else:
        config_path = CFG_FILE

    if os.path.isfile(config_path):
        try:
            dynamic_inventory = generate_dynamic_inventory()
        except UserException as exc:
            log.debug("UserException raised when attempting to generate "
                      "dynamic inventory: {}".format(exc))
    if dynamic_inventory is None:
        print("Dynamic inventory not found")
    return dynamic_inventory


def _expand_children(dynamic_inventory, children_list):
    """Replace each children item with expanded dictionary
    Args:
        dynamic_inventory (dict): Dynamic inventory dictionary
        children_list (list): List of children

    Returns:
        dict: Children dictionaries from dynamic inventory
    """
    children_dict = {}
    for child in children_list:
        children_dict[child] = dynamic_inventory[child]
        if 'children' in children_dict[child]:
            children_dict[child]['children'] = _expand_children(
                dynamic_inventory,
                children_dict[child]['children'])
    return children_dict


def _get_inventory_summary(dynamic_inventory, top_level_group='all'):
    """Get the Ansible inventory structured as a nested dictionary
    with a single top level group (default 'all').

    Args:
        dynamic_inventory (dict): Dynamic inventory dictionary
        top_level_group (str): Name of top level group

    Returns:
        dict: Inventory dictionary, including groups, 'hosts',
              'children', and 'vars'.
    """
    inventory_summary = {top_level_group: dynamic_inventory[top_level_group]}
    if 'children' in inventory_summary[top_level_group]:
        inventory_summary[top_level_group]['children'] = _expand_children(
            dynamic_inventory,
            inventory_summary[top_level_group]['children'])
    return inventory_summary


def _get_hosts_list(dynamic_inventory, top_level_group='all'):
    """Get a list of hosts.

    Args:
        dynamic_inventory (dict): Dynamic inventory dictionary
        top_level_group (str): Name of top level group

    Returns:
        list: List containing all inventory hosts
    """
    hosts_list = []
    if 'hosts' in dynamic_inventory[top_level_group]:
        hosts_list += dynamic_inventory[top_level_group]['hosts']
    if 'children' in dynamic_inventory[top_level_group]:
        for child in dynamic_inventory[top_level_group]['children']:
            hosts_list += _get_hosts_list(dynamic_inventory, child)
    return hosts_list


def _get_groups_hosts_dict(dynamic_inventory, top_level_group='all'):
    """Get a dictionary of groups and hosts. Hosts will be listed under
    their lowest level group membership only.

    Args:
        dynamic_inventory (dict): Dynamic inventory dictionary
        top_level_group (str): Name of top level group

    Returns:
        dict: Dictionary containing groups with lists of hosts
    """
    groups_hosts_dict = {}
    if 'hosts' in dynamic_inventory[top_level_group]:
        if top_level_group not in groups_hosts_dict:
            groups_hosts_dict[top_level_group] = []
        groups_hosts_dict[top_level_group] += (
            dynamic_inventory[top_level_group]['hosts'])
    if 'children' in dynamic_inventory[top_level_group]:
        for child in dynamic_inventory[top_level_group]['children']:
            groups_hosts_dict.update(_get_groups_hosts_dict(dynamic_inventory,
                                                            child))
    return groups_hosts_dict


def _get_groups_hosts_string(dynamic_inventory):
    """Get a string containing groups and hosts formatted in the
    Ansible inventory 'ini' style. Hosts will be listed under their
    lowest level group membership only.

    Args:
        dynamic_inventory (dict): Dynamic inventory dictionary

    Returns:
        str: String containing groups with lists of hosts
    """
    output_string = ""
    groups_hosts_dict = _get_groups_hosts_dict(dynamic_inventory)
    for host in groups_hosts_dict['all']:
        output_string += host + "\n"
    output_string += "\n"
    for group, hosts in groups_hosts_dict.items():
        if group != 'all':
            output_string += "[" + group + "]\n"
            for host in hosts:
                output_string += host + "\n"
            output_string += "\n"
    return output_string.rstrip()


def _create_new_software_inventory(software_hosts_file_path):
    hosts_template = ("""\
# Ansible Inventory File
#
# For detailed information visit:
#   http://docs.ansible.com/ansible/latest/user_guide/intro_inventory.html
#
# Only host definitions are required. SSH keys can be automatically
# configured by pup or manually defined in this file.
#
# POWER-Up uses ssh keys to access the client nodes. If there is an
# existing ssh key pair available, you may enter it under the [all:vars]
# section (eg; ansible_ssh_private_key_file=/root/.ssh/your-private-key).
# If one is not available, POWER-Up will generate one for you. POWER-Up
# also needs an active user id for the client nodes. The POWER-Up
# software will prompt for the user id, or you may enter it under the
# [all:vars] section below (eg; ansible_ssh_user=egoadmin).
#
# Global variables can be defined via the [all:vars] group
#   e.g.:
#   [all:vars]
#   ansible_ssh_user=egoadmin
#
# Group names are defined within brackets
# Hosts are defined with an FQDN or IP address
#   e.g.:
#   [master]
#   host1.domain.com  # master host
#
#   [compute]
#   host3.domain.com  # compute host 1
#   host4.domain.com  # compute host 2

[master]
  # define master host on this line before the "#"

[compute]
  # define first compute host on this line before the "#"

""")
    hosts = None
    while hosts is None:
        hosts = click.edit(hosts_template)
        if hosts is not None:
            with open(software_hosts_file_path, "w") as new_hosts_file:
                new_hosts_file.write(hosts)
        elif not click.confirm('File not written! Try again?'):
            return False

    _set_software_hosts_owner_mode(software_hosts_file_path)

    return True


def _set_software_hosts_owner_mode(software_hosts_file_path):
    """Set software_hosts file owner to "login" user

    Args:
        software_hosts_file_path (str): Path to software inventory file
    """
    user_name = getlogin()
    if getuid() == 0 and user_name != 'root':
        user_uid = pwd.getpwnam(user_name).pw_uid
        user_gid = grp.getgrnam(user_name).gr_gid
        os.chown(software_hosts_file_path, user_uid, user_gid)
        os.chmod(software_hosts_file_path, 0o644)


def _validate_inventory_count(software_hosts_file_path, min_hosts,
                              group='all'):
    """Validate minimum number of hosts are defined in inventory
    Calls Ansible to process inventory which validates file syntax.

    Args:
        software_hosts_file_path (str): Path to software inventory file
        min_hosts (int): Minimum number of hosts required to pass
        group (str, optional): Ansible group name (defaults to 'all')

    Returns:
        list: List of hosts defined in software inventory file

    Raises:
        UserException: Ansible reports host count of less than min_hosts
    """
    log = logger.getlogger()
    host_count = None
    host_list = []
    raw_host_list = bash_cmd(f'ansible {group} -i {software_hosts_file_path} '
                             '--list-hosts')

    # Iterate over ansible '--list-hosts' output
    count_verified = False
    host_count_pattern = re.compile(r'.*\((\d+)\)\:$')
    for host in raw_host_list.splitlines():
        if not count_verified:
            # Verify host count is > 0
            match = host_count_pattern.match(host)
            if match:
                host_count = int(match.group(1))
                log.debug("Ansible host count: {}".format(host_count))
                if host_count < min_hosts:
                    raise UserException("Ansible reporting host count of less "
                                        "than one ({})!".format(host_count))
                count_verified = True
        else:
            host_list.append(host.strip())

    log.debug("Software inventory host count validation passed")
    log.debug("Ansible host list: {}".format(host_list))
    return host_list


def _validate_host_list_network(host_list):
    """Validate all hosts in list are pingable

    Args:
        host_list (list): List of hostnames or IP addresses

    Returns:
        bool: True if all hosts are pingable

    Raises:
        UserException: If list item will not resolve or ping
    """
    log = logger.getlogger()
    for host in host_list:
        # Check if host is given as IP address
        if not netaddr.valid_ipv4(host, flags=0):
            try:
                socket.gethostbyname(host)
            except socket.gaierror as exc:
                log.debug("Unable to resolve host to IP: '{}' exception: '{}'"
                          .format(host, exc))
                raise UserException("Unable to resolve hostname '{}'!"
                                    .format(host))
        else:
            raise UserException('Client nodes must be defined using hostnames '
                                f'(IP address found: {host})!')

    # Ping IP
    try:
        bash_cmd('fping -u {}'.format(' '.join(host_list)))
    except CalledProcessError as exc:
        msg = "Ping failed on hosts:\n{}".format(exc.output)
        log.debug(msg)
        raise UserException(msg)
    log.debug("Software inventory host fping validation passed")
    return True


def _check_known_hosts(host_list):
    """Ensure all hosts have entries in 'known_hosts' to avoid
    Ansible's clunky yes/no prompting to accept keys (all prompts are
    printed at once).

    If any hosts are missing the user will be prompted to add it.

    Args:
        host_list (list): List of hostnames or IP addresses
    """
    known_hosts_files = [os.path.join(Path.home(), ".ssh", "known_hosts")]
    user_name, user_home_dir = get_user_and_home()
    if os.environ['USER'] == 'root' and user_name != 'root':
        known_hosts_files.append('/root/.ssh/known_hosts')
        if not os.path.isdir('/root/.ssh'):
            os.mkdir('/root/.ssh')
            os.chmod('/root/.ssh', 0o700)

    for host in host_list:
        for known_hosts in known_hosts_files:
            cmd = (f'ssh-keygen -F {host} -f {known_hosts}')
            resp, err, rc = sub_proc_exec(cmd)
            if rc != 0:
                cmd = (f'ssh-keyscan -H {host}')
                resp, err, rc = sub_proc_exec(cmd)
                print(f'Adding \'{host}\' host keys to \'{known_hosts}\'')
                append_line(known_hosts, resp, check_exists=False)


def _validate_ansible_ping(software_hosts_file_path, hosts_list):
    """Validate Ansible connectivity and functionality on all hosts

    Args:
        software_hosts_file_path (str): Path to software inventory file
        host_list (list): List of hostnames or IP addresses

    Returns:
        bool: True if Ansible can connect to all hosts

    Raises:
        UserException: If any host fails
    """
    log = logger.getlogger()
    cmd = ('{} -i {} -m ping all'.format(get_ansible_path(),
                                         software_hosts_file_path))
    resp, err, rc = sub_proc_exec(cmd)
    if str(rc) != "0":
        msg = f'Ansible ping validation failed:\n{resp}'
        log.debug(msg)
        if 'WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!' in msg:
            print(
                '@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@\n'
                '@    WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED      @\n'
                '@             ON ONE OR MORE CLIENT NODES!                @\n'
                '@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@\n'
                'IT IS POSSIBLE THAT SOMEONE IS DOING SOMETHING NASTY!\n'
                'Someone could be eavesdropping on you right now '
                '(man-in-the-middle attack)!\n'
                'It is also possible that a host key has just been changed.\n')
            if get_yesno('Remove the existing known host keys? '):
                known_hosts_files = (
                    [os.path.join(Path.home(), ".ssh", "known_hosts")])
                user_name, user_home_dir = get_user_and_home()
                if user_home_dir != str(Path.home()):
                    known_hosts_files.append(os.path.join(user_home_dir,
                                                          ".ssh", "known_hosts"))
                for host in hosts_list:
                    print(f'Collecting new host key(s) for {host}')
                    cmd = (f'ssh-keyscan -H {host}')
                    new_host_key, err, rc = sub_proc_exec(cmd)
                    for known_hosts in known_hosts_files:
                        print(f'Removing host keys for {host} '
                              f'from {known_hosts}')
                        cmd = (f'ssh-keygen -R {host} -f {known_hosts}')
                        resp, err, rc = sub_proc_exec(cmd)
                        print(f'Appending new host key for {host} to '
                              f'{known_hosts}')
                        append_line(known_hosts, new_host_key,
                                    check_exists=False)

                if user_home_dir != str(Path.home()):
                    user_known_hosts = os.path.join(user_home_dir, ".ssh",
                                                    "known_hosts")
                    user_uid = pwd.getpwnam(user_name).pw_uid
                    user_gid = grp.getgrnam(user_name).gr_gid
                    os.chown(user_known_hosts, user_uid, user_gid)
                    os.chmod(user_known_hosts, 0o600)
                    os.chown(user_known_hosts + '.old', user_uid, user_gid)
                    os.chmod(user_known_hosts + '.old', 0o600)

                return _validate_ansible_ping(software_hosts_file_path,
                                              hosts_list)
        elif 'Permission denied' in msg:
            print('"Permission denied" detected')
            if get_yesno('Configure Client Nodes for SSH Key Access? '):
                configure_ssh_keys(software_hosts_file_path)
                return _validate_ansible_ping(software_hosts_file_path,
                                              hosts_list)
        raise UserException(msg)
    log.debug("Software inventory Ansible ping validation passed")
    return True


def _validate_master_node_count(software_hosts_file_path, min_count,
                                max_count=0):
    """Validate number of nodes are defined in inventory's 'master'
    group. Either an exact or minimum count can be validated.

    Args:
        software_hosts_file_path (str): Path to software inventory file
        min_count (int): Minimum number of master nodes
        max_count (int, optional): Maximum number of master nodes. If
                                   set to 0 no maximum value is checked.

    Returns:
        bool: True validation passes

    Raises:
        UserException: Minimum or exact count is not present
    """
    host_count = len(_validate_inventory_count(software_hosts_file_path, 0,
                                               group='master'))

    if host_count < min_count:
        raise UserException(f'Inventory requires at least {min_count} master '
                            f'node(s) ({host_count} found)!')
    elif max_count != 0 and host_count > max_count:
        raise UserException(f'Inventory requires at most {max_count} master '
                            f'node(s) ({host_count} found)!')
    else:
        return True


def _validate_installer_is_not_client(host_list):
    """Validate the installer node is not listed as a client

    Args:
        host_list (list): List of hostnames

    Returns:
        bool: True validation passes

    Raises:
        UserException: If installer is listed as client
    """
    hostname = gethostname()
    fqdn = getfqdn()

    if hostname in host_list or fqdn in host_list:
        raise UserException('Installer can not be a target for install')
    else:
        return True


def _validate_client_hostnames(software_hosts_file_path, hosts_list):
    """Validate hostnames listed in inventory match client hostnames

    Args:
        software_hosts_file_path (str): Path to software inventory file
        host_list (list): List of hostnames or IP addresses

    Returns:
        bool: True if all client hostnames match

    Raises:
        UserException: If any hostname does not match
    """
    base_cmd = (f'{get_ansible_path()} -i {software_hosts_file_path} ')
    msg = ""

    for host in hosts_list:
        cmd = base_cmd + f'{host} -a "hostname --fqdn"'
        resp, err, rc = sub_proc_exec(cmd, shell=True)

        hostname = resp.splitlines()[-1]

        if hostname != host:
            msg += (f"Inventory hostname mis-match: '{host}' is reporting "
                    f"an FQDN of '{hostname}'\n")
    if msg != "":
        raise UserException(msg)
    else:
        return True


def configure_ssh_keys(software_hosts_file_path):
    """Configure SSH keys for Ansible software hosts

    Scan for SSH key pairs in home directory, and if called using
    'sudo' also in "login" user's home directory. Allow user to create
    a new SSH key pair if 'default_ssh_key_name' doesn't already exist.
    If multiple choices are available user will be prompted to choose.
    Selected key pair is copied into "login" user's home '.ssh'
    directory if necessary. Selected key pair is then copied to all
    hosts listed in 'software_hosts' file via 'ssh-copy-id', and
    finally assigned to the 'ansible_ssh_private_key_file' var in
    the 'software_hosts' '[all:vars]' section.

    Args:
        software_hosts_file_path (str): Path to software inventory file
    """
    log = logger.getlogger()
    default_ssh_key_name = "powerup"

    ssh_key_options = get_existing_ssh_key_pairs(no_root_keys=True)

    user_name, user_home_dir = get_user_and_home()
    if os.path.join(user_home_dir, ".ssh",
                    default_ssh_key_name) not in ssh_key_options:
        ssh_key_options.insert(0, 'Create New "powerup" Key Pair')

    if len(ssh_key_options) == 1:
        item = ssh_key_options[0]
    elif len(ssh_key_options) > 1:
        print(bold("\nSelect an SSH key to use:"))
        choice, item = get_selection(ssh_key_options)

    if item == 'Create New "powerup" Key Pair':
        ssh_key = create_ssh_key_pair(default_ssh_key_name)
    else:
        ssh_key = item

    ssh_key = copy_ssh_key_pair_to_user_dir(ssh_key)

    add_software_hosts_global_var(
        software_hosts_file_path,
        "ansible_ssh_common_args='-o StrictHostKeyChecking=no'")

    hostvars = get_ansible_hostvars(software_hosts_file_path)

    run = True
    while run:
        global_user = None
        global_pass = None
        header_printed = False
        header_msg = bold('\nGlobal client SSH login credentials required')
        for host in _validate_inventory_count(software_hosts_file_path, 0):
            if global_user is None and 'ansible_user' not in hostvars[host]:
                print(header_msg)
                header_printed = True
                global_user = rlinput('username: ')
                add_software_hosts_global_var(software_hosts_file_path,
                                              f'ansible_user={global_user}')
            if (global_pass is None and
                    'ansible_ssh_pass' not in hostvars[host]):
                if not header_printed:
                    print(header_msg)
                global_pass = getpass('password: ')
            if global_user is not None and global_pass is not None:
                break
        heading1("Copying SSH Public Keys to Hosts\n")
        rc = copy_ssh_key_pair_to_hosts(ssh_key, software_hosts_file_path,
                                        global_pass)
        if not rc:
            log.warning("One or more SSH key copy failed!")
            choice, item = get_selection(['Retry', 'Continue', 'Exit'])
            if choice == "1":
                pass
            elif choice == "2":
                run = False
            elif choice == "3":
                log.debug('User chooses to exit.')
                sys.exit('Exiting')
        else:
            print()
            log.info("SSH key successfully copied to all hosts\n")
            run = False

    add_software_hosts_global_var(software_hosts_file_path,
                                  f'ansible_ssh_private_key_file={ssh_key}')


def add_software_hosts_global_var(software_hosts_file_path, entry):
    """Copy an SSH public key into software hosts authorized_keys files

    Add entry to software_hosts '[all:vars]' section. Any existing
    entries with the same key name (string before '=') will be
    overwritten.

    Args:
        software_hosts_file_path (str): Path to software inventory file
        entry (str) : Entry to write in software_hosts '[all:vars]'
    """
    remove_line(software_hosts_file_path, '^ansible_ssh_private_key_file=.*')

    append_line(software_hosts_file_path, '[all:vars]')

    with open(software_hosts_file_path, 'r') as software_hosts_read:
        software_hosts = software_hosts_read.readlines()

    in_all_vars = False
    prev_line = "BOF"
    with open(software_hosts_file_path, 'w') as software_hosts_write:
        for line in software_hosts:
            if line.startswith("[all:vars]"):
                if prev_line != "\n":
                    line = "\n" + line
                line = line + f'{entry}\n'
                in_all_vars = True
            elif in_all_vars and line.startswith('['):
                in_all_vars = False
            elif in_all_vars and line.startswith(entry.split('=')[0]):
                continue
            software_hosts_write.write(line)
            prev_line = line
    _set_software_hosts_owner_mode(software_hosts_file_path)


def get_existing_ssh_key_pairs(no_root_keys=False):
    """Get a list of existing SSH private/public key paths from
    '~/.ssh/'. If called with 'sudo' and 'no_root_keys=False', then get
    list from both '/root/.ssh/' and '~/.ssh'. If 'no_root_keys=True'
    then any private keys located in '/root/.ssh' will be omitted.

    Args:
        no_root_keys (bool): Do not return any keys from '/root/.ssh'

    Returns:
        list of str: List of private ssh key paths
    """
    ssh_key_pairs = []

    ssh_dir = os.path.join(Path.home(), ".ssh")
    if (not ('/root' == str(Path.home()) and no_root_keys) and
            os.path.isdir(ssh_dir)):
        for item in listdir(ssh_dir):
            item = os.path.join(ssh_dir, item)
            if os.path.isfile(item + '.pub'):
                ssh_key_pairs.append(item)

    user_name, user_home_dir = get_user_and_home()
    if user_home_dir != str(Path.home()):
        user_ssh_dir = os.path.join(user_home_dir, ".ssh")
        if os.path.isdir(user_ssh_dir):
            for item in listdir(user_ssh_dir):
                item = os.path.join(user_ssh_dir, item)
                if os.path.isfile(item + '.pub'):
                    ssh_key_pairs.append(item)

    return ssh_key_pairs


def create_ssh_key_pair(name):
    """Create an SSH private/public key pair in ~/.ssh/

    If an SSH key pair exists with "name" then the private key path is
    returned *without* creating anything new.

    Args:
        name (str): Filename of private key file

    Returns:
        str: Private ssh key path

    Raises:
        UserException: If ssh-keygen command fails
    """
    log = logger.getlogger()
    ssh_dir = os.path.join(Path.home(), ".ssh")
    private_key_path = os.path.join(ssh_dir, name)
    if not os.path.isdir(ssh_dir):
        os.mkdir(ssh_dir, mode=0o700)
    if os.path.isfile(private_key_path):
        log.info(f'SSH key \'{private_key_path}\' already exists, continuing')
    else:
        print(bold(f'Creating SSH key \'{private_key_path}\''))
        cmd = ('ssh-keygen -t rsa -b 4096 '
               '-C "Generated by Power-Up Software Installer" '
               f'-f {private_key_path} -N ""')
        resp, err, rc = sub_proc_exec(cmd, shell=True)
        if str(rc) != "0":
            msg = 'ssh-keygen failed:\n{}'.format(resp)
            log.debug(msg)
            raise UserException(msg)
    return private_key_path


def copy_ssh_key_pair_to_user_dir(private_key_path):
    """Copy an SSH private/public key pair into the user's ~/.ssh dir

    This function is useful when a key pair is created as root user
    (e.g. using 'sudo') but should also be available to the user for
    direct 'ssh' calls.

    If the private key is already in the user's ~/.ssh directory
    nothing is done.

    Args:
        private_key_path (str) : Filename of private key file

    Returns:
        str: Path to user copy of private key
    """
    public_key_path = private_key_path + '.pub'

    user_name, user_home_dir = get_user_and_home()
    user_ssh_dir = os.path.join(user_home_dir, ".ssh")

    if user_ssh_dir not in private_key_path:
        user_private_key_path = os.path.join(
            user_ssh_dir, os.path.basename(private_key_path))
        user_public_key_path = user_private_key_path + '.pub'
        user_uid = pwd.getpwnam(user_name).pw_uid
        user_gid = grp.getgrnam(user_name).gr_gid

        if not os.path.isdir(user_ssh_dir):
            os.mkdir(user_ssh_dir, mode=0o700)
            os.chown(user_ssh_dir, user_uid, user_gid)

        # Never overwrite an existing private key file!
        already_copied = False
        while os.path.isfile(user_private_key_path):
            # If key pair already exists no need to do anything
            if (filecmp.cmp(private_key_path, user_private_key_path) and
                    filecmp.cmp(public_key_path, user_public_key_path)):
                already_copied = True
                break
            else:
                user_private_key_path += "_powerup"
                user_public_key_path = user_private_key_path + '.pub'

        if already_copied:
            print(f'\'{private_key_path}\' already copied to '
                  f'\'{user_private_key_path}\'')
        else:
            print(bold(f'Copying \'{private_key_path}\' to '
                       f'\'{user_private_key_path}\' for unprivileged use'))
            copyfile(private_key_path, user_private_key_path)
            copyfile(public_key_path, user_public_key_path)

            os.chown(user_private_key_path, user_uid, user_gid)
            os.chmod(user_private_key_path, 0o600)

            os.chown(user_public_key_path, user_uid, user_gid)
            os.chmod(user_public_key_path, 0o644)

    else:
        user_private_key_path = private_key_path

    return user_private_key_path


def copy_ssh_key_pair_to_hosts(private_key_path, software_hosts_file_path,
                               global_pass=None):
    """Copy an SSH public key into software hosts authorized_keys files

    TODO: detailed description

    Args:
        private_key_path (str) : Filename of private key file
        software_hosts_file_path (str): Path to software inventory file
        global_pass (str, optional): Global client default SSH password

    Returns:
        bool: True iff rc of all commands are "0"
    """
    hosts_list = _validate_inventory_count(software_hosts_file_path, 0)
    all_zero_returns = True

    hostvars = get_ansible_hostvars(software_hosts_file_path)

    for host in hosts_list:
        print(bold(f'Copy SSH Public Key to {host}'))
        cmd = f'ssh-copy-id -i {private_key_path} '
        if "ansible_port" in hostvars[host]:
            cmd += f'-p {hostvars[host]["ansible_port"]} '
        if "ansible_ssh_common_args" in hostvars[host]:
            cmd += f'{hostvars[host]["ansible_ssh_common_args"]} '
        cmd += f'{hostvars[host]["ansible_user"]}@{host}'

        if 'ansible_ssh_pass' not in hostvars[host]:
            cmd = f'SSHPASS=\'{global_pass}\' sshpass -e ' + cmd

        resp, err, rc = sub_proc_exec(cmd, shell=True)
        if rc != 0:
            all_zero_returns = False
            print(err)

    return all_zero_returns


def get_ansible_hostvars(software_hosts_file_path):
    """Get Ansible generated 'hostvars' dictionary

    Args:
        software_hosts_file_path (str): Path to software inventory file

    Returns:
        dict: Ansible 'hostvars' dictionary
    """
    cmd = (f'ansible-inventory --inventory {software_hosts_file_path} --list')
    resp, err, rc = sub_proc_exec(cmd, shell=True)
    hostvars = json.loads(resp)['_meta']['hostvars']
    return hostvars


def get_user_and_home():
    """Get user name and home directory path

    Returns the user account calling the script, *not* 'root' even
    when called with 'sudo'.

    Returns:
        user_name, user_home_dir (tuple): User name and home dir path

    Raises:
        UserException: If 'getent' command fails
    """
    log = logger.getlogger()
    user_name = getlogin()

    cmd = f'getent passwd {user_name}'
    resp, err, rc = sub_proc_exec(cmd, shell=True)
    if str(rc) != "0":
        msg = 'getent failed:\n{}'.format(err)
        log.debug(msg)
        raise UserException(msg)
    user_home_dir = resp.split(':')[5].rstrip()

    return (user_name, user_home_dir)


def validate_software_inventory(software_hosts_file_path):
    """Validate Ansible software inventory

    Args:
        software_hosts_file_path (str): Path to software inventory file

    Returns:
        bool: True is validation passes
    """
    try:
        # Validate file syntax and host count
        hosts_list = _validate_inventory_count(software_hosts_file_path, 1)

        # Validate installer is not in inventory
        _validate_installer_is_not_client(hosts_list)

        # Validate hostname resolution and network connectivity
        _validate_host_list_network(hosts_list)

        # Validate  master node count is exactly 1
        _validate_master_node_count(software_hosts_file_path, 1, 1)

        # Ensure hosts keys exist in known_hosts
        _check_known_hosts(hosts_list)

        # Validate complete Ansible connectivity
        _validate_ansible_ping(software_hosts_file_path, hosts_list)

        # Validate hostnames listed in inventory match client hostnames
        _validate_client_hostnames(software_hosts_file_path, hosts_list)

    except UserException as exc:
        print("Inventory validation error: {}".format(exc))
        return False

    # If no exceptions were caught validation passed
    return True


def get_ansible_inventory():
    log = logger.getlogger()
    inventory_choice = None
    dynamic_inventory_path = get_dynamic_inventory_path()
    software_hosts_file_path = (
        os.path.join(get_playbooks_path(), 'software_hosts'))

    heading1("Software hosts inventory setup\n")

    dynamic_inventory = None

    # If dynamic inventory contains clients prompt user to use it
    if (dynamic_inventory is not None and
            len(set(_get_hosts_list(dynamic_inventory)) -
                set(['deployer', 'localhost'])) > 0):
        print("Ansible Dynamic Inventory found:")
        print("--------------------------------")
        print(_get_groups_hosts_string(dynamic_inventory))
        print("--------------------------------")
        validate_software_inventory(dynamic_inventory)
        if click.confirm('Do you want to use this inventory?'):
            print("Using Ansible Dynamic Inventory")
            inventory_choice = dynamic_inventory_path
        else:
            print("NOT using Ansible Dynamic Inventory")

    # If dynamic inventory has no hosts or user declines to use it
    if inventory_choice is None:
        while True:
            # Check if software inventory file exists
            if os.path.isfile(software_hosts_file_path):
                print("Software inventory file found at '{}':"
                      .format(software_hosts_file_path))
            # If no software inventory file exists create one using template
            else:
                rlinput("Press enter to create client node inventory")
                _create_new_software_inventory(software_hosts_file_path)

            # If still no software inventory file exists prompt user to
            # exit (else start over to create one).
            if not os.path.isfile(software_hosts_file_path):
                print("No inventory file found at '{}'"
                      .format(software_hosts_file_path))
                if click.confirm('Do you want to exit the program?'):
                    sys.exit(1)
                else:
                    continue

            # Menu items can modified to show validation results
            continue_msg = 'Continue with current inventory'
            edit_msg = 'Edit inventory file'
            exit_msg = 'Exit program'
            ssh_config_msg = 'Configure Client Nodes for SSH Key Access'
            menu_items = []

            # Validate software inventory
            inv_count = len(_validate_inventory_count(software_hosts_file_path,
                                                      0))
            print(f'Validating software inventory ({inv_count} nodes)...')
            if validate_software_inventory(software_hosts_file_path):
                print(bold("Validation passed!"))
            else:
                print(bold("Unable to complete validation"))
                continue_msg = ("Continue with inventory as-is - "
                                "WARNING: Validation incomplete")
                menu_items.append(ssh_config_msg)

            # Prompt user
            menu_items += [continue_msg, edit_msg, exit_msg]
            choice, item = get_selection(menu_items)
            print(f'Choice: {choice} Item: {item}')
            if item == ssh_config_msg:
                configure_ssh_keys(software_hosts_file_path)
            elif item == continue_msg:
                print("Using '{}' as inventory"
                      .format(software_hosts_file_path))
                inventory_choice = software_hosts_file_path
                break
            elif item == edit_msg:
                click.edit(filename=software_hosts_file_path)
            elif item == exit_msg:
                sys.exit(1)

    if inventory_choice is None:
        log.error("Software inventory file is required to continue!")
        sys.exit(1)
    log.debug("User software inventory choice: {}".format(inventory_choice))

    return inventory_choice


if __name__ == '__main__':
    logger.create()

    print(get_ansible_inventory())
