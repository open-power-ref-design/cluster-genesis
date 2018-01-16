#!/usr/bin/env python
"""Cluster Genesis 'gen' command"""

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

import os
import sys
import getpass

import enable_deployer_networks
import validate_cluster_hardware
import configure_mgmt_switches
import configure_data_switches
import download_os_images
import lxc_conf
import lib.argparse_gen as argparse_gen
import lib.logger as logger
import lib.genesis as gen
from lib.db import Database
from lib.exception import UserException


class Gen(object):
    """Cluster Genesis 'gen' command

    Args:
        log(object): log
    """

    ROOTUSER = 'root'

    def __init__(self, args):
        self.args = args

    def _check_root_user(self, cmd):
        if getpass.getuser() != self.ROOTUSER:
            print(
                "Fail: '%s %s ...' should be run as root" %
                (sys.argv[0], cmd),
                file=sys.stderr)
            sys.exit(1)

    def _check_non_root_user(self, cmd):
        if getpass.getuser() == self.ROOTUSER:
            print(
                "Fail: '%s %s ...' should not be run as root" %
                (sys.argv[0], cmd),
                file=sys.stderr)
            sys.exit(1)

    def _config_mgmt_switches(self):
        try:
            configure_mgmt_switches.configure_mgmt_switches()
        except UserException as exc:
            print('Error occured while configuring managment switches: \n' +
                  exc)
            sys.exit(1)

    def _create_bridges(self):
        enable_deployer_networks.enable_deployer_network()

    def _create_container(self):
        from lib.container import Container

        cont = Container(self.args.create_container)
        try:
            cont.check_permissions(getpass.getuser())
        except UserException as exc:
            print('Fail:', exc, file=sys.stderr)
            sys.exit(1)
        try:
            conf = lxc_conf.LxcConf()
            conf.create()
        except Exception as exc:
            print("Fail:", exc, file=sys.stderr)
            sys.exit(1)
        try:
            cont.create()
        except UserException as exc:
            print('Fail:', exc, file=sys.stderr)
            sys.exit(1)
        print('Success: Created container')

    def _config_file(self):
        dbase = Database()
        try:
            dbase.validate_config(self.args.config_file)
        except UserException as exc:
            print('Fail:', exc.message, file=sys.stderr)
            sys.exit(1)
        print('Success: Config file validation passed')

    def _cluster_hardware(self):
        print('\nDiscovering and validating cluster hardware')
        val = validate_cluster_hardware.ValidateClusterHardware()
        try:
            val.validate_mgmt_switches()
        except UserException as exc:
            print(exc)
            sys.exit(1)

        try:
            val.validate_data_switches()
        except UserException as exc:
            print(exc)
            print('Warning. Cluster Genesis can continue with deployment, but')
            print('network configuration will not succeed until issues are resolved')

        try:
            val.validate_ipmi()
        except UserException as exc:
            print(exc)
            print('Warning. Cluster Genesis can continue with deployment, but')
            print('Not all nodes will be deployed at this time')

        try:
            val.validate_pxe(self.args.cluster_hardware)
        except UserException as exc:
            print(exc)
            print('Warning. Cluster Genesis can continue with deployment, but')
            print('Not all nodes will be deployed at this time')

    def _create_inventory(self):
        from lib.container import Container

        cont = Container(self.args.create_inventory)
        cmd = []
        cmd.append(gen.get_container_venv_python_exe())
        cmd.append(os.path.join(
            gen.get_container_python_path(), 'inv_create.py'))
        try:
            cont.run_command(cmd)
        except UserException as exc:
            print('Fail:', exc.message, file=sys.stderr)
            sys.exit(1)
        print('Success: Created inventory file')

        # Remove existing inventory file on deployer
        deployer_inv_file = os.path.realpath(gen.INV_FILE)
        if os.path.isfile(deployer_inv_file):
            os.remove(deployer_inv_file)

        # Create a sym link on deployer to inventory inside container
        cont_inv_file = os.path.join(gen.LXC_DIR, cont.name, 'rootfs',
                                     gen.CONTAINER_PACKAGE_PATH[1:],
                                     gen.INV_FILE_NAME)
        os.symlink(cont_inv_file, deployer_inv_file)

    def _install_cobbler(self):
        from lib.container import Container

        cont = Container(self.args.install_cobbler)
        cmd = []
        cmd.append(gen.get_container_venv_python_exe())
        cmd.append(os.path.join(
            gen.get_container_python_path(), 'cobbler_install.py'))
        try:
            cont.run_command(cmd)
        except UserException as exc:
            print('Fail:', exc.message, file=sys.stderr)
            sys.exit(1)
        print('Success: Cobbler installed')

    def _download_os_images(self):
        from lib.container import Container

        try:
            download_os_images.download_os_images()
        except UserException as exc:
            print('Fail:', exc.message, file=sys.stderr)
            sys.exit(1)

        cont = Container(self.args.download_os_images)
        ssh = cont.open_ssh()
        sftp = cont.open_sftp(ssh)
        try:
            cont.copy_dir_to_container(sftp, cont.depl_os_images_path)
        except UserException as exc:
            print('Fail:', exc.message, file=sys.stderr)
            sys.exit(1)
        print('Success: OS images downloaded and copied into container')

    def _inv_add_ports_ipmi(self):
        dhcp_lease_file = '/var/lib/misc/dnsmasq.leases'
        from lib.container import Container

        cont = Container(self.args.inv_add_ports_ipmi)
        cmd = []
        cmd.append(gen.get_container_venv_python_exe())
        cmd.append(os.path.join(
            gen.get_container_python_path(), 'inv_add_ports.py'))
        cmd.append(dhcp_lease_file)
        cmd.append('ipmi')
        try:
            cont.run_command(cmd)
        except UserException as exc:
            print('Fail:', exc.message, file=sys.stderr)
            sys.exit(1)
        print('IPMI ports added to inventory')

    def _add_cobbler_distros(self):
        from lib.container import Container

        cont = Container(self.args.add_cobbler_distros)
        cmd = []
        cmd.append(gen.get_container_venv_python_exe())
        cmd.append(os.path.join(
            gen.get_container_python_path(), 'cobbler_add_distros.py'))
        try:
            cont.run_command(cmd)
        except UserException as exc:
            print('Fail:', exc.message, file=sys.stderr)
            sys.exit(1)
        print('Success: Cobbler distros and profiles added')

    def _inv_add_ports_pxe(self):
        dhcp_lease_file = '/var/lib/misc/dnsmasq.leases'
        from lib.container import Container

        cont = Container(self.args.inv_add_ports_pxe)
        cmd = []
        cmd.append(gen.get_container_venv_python_exe())
        cmd.append(os.path.join(
            gen.get_container_python_path(), 'inv_add_ports.py'))
        cmd.append(dhcp_lease_file)
        cmd.append('pxe')
        try:
            cont.run_command(cmd)
        except UserException as exc:
            print('Fail:', exc.message, file=sys.stderr)
            sys.exit(1)
        print('PXE ports added to inventory')

    def _add_cobbler_systems(self):
        from lib.container import Container

        cont = Container(self.args.add_cobbler_systems)
        cmd = []
        cmd.append(gen.get_container_venv_python_exe())
        cmd.append(os.path.join(
            gen.get_container_python_path(), 'cobbler_add_systems.py'))
        try:
            cont.run_command(cmd)
        except UserException as exc:
            print('Fail:', exc.message, file=sys.stderr)
            sys.exit(1)
        print('Success: Cobbler systems added')

    def _install_client_os(self):
        from lib.container import Container

        cont = Container(self.args.install_client_os)
        cmd = []
        cmd.append(gen.get_container_venv_python_exe())
        cmd.append(os.path.join(
            gen.get_container_python_path(), 'install_client_os.py'))
        try:
            cont.run_command(cmd)
        except UserException as exc:
            print('Fail:', exc.message, file=sys.stderr)
            sys.exit(1)
        print('Success: Client OS installaion initiated')

    def _config_data_switches(self):
        if gen.is_container_running():
            from lib.container import Container
            cont = Container(self.args.add_cobbler_systems)
            cmd = []
            cmd.append(gen.get_container_venv_python_exe())
            cmd.append(os.path.join(
                gen.get_container_python_path(), 'configure_data_switches.py'))
            try:
                cont.run_command(cmd)
            except UserException as exc:
                print('Fail:', exc.message, file=sys.stderr)
            print('Succesfully configured data switches')
        else:
            try:
                configure_data_switches.gather_and_display()
            except UserException as exc:
                print('Fail:', exc.message, file=sys.stderr)
            print('Succesfully configured data switches')

    def _gather_mac_addr(self):
        from lib.container import Container

        cont = Container(self.args.gather_mac_addr)
        _cmd = (
            'source ' + gen.get_container_venv_path() + '/bin/activate ' +
            '&& python ' + os.path.join(gen.get_container_python_path(), 'clear_port_macs.py') + ' ' +
            '&& ansible-playbook -i ' +
            gen.get_container_python_path() + '/inventory.py ' +
            gen.get_container_playbooks_path() + '/activate_client_interfaces.yml ' +
            '&& sleep 30 ' +
            '&& python ' + os.path.join(gen.get_container_python_path(), 'set_port_macs.py') + ' ' +
            '&& ansible-playbook -i ' +
            gen.get_container_python_path() + '/inventory.py ' +
            gen.get_container_playbooks_path() + '/restore_client_interfaces.yml ' +
            '&& deactivate')
        cmd = ['bash', '-c', _cmd]
        try:
            cont.run_command(cmd)
        except UserException as exc:
            print('Fail:', exc.message, file=sys.stderr)
            sys.exit(1)
        print('Success: Gathered Client MAC addresses')

    def launch(self):
        """Launch actions"""

        cmd = None
        # Determine which subcommand was specified
        try:
            if self.args.setup:
                cmd = argparse_gen.Cmd.SETUP.value
        except AttributeError:
            pass
        try:
            if self.args.config:
                cmd = argparse_gen.Cmd.CONFIG.value
        except AttributeError:
            pass
        try:
            if self.args.validate:
                cmd = argparse_gen.Cmd.VALIDATE.value
        except AttributeError:
            pass
        try:
            if self.args.deploy:
                cmd = argparse_gen.Cmd.DEPLOY.value
        except AttributeError:
            pass

        # Invoke subcommand method
        if cmd == argparse_gen.Cmd.SETUP.value:
            if gen.is_container():
                print(
                    'Fail: Invalid subcommand in container', file=sys.stderr)
                sys.exit(1)
            self._check_root_user(cmd)
            if self.args.bridges:
                self._create_bridges()

        if cmd == argparse_gen.Cmd.CONFIG.value:
            if gen.is_container():
                print(
                    'Fail: Invalid subcommand in container', file=sys.stderr)
                sys.exit(1)
            self._check_non_root_user(cmd)
            if argparse_gen.is_arg_present(self.args.create_container):
                self._create_container()
            if self.args.mgmt_switches:
                self._config_mgmt_switches()
            if self.args.data_switches:
                self._config_data_switches()

        if cmd == argparse_gen.Cmd.VALIDATE.value:
            if argparse_gen.is_arg_present(self.args.config_file):
                self._check_non_root_user(cmd)
                self._config_file()
            if argparse_gen.is_arg_present(self.args.cluster_hardware):
                self._check_root_user(cmd)
                self._cluster_hardware()

        if cmd == argparse_gen.Cmd.DEPLOY.value:
            if gen.is_container():
                print(
                    'Fail: Invalid subcommand in container', file=sys.stderr)
                sys.exit(1)

            if argparse_gen.is_arg_present(self.args.all):
                self.args.create_inventory = self.args.all
                self.args.install_cobbler = self.args.all
                self.args.download_os_images = self.args.all
                self.args.inv_add_ports_ipmi = self.args.all
                self.args.inv_add_ports_pxe = self.args.all
                self.args.add_cobbler_distros = self.args.all
                self.args.add_cobbler_systems = self.args.all
                self.args.install_client_os = self.args.all
                self.args.gather_mac_addr = self.args.all

            if argparse_gen.is_arg_present(self.args.create_inventory):
                self._create_inventory()
            if argparse_gen.is_arg_present(self.args.install_cobbler):
                self._install_cobbler()
            if argparse_gen.is_arg_present(self.args.download_os_images):
                self._download_os_images()
            if argparse_gen.is_arg_present(self.args.inv_add_ports_ipmi):
                self._inv_add_ports_ipmi()
            if argparse_gen.is_arg_present(self.args.inv_add_ports_pxe):
                self._inv_add_ports_pxe()
            if argparse_gen.is_arg_present(self.args.add_cobbler_distros):
                self._add_cobbler_distros()
            if argparse_gen.is_arg_present(self.args.add_cobbler_systems):
                self._add_cobbler_systems()
            if argparse_gen.is_arg_present(self.args.install_client_os):
                self._install_client_os()
            if argparse_gen.is_arg_present(self.args.gather_mac_addr):
                self._gather_mac_addr()


if __name__ == '__main__':
    args = argparse_gen.get_parsed_args()
    logger.create(
        args.log_level_file[0],
        args.log_level_print[0])
    GEN = Gen(args)
    GEN.launch()
