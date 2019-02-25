#!/usr/bin/env python3
"""POWER-Up 'gen' command"""

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

import importlib
import os
import sys
import getpass
import subprocess

import enable_deployer_networks
import enable_deployer_gateway
import validate_cluster_hardware
import configure_mgmt_switches
import osinstall
import remove_client_host_keys
from lib.utilities import scan_ping_network, sub_proc_exec
import download_os_images
import lib.argparse_gen as argparse_gen
import lib.logger as logger
import lib.genesis as gen
from lib.db import DatabaseConfig
from lib.exception import UserException, UserCriticalException
from lib.switch_exception import SwitchException
from set_power_clients import set_power_clients
from set_bootdev_clients import set_bootdev_clients


class Gen(object):
    """POWER-Up 'gen' command

    Args:
        log(object): log
    """

    ROOTUSER = 'root'
    global COL
    COL = gen.Color

    def __init__(self, args):
        self.args = args
        self.config_file_path = gen.GEN_PATH
        self.cont_config_file_path = gen.CONTAINER_PACKAGE_PATH + '/'

        ssh_log = os.path.join(gen.GEN_LOGS_PATH, 'ssh_paramiko')
        if not os.path.isfile(ssh_log):
            os.mknod(ssh_log)
        if not os.access(ssh_log, os.W_OK):
            cmd = f'sudo chmod 666 {ssh_log}'
            res, err, rc = sub_proc_exec(cmd)

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
        print(COL.scroll_ten, COL.up_ten)
        print('{}Configuring management switches{}\n'.
              format(COL.header1, COL.endc))
        print('This may take a few minutes depending on the size'
              ' of the cluster')
        try:
            configure_mgmt_switches.configure_mgmt_switches(
                self.config_file_path)
        except UserCriticalException as exc:
            print('{}A critical error occured while configuring managment '
                  'switches: \n{}{}'.format(COL.red, exc, COL.endc))
            sys.exit(1)
        else:
            print('\nSuccessfully completed management switch configuration\n')

    def _create_deployer_networks(self):
        print(COL.scroll_ten, COL.up_ten)
        print('{}Setting up deployer interfaces and networks{}\n'.
              format(COL.header1, COL.endc))
        try:
            enable_deployer_networks.enable_deployer_network(
                self.config_file_path)
        except UserCriticalException as exc:
            print('{}Critical error occured while setting up deployer networks:'
                  '\n{}{}'.format(COL.red, exc, COL.endc))
            sys.exit(1)
        except UserException as exc:
            print('{}Error occured while setting up deployer networks: \n{}{}'.
                  format(COL.yellow, exc, COL.endc))
        else:
            print('Successfully completed deployer network setup\n')

    def _enable_deployer_gateway(self):
        print(COL.scroll_ten, COL.up_ten)
        print('{}Setting up PXE network gateway and NAT record{}\n'.
              format(COL.header1, COL.endc))
        try:
            enable_deployer_gateway.enable_deployer_gateway(
                self.config_file_path)
        except UserCriticalException as exc:
            print('{}Critical error occured while setting up PXE network '
                  'gateway and NAT record:\n{}{}'.
                  format(COL.red, exc, COL.endc))
            sys.exit(1)
        except UserException as exc:
            print('{}Error occured while setting up PXE network gateway and '
                  'NAT record: \n{}{}'.
                  format(COL.yellow, exc, COL.endc))
        else:
            print('Successfully completed PXE network gateway setup\n')

    def _create_container(self):
        print(COL.scroll_ten, COL.up_ten)
        print('{}Creating container for running the POWER-Up '
              'software{}\n'.format(COL.header1, COL.endc))
        from lib.container import Container
        cont = Container(self.config_file_path)
        try:
            cont.create()
        except UserException as exc:
            print('Fail:', exc, file=sys.stderr)
            sys.exit(1)
        print('Success: Created container')

    def _config_file(self):
        from lib.inv_nodes import InventoryNodes
        print(COL.scroll_ten, COL.up_ten)
        print('{}Validating cluster configuration file{}\n'.
              format(COL.header1, COL.endc))
        dbase = DatabaseConfig(self.config_file_path)
        inv_path = gen.GEN_LOGS_PATH + gen.INV_FILE_NAME
        nodes = InventoryNodes(inv_path, self.config_file_path)
        try:
            dbase.validate_config()
            nodes.create_nodes()
        except UserCriticalException as exc:
            message = 'Failure: Config file validation.\n' + str(exc)
            print('{}{}{}'.format(COL.red, message, COL.endc))
            sys.exit(1)
        except UserException as exc:
            message = 'Warning: Config file validation.\n' + str(exc)
            print('{}{}{}'.format(COL.yellow, message, COL.endc))
        else:
            print('Successfully completed config file validation.\n')

    def _cluster_hardware(self):
        print(COL.scroll_ten, COL.up_ten)
        print('{}Discovering and validating cluster hardware{}\n'.
              format(COL.header1, COL.endc))
        err = False
        val = validate_cluster_hardware.ValidateClusterHardware(
            self.config_file_path)
        try:
            val.validate_mgmt_switches()
        except UserCriticalException as exc:
            print(str(exc), file=sys.stderr)
            print('{}Failure: Management switch validation.\n{}{}'.
                  format(COL.red, str(exc), COL.endc))
            sys.exit(1)

        try:
            val.validate_data_switches()
        except UserException as exc:
            print('{}Failure: Data switch validation\n{}{}'.
                  format(COL.yellow, str(exc), COL.endc))
            print('Warning. POWER-Up can continue with deployment, but')
            print('data network configuration will not succeed until issues ')
            print('are resolved')

        try:
            val.validate_ipmi()
        except UserException as exc:
            err = True
            print('{}Failure: Node IPMI validation error\n{}{}'.
                  format(COL.yellow, str(exc), COL.endc))
            print('Warning. POWER-Up can continue with deployment, but')
            print('Not all nodes will be deployed at this time')

        try:
            val.validate_pxe()
        except UserException as exc:
            err = True
            print('{}Failure: Node PXE validation error\n{}{}'.
                  format(COL.yellow, str(exc), COL.endc))
            print('Warning. POWER-Up can continue with deployment, but')
            print('Not all nodes will be deployed at this time')

        if err:
            print('Cluster hardware validation complete.')
        else:
            print('Successfully validated cluster hardware.\n')

    def _create_inventory(self):
        # from lib.inventory import Inventory
        # log = logger.getlogger()
        # inv = Inventory(cfg_file=self.config_file_path)
        # node_count = len(inv.inv['nodes'])
        # if node_count > 0:
        #     log.info("Inventory already exists!")
        #     print("\nInventory already exists with {} nodes defined."
        #           "".format(node_count))
        #     print("Press enter to continue using the existing inventory.")
        #     print("Type 'C' to continue creating a new inventory. "
        #           "WARNING: Contents of current file will be overwritten!")
        #     resp = input("Type 'T' to terminate Cluster Genesis ")
        #     if resp == 'T':
        #         sys.exit('POWER-Up stopped at user request')
        #     elif resp == 'C':
        #         log.info("'{}' entered. Creating new inventory file."
        #                  "".format(resp))
        #     else:
        #         log.info("Continuing with existing inventory.")
        #         return

        from lib.container import Container

        cont = Container(self.config_file_path, self.args.create_inventory)
        cont.copy(self.config_file_path, self.cont_config_file_path)
        cmd = []
        cmd.append(gen.get_container_venv_python_exe())
        cmd.append(os.path.join(
            gen.get_container_python_path(), 'inv_create.py'))
        cmd.append(self.cont_config_file_path)
        try:
            cont.run_command(cmd, interactive=True)
        except UserException as exc:
            print('Fail:', str(exc), file=sys.stderr)
            sys.exit(1)

        print('Success: Created inventory file')

    def _install_cobbler(self):
        from lib.container import Container

        cont = Container(self.config_file_path)
        cmd = []
        cmd.append(gen.get_container_venv_python_exe())
        cmd.append(os.path.join(
            gen.get_container_python_path(), 'cobbler_install.py'))
        cmd.append(self.cont_config_file_path)
        try:
            cont.run_command(cmd, interactive=True)
        except UserException as exc:
            print('Fail:', str(exc), file=sys.stderr)
            sys.exit(1)
        print('Success: Cobbler installed')

    def _download_os_images(self):
        from lib.container import Container

        try:
            download_os_images.download_os_images(self.config_file_path)
        except UserException as exc:
            print('Fail:', str(exc), file=sys.stderr)
            sys.exit(1)

        cont = Container(self.config_file_path)
        local_os_images = gen.get_os_images_path()
        cont_os_images = gen.get_container_os_images_path()
        try:
            cont.copy(local_os_images, cont_os_images)
        except UserException as exc:
            print('Fail:', str(exc), file=sys.stderr)
            sys.exit(1)
        print('Success: OS images downloaded and copied into container')

    def _inv_add_ports_ipmi(self):
        log = logger.getlogger()
        from lib.inventory import Inventory
        inv = Inventory(cfg_file=self.config_file_path)
        if (inv.check_all_nodes_ipmi_macs() and
                inv.check_all_nodes_ipmi_ipaddrs()):
            log.info("IPMI ports MAC and IP addresses already in inventory")
            return

        dhcp_lease_file = '/var/lib/misc/dnsmasq.leases'
        from lib.container import Container

        cont = Container(self.config_file_path)
        cmd = []
        cmd.append(gen.get_container_venv_python_exe())
        cmd.append(os.path.join(
            gen.get_container_python_path(), 'inv_add_ports.py'))
        cmd.append(dhcp_lease_file)
        cmd.append('ipmi')
        cmd.append(self.cont_config_file_path)
        try:
            cont.run_command(cmd, interactive=True)
        except UserException as exc:
            print('Fail:', str(exc), file=sys.stderr)
            sys.exit(1)
        print('IPMI ports added to inventory')

    def _add_cobbler_distros(self):
        from lib.container import Container

        cont = Container(self.config_file_path)
        cmd = []
        cmd.append(gen.get_container_venv_python_exe())
        cmd.append(os.path.join(
            gen.get_container_python_path(), 'cobbler_add_distros.py'))
        cmd.append(self.cont_config_file_path)
        try:
            cont.run_command(cmd, interactive=True)
        except UserException as exc:
            print('Fail:', str(exc), file=sys.stderr)
            sys.exit(1)
        print('Success: Cobbler distros and profiles added')

    def _inv_add_ports_pxe(self):
        log = logger.getlogger()
        from lib.inventory import Inventory
        inv = Inventory(cfg_file=self.config_file_path)
        if (inv.check_all_nodes_pxe_macs() and
                inv.check_all_nodes_pxe_ipaddrs()):
            log.info("PXE ports MAC and IP addresses already in inventory")
            return

        power_wait = gen.get_power_wait()
        set_power_clients('off', self.config_file_path, wait=power_wait)
        # set boot dev to bios, to avoid situations where some node types can skip
        # past pxe boot or attempt to boot from disk if pxe does not respond in time
        set_bootdev_clients('setup', False, self.config_file_path)
        set_power_clients('on', self.config_file_path, wait=power_wait)

        dhcp_lease_file = '/var/lib/misc/dnsmasq.leases'
        from lib.container import Container

        cont = Container(self.config_file_path, self.args.inv_add_ports_pxe)
        cmd = []
        cmd.append(gen.get_container_venv_python_exe())
        cmd.append(os.path.join(
            gen.get_container_python_path(), 'inv_add_ports.py'))
        cmd.append(dhcp_lease_file)
        cmd.append('pxe')
        cmd.append(self.cont_config_file_path)
        try:
            cont.run_command(cmd, interactive=True)
        except UserException as exc:
            print('Fail:', str(exc), file=sys.stderr)
            sys.exit(1)
        print('PXE ports added to inventory')

    def _reserve_ipmi_pxe_ips(self):
        from lib.container import Container

        cont = Container(self.config_file_path)
        cmd = []
        cmd.append(gen.get_container_venv_python_exe())
        cmd.append(os.path.join(
            gen.get_container_python_path(), 'inv_reserve_ipmi_pxe_ips.py'))
        cmd.append(self.cont_config_file_path)
        try:
            cont.run_command(cmd, interactive=True)
        except UserException as exc:
            print('Fail:', str(exc), file=sys.stderr)
            sys.exit(1)
        print('Success: IPMI and PXE IP Addresses Reserved')

    def _add_cobbler_systems(self):
        from lib.container import Container

        cont = Container(self.config_file_path)
        cmd = []
        cmd.append(gen.get_container_venv_python_exe())
        cmd.append(os.path.join(
            gen.get_container_python_path(), 'cobbler_add_systems.py'))
        cmd.append(self.cont_config_file_path)
        try:
            cont.run_command(cmd, interactive=True)
        except UserException as exc:
            print('Fail:', str(exc), file=sys.stderr)
            sys.exit(1)
        print('Success: Cobbler systems added')

    def _install_client_os(self):
        from lib.container import Container

        remove_client_host_keys.remove_client_host_keys(self.config_file_path)

        cont = Container(self.config_file_path)
        cmd = []
        cmd.append(gen.get_container_venv_python_exe())
        cmd.append(os.path.join(
            gen.get_container_python_path(), 'install_client_os.py'))
        cmd.append(self.cont_config_file_path)
        try:
            cont.run_command(cmd, interactive=True)
        except UserException as exc:
            print('Fail:', str(exc), file=sys.stderr)
            sys.exit(1)
        _run_playbook("wait_for_clients_ping.yml", self.config_file_path)

        print('Success: Client OS installaion complete')

    def _ssh_keyscan(self):
        _run_playbook("ssh_keyscan.yml", self.config_file_path)
        print('Success: SSH host key scan complete')

    def _config_data_switches(self):
        import configure_data_switches

        print(COL.scroll_ten, COL.up_ten)
        print('{}Configuring data switches{}\n'.
              format(COL.header1, COL.endc))
        print('This may take a few minutes depending on the size'
              ' of the cluster')
        try:
            configure_data_switches.configure_data_switch(
                self.args.config_file_name)
        except UserException as exc:
            print('\n{}Fail: {}{}'.format(COL.red, str(exc), COL.endc),
                  file=sys.stderr)
        except SwitchException as exc:
            print('\n{}Fail (switch error): {}{}'.format(
                  COL.red, str(exc), COL.endc), file=sys.stderr)
        else:
            print('\nSuccesfully configured data switches')

    def _gather_mac_addr(self):
        from lib.container import Container
        from lib.inventory import Inventory
        yellow = '\033[93m'
        endc = '\033[0m'

        log = logger.getlogger()
        cont = Container(self.config_file_path)

        found_all = False
        while found_all is not True:
            cmd = []
            cmd.append(gen.get_container_venv_python_exe())
            cmd.append(os.path.join(
                gen.get_container_python_path(), 'clear_port_macs.py'))
            cmd.append(self.cont_config_file_path)
            try:
                cont.run_command(cmd, interactive=True)
            except UserException as exc:
                print('Fail:', str(exc), file=sys.stderr)
                sys.exit(1)

            _run_playbook("activate_client_interfaces.yml", self.config_file_path)

            cmd[-2] = os.path.join(
                gen.get_container_python_path(), 'set_port_macs.py')
            try:
                cont.run_command(cmd, interactive=True)
            except UserException as exc:
                print('Fail:', str(exc), file=sys.stderr)
                sys.exit(1)

            inv = Inventory(cfg_file=self.config_file_path)
            if inv.check_data_interfaces_macs():
                found_all = True
            else:
                print()
                msg = 'Some data interface MAC addresses were not found!'
                log.warning(msg)
                print(f'{yellow}' + ('-' * (len(msg) + 10)) + f'{endc}')
                print("\nPress enter to retry")
                resp = input("Enter C to continue POWER-Up or 'T' to terminate ")
                if resp == 'T':
                    log.info("'{}' entered. Terminating POWER-Up at user request".format(resp))
                    sys.exit(1)
                elif resp == 'C':
                    log.info("'{}' entered. Continuing POWER-Up".format(resp))
                    found_all = True

        print('Success: Gathered Client MAC addresses')

    def _lookup_interface_names(self):
        try:
            _run_playbook("lookup_interface_names.yml --extra-vars config_path=" +
                          self.cont_config_file_path, self.config_file_path)
        except UserException as exc:
            print('Fail:', str(exc), file=sys.stderr)
            sys.exit(1)

        print('Success: Interface names collected')

    def _config_client_os(self):
        _run_playbook("configure_operating_systems.yml", self.config_file_path)
        print('Success: Client operating systems are configured')

    def _scan_pxe_network(self):
        print('Scanning cluster PXE network')
        scan_ping_network('pxe', self.config_file_path)

    def _scan_ipmi_network(self):
        print('Scanning cluster IPMI network')
        scan_ping_network('ipmi', self.config_file_path)

    def _osinstall(self):
        osinstall.osinstall(self.config_file_path)
        # print(self.config_file_path)

    def launch(self):
        """Launch actions"""

        cmd = None
        if not hasattr(self.args, 'software'):
            self.cont_config_file_path += (
                os.path.basename(self.args.config_file_name))

            path = self.args.config_file_name
            if os.path.dirname(self.args.config_file_name) == '':
                path = os.path.join(os.getcwd(), self.args.config_file_name)

            if os.path.isfile(path):
                self.config_file_path = path
            else:
                self.config_file_path += self.args.config_file_name

            if not os.path.isfile(self.config_file_path):
                print('{} not found. Please specify a file name'.format(
                    self.config_file_path))
                sys.exit(1)

            self.config_file_path = os.path.abspath(self.config_file_path)

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
                print('\nUsing {}'.format(self.config_file_path))
                resp = input('Enter to continue. "T" to terminate ')
                if resp == 'T':
                    sys.exit('POWER-Up stopped at user request')
        except AttributeError:
            pass
        try:
            if self.args.deploy:
                cmd = argparse_gen.Cmd.DEPLOY.value
        except AttributeError:
            pass
        try:
            if self.args.post_deploy:
                cmd = argparse_gen.Cmd.POST_DEPLOY.value
        except AttributeError:
            pass
        try:
            if self.args.osinstall:
                cmd = argparse_gen.Cmd.OSINSTALL.value
        except AttributeError:
            pass
        try:
            if self.args.software:
                cmd = argparse_gen.Cmd.SOFTWARE.value
        except AttributeError:
            pass
        try:
            if self.args.utils:
                cmd = argparse_gen.Cmd.UTIL.value
        except AttributeError:
            pass

        # Invoke subcommand method
        if cmd == argparse_gen.Cmd.SETUP.value:
            if gen.is_container():
                print(
                    'Fail: Invalid subcommand in container', file=sys.stderr)
                sys.exit(1)

            self._check_root_user(cmd)

            if self.args.all:
                self.args.networks = True
                self.args.gateway = True

            if self.args.networks:
                self._create_deployer_networks()
            if self.args.gateway:
                self._enable_deployer_gateway()

        if cmd == argparse_gen.Cmd.CONFIG.value:
            if gen.is_container():
                print(
                    'Fail: Invalid subcommand in container', file=sys.stderr)
                sys.exit(1)
            if argparse_gen.is_arg_present(self.args.create_container):
                self._check_non_root_user(cmd)
                self._create_container()
            if self.args.mgmt_switches:
                self._config_mgmt_switches()
            if argparse_gen.is_arg_present(self.args.data_switches):
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
                self.args.reserve_ipmi_pxe_ips = self.args.all
                self.args.add_cobbler_distros = self.args.all
                self.args.add_cobbler_systems = self.args.all
                self.args.install_client_os = self.args.all

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
            if argparse_gen.is_arg_present(self.args.reserve_ipmi_pxe_ips):
                self._reserve_ipmi_pxe_ips()
            if argparse_gen.is_arg_present(self.args.add_cobbler_distros):
                self._add_cobbler_distros()
            if argparse_gen.is_arg_present(self.args.add_cobbler_systems):
                self._add_cobbler_systems()
            if argparse_gen.is_arg_present(self.args.install_client_os):
                self._install_client_os()
            if argparse_gen.is_arg_present(self.args.all):
                print("\n\nPress enter to continue with node configuration ")
                print("and data switch setup, or 'T' to terminate ")
                print("POWER-Up. (To restart, type: 'pup post-deploy)")
                resp = input("\nEnter or 'T': ")
                if resp == 'T':
                    sys.exit('POWER-Up stopped at user request')
                cmd = argparse_gen.Cmd.POST_DEPLOY.value

        if cmd == argparse_gen.Cmd.POST_DEPLOY.value:
            if gen.is_container():
                print('Fail: Invalid subcommand in container', file=sys.stderr)
                sys.exit(1)
            if argparse_gen.is_arg_present(self.args.all):
                self.args.ssh_keyscan = self.args.all
                self.args.gather_mac_addr = self.args.all
                self.args.data_switches = self.args.all
                self.args.lookup_interface_names = self.args.all
                self.args.config_client_os = self.args.all

            if argparse_gen.is_arg_present(self.args.ssh_keyscan):
                self._ssh_keyscan()
            if argparse_gen.is_arg_present(self.args.gather_mac_addr):
                self._gather_mac_addr()
            if argparse_gen.is_arg_present(self.args.lookup_interface_names):
                self._lookup_interface_names()
            if argparse_gen.is_arg_present(self.args.config_client_os):
                self._config_client_os()
            if argparse_gen.is_arg_present(self.args.all):
                self._config_data_switches()

        if cmd == argparse_gen.Cmd.OSINSTALL.value:
            self._osinstall()

        if cmd == argparse_gen.Cmd.SOFTWARE.value:
            if not argparse_gen.is_arg_present(self.args.prep) and not \
                    argparse_gen.is_arg_present(self.args.init_clients) and not \
                    argparse_gen.is_arg_present(self.args.install) and not \
                    argparse_gen.is_arg_present(self.args.README) and not \
                    argparse_gen.is_arg_present(self.args.status):
                self.args.all = True
            if gen.GEN_SOFTWARE_PATH not in sys.path:
                sys.path.append(gen.GEN_SOFTWARE_PATH)
            try:
                self.args.name = self.args.name.split('.')[0]
                software_module = importlib.import_module(self.args.name)
            except ImportError as exc:
                print(exc)
                sys.exit(1)
            if 'software' not in dir(software_module):
                self.log.error('Software installation modules need to implement a '
                               'class named "software"')
                sys.exit(1)
            else:
                soft = software_module.software(self.args.eval, self.args.non_interactive, self.args.arch)
            if self.args.prep is True or self.args.all is True:
                try:
                    soft.prep()
                except AttributeError as exc:
                    print(exc)
                    print('The software class needs to implement a '
                          'method named "setup"')
            if self.args.init_clients is True or self.args.all is True:
                try:
                    soft.init_clients()
                except AttributeError as exc:
                    print(exc)
                    print('The software class needs to implement a '
                          'method named "init_clients"')
            if self.args.install is True or self.args.all is True:
                try:
                    soft.install()
                except AttributeError as exc:
                    print(exc)
                    print('The software class needs to implement a '
                          'method named "install"')
            if self.args.README is True:
                try:
                    soft.README()
                except AttributeError as exc:
                    print(exc)
                    print('No "about" information available')

            if self.args.status is True:
                try:
                    soft.status()
                except AttributeError as exc:
                    print(exc)
                    print('No "status" information available')

        if cmd == argparse_gen.Cmd.UTIL.value:
            if self.args.scan_pxe_network:
                self._scan_pxe_network()
            if self.args.scan_ipmi_network:
                self._scan_ipmi_network()

        if not cmd:
            print('Unrecognized POWER-Up command')


def _run_playbook(playbook, config_path):
    log = logger.getlogger()
    config_pointer_file = gen.get_python_path() + '/config_pointer_file'
    with open(config_pointer_file, 'w') as f:
        f.write(config_path)
    ansible_playbook = gen.get_ansible_playbook_path()
    inventory = ' -i ' + gen.get_python_path() + '/inventory.py'
    playbook = ' ' + playbook
    cmd = ansible_playbook + inventory + playbook
    command = ['bash', '-c', cmd]
    log.debug('Run subprocess: %s' % ' '.join(command))
    process = subprocess.Popen(command, cwd=gen.get_playbooks_path())
    process.wait()


if __name__ == '__main__':
    args = argparse_gen.get_parsed_args()

    logger.create(
        args.log_level_file[0],
        args.log_level_print[0])

    if args.log_level_print[0] == 'debug':
        print('DEBUG - {}'.format(args))
    GEN = Gen(args)
    GEN.launch()
