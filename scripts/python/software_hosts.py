#!/usr/bin/env python
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

from __future__ import nested_scopes, generators, division, absolute_import, \
    with_statement, print_function, unicode_literals

import click
import os.path
from os import listdir, mkdir, chown, chmod, getlogin
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

from inventory import generate_dynamic_inventory
from lib.exception import UserException
import lib.logger as logger
from lib.genesis import get_python_path, CFG_FILE, \
    get_dynamic_inventory_path, get_playbooks_path, get_ansible_path
from lib.utilities import bash_cmd, sub_proc_exec, heading1, get_selection, \
    bold, get_yesno, sub_proc_display, remove_line, append_line


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
# Global SSH logic credentials can be specified with [all:vars]
#   e.g.:
#   [all:vars]
#   ansible_ssh_private_key_file=~/.ssh/powerup
#   ansible_user=root
#   ansible_ssh_common_args='-o StrictHostKeyChecking=no'
#
# Group names are defined within brackets
# Hosts are defined with an FQDN or IP address
#   e.g.:
#   [master]
#   host1.domain.com  # master host1
#   192.168.1.21      # master host2
#
#   [worker]
#   host3.domain.com  # worker host1
#   192.168.1.22      # worker host2
#
# Localhost can be specified as:
#   localhost ansible_connection=local

[all:vars]

[master]
  # define first master host on this line before the "#"

[worker]
  # define first worker host on this line before the "#"
""")
    hosts = None
    while hosts is None:
        hosts = click.edit(hosts_template)
        if hosts is not None:
            with open(software_hosts_file_path, "w") as new_hosts_file:
                new_hosts_file.write(hosts)
        elif not click.confirm('File not written! Try again?'):
            return False
    return True


def _validate_inventory_count(software_hosts_file_path):
    """Validate > 0 hosts are defined in inventory
    Calls Ansible to process inventory which validates file syntax.

    Args:
        software_hosts_file_path (str): Path to software inventory file

    Returns:
        list: List of hosts defined in software inventory file

    Raises:
        UserException: Ansible reports host count of less than one
    """
    log = logger.getlogger()
    host_count = None
    host_list = []
    raw_host_list = bash_cmd('ansible all -i {} --list-hosts'
                             .format(software_hosts_file_path))

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
                if host_count < 1:
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

    # Ping IP
    try:
        bash_cmd('fping -u {}'.format(' '.join(host_list)))
    except CalledProcessError as exc:
        msg = "Ping failed on hosts:\n{}".format(exc.output)
        log.debug(msg)
        raise UserException(msg)
    log.debug("Software inventory host fping validation passed")
    return True


def _validate_ansible_ping(software_hosts_file_path):
    """Validate Ansible connectivity and functionality on all hosts

    Args:
        software_hosts_file_path (str): Path to software inventory file

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
        msg = 'Ansible ping validation failed:\n{}'.format(resp)
        log.debug(msg)
        raise UserException(msg)
    log.debug("Software inventory Ansible ping validation passed")
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
    default_ssh_key_name = "powerup"

    ssh_key_options = get_existing_ssh_key_pairs()

    if os.path.join(Path.home(), ".ssh",
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

    copy_ssh_key_pair_to_user(ssh_key)

    hosts_list = _validate_inventory_count(software_hosts_file_path)

    cmd = (f'ansible-inventory --inventory {software_hosts_file_path} --list')
    resp, err, rc = sub_proc_exec(cmd, shell=True)
    hostvars = json.loads(resp)['_meta']['hostvars']

    for host in hosts_list:
        cmd = (f'ssh-copy-id {hostvars[host]["ansible_user"]}@{host} '
               f'-i {ssh_key} ')
        if "ansible_port" in hostvars[host]:
            cmd += f'-p {hostvars[host]["ansible_port"]} '
        if "ansible_ssh_common_args" in hostvars[host]:
            cmd += f'{hostvars[host]["ansible_ssh_common_args"]} '

        rc = sub_proc_display(cmd)

    remove_line(software_hosts_file_path, '^ansible_ssh_private_key_file=.*')
    append_line(software_hosts_file_path, '[all:vars]')
    with open(software_hosts_file_path, 'r') as software_hosts_read:
        software_hosts = software_hosts_read.readlines()
    with open(software_hosts_file_path, 'w') as software_hosts_write:
        for line in software_hosts:
            if line.startswith("[all:vars]"):
                line = line + f'ansible_ssh_private_key_file={ssh_key}\n'
            software_hosts_write.write(line)


def get_existing_ssh_key_pairs():
    """Get a list of existing SSH private/public key paths from
    '~/.ssh/'. If called with 'sudo' then get list from both
    '/root/.ssh/' and '~/.ssh'.

    Returns:
        list of str: List of private ssh key paths
    """
    ssh_key_pairs = []

    ssh_dir = os.path.join(Path.home(), ".ssh")
    if os.path.isdir(ssh_dir):
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
        log.info(f'Creating SSH key \'{private_key_path}\'')
        cmd = ('ssh-keygen -t rsa -b 4096 '
               '-C "Generated by Power-Up Software Installer" '
               f'-f {private_key_path} -N ""')
        resp, err, rc = sub_proc_exec(cmd, shell=True)
        if str(rc) != "0":
            msg = 'ssh-keygen failed:\n{}'.format(resp)
            log.debug(msg)
            raise UserException(msg)
    return private_key_path


def copy_ssh_key_pair_to_user(private_key_path):
    """Copy an SSH private/public key pair into the user's ~/.ssh dir

    This function is useful when a key pair is created as root user
    (e.g. using 'sudo') but should also be available to the user for
    direct 'ssh' calls.

    If the private key is already in the user's ~/.ssh directory
    nothing is done.

    Args:
        private_key_path (str) : Filename of private key file
    """
    log = logger.getlogger()
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
        while os.path.isfile(user_private_key_path):
            # If key pair already exists no need to do anything
            if (filecmp.cmp(private_key_path, user_private_key_path) and
                    filecmp.cmp(public_key_path, user_public_key_path)):
                return
            else:
                user_private_key_path += "_powerup"
                user_public_key_path = user_private_key_path + '.pub'

        copyfile(private_key_path, user_private_key_path)
        copyfile(public_key_path, user_public_key_path)

        os.chown(user_private_key_path, user_uid, user_gid)
        os.chmod(user_private_key_path, 0o600)

        os.chown(user_public_key_path, user_uid, user_gid)
        os.chmod(user_public_key_path, 0o644)


def get_user_and_home():
    """Get user name and home directory path

    Returns the user account calling the script, *not* 'root' even
    when called with 'sudo'.

    Returns:
        user_name, user_home_dir (tuple): User name and home dir path

    Raises:
        UserException: If 'getent' command fails
    """
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
    # Validate file syntax and host count
    try:
        hosts_list = _validate_inventory_count(software_hosts_file_path)
    except UserException as exc:
        print("Inventory validation error: {}".format(exc))
        return False

    # Validate hostname resolution and network connectivity
    try:
        _validate_host_list_network(hosts_list)
    except UserException as exc:
        print("Inventory network validation error: {}".format(exc))
        return False

    # Validate complete Ansible connectivity
    try:
        _validate_ansible_ping(software_hosts_file_path)
    except UserException as exc:
        print("Inventory validation error:\n{}".format(exc))
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

    dynamic_inventory = _get_dynamic_inventory()

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
                print("Software inventory file not found.")
                if click.confirm('Do you want to create a new inventory from a template?'):
                    _create_new_software_inventory(software_hosts_file_path)
                elif click.confirm('Do you want to exit the program?'):
                    sys.exit(1)
                else:
                    continue

            # Print software inventory file contents
            if os.path.isfile(software_hosts_file_path):
                print("--------------------------------------------------")
                with open(software_hosts_file_path, 'r') as hosts_file:
                    print(hosts_file.read())
                print("--------------------------------------------------")
            # If still no software inventory file exists prompt user to
            # exit (else start over to create one).
            else:
                print("No inventory file found at '{}'"
                      .format(software_hosts_file_path))
                if click.confirm('Do you want to exit the program?'):
                    sys.exit(1)
                else:
                    continue

            # Menu items can modified to show validation results
            menu_items = ['Continue with current inventory',
                          'Edit inventory file',
                          'Exit program']

            # Validate software inventory
            print("Validating software inventory...")
            if validate_software_inventory(software_hosts_file_path):
                print(bold("Validation passed!"))
            else:
                print(bold("Validation FAILED!"))
                menu_items[0] = ("Continue with inventory as-is - "
                                 "WARNING: Validated failed")
                menu_items.insert(0, 'Configure SSH Keys')

            # Prompt user
            choice, item = get_selection(menu_items)
            print(f'Choice: {choice} Item: {item}')
            if item == 'Configure SSH Keys':
                configure_ssh_keys(software_hosts_file_path)
            elif item.startswith('Continue with'):
                print("Using '{}' as inventory"
                      .format(software_hosts_file_path))
                inventory_choice = software_hosts_file_path
                break
            elif item == 'Edit inventory file':
                click.edit(filename=software_hosts_file_path)
            elif item == 'Exit program':
                sys.exit(1)

    if inventory_choice is None:
        log.error("Software inventory file is required to continue!")
        sys.exit(1)
    log.debug("User software inventory choice: {}".format(inventory_choice))

    return inventory_choice


if __name__ == '__main__':
    logger.create()

    print(get_ansible_inventory())
