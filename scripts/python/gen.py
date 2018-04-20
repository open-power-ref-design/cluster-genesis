#!/usr/bin/env python
"""POWER-Up 'gen' command"""

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
import subprocess

import enable_deployer_networks
import enable_deployer_gateway
import validate_cluster_hardware
import configure_mgmt_switches
import download_os_images
import lxc_conf
import lib.argparse_gen as argparse_gen
import lib.logger as logger
import lib.genesis as gen
from lib.db import DatabaseConfig
from lib.exception import UserException, UserCriticalException
from lib.switch_exception import SwitchException
from ipmi_power_off import ipmi_power_off
from ipmi_set_bootdev import ipmi_set_bootdev
from ipmi_power_on import ipmi_power_on


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
            configure_mgmt_switches.configure_mgmt_switches()
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
            enable_deployer_networks.enable_deployer_network()
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
            enable_deployer_gateway.enable_deployer_gateway()
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
        print('{}Creating container for running the Cluster '
              'Genesis software{}\n'.format(COL.header1, COL.endc))
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
        from lib.inv_nodes import InventoryNodes
        print(COL.scroll_ten, COL.up_ten)
        print('{}Validating cluster configuration file{}\n'.
              format(COL.header1, COL.endc))
        dbase = DatabaseConfig()
        inv_path = gen.GEN_LOGS_PATH + gen.INV_FILE_NAME
        nodes = InventoryNodes(inv_path)
        try:
            dbase.validate_config(self.args.config_file)
            nodes.create_nodes()
        except UserCriticalException as exc:
            exc.message = 'Failure: Config file validation.\n' + exc.message
            print('{}{}{}'.format(COL.red, exc.message, COL.endc))
            sys.exit(1)
        except UserException as exc:
            exc.message = 'Warning: Config file validation.\n' + exc.message
            print('{}{}{}'.format(COL.yellow, exc.message, COL.endc))
        else:
            print('Successfully completed config file validation.\n')

    def _cluster_hardware(self):
        print(COL.scroll_ten, COL.up_ten)
        print('{}Discovering and validating cluster hardware{}\n'.
              format(COL.header1, COL.endc))
        err = False
        val = validate_cluster_hardware.ValidateClusterHardware()
        try:
            val.validate_mgmt_switches()
        except UserCriticalException as exc:
            print(exc.message, file=sys.stderr)
            print('{}Failure: Management switch validation.\n{}{}'.
                  format(COL.red, exc.message, COL.endc))
            sys.exit(1)

        try:
            val.validate_data_switches()
        except UserException as exc:
            print('{}Failure: Data switch validation\n{}{}'.
                  format(COL.yellow, exc.message, COL.endc))
            print('Warning. POWER-Up can continue with deployment, but')
            print('data network configuration will not succeed until issues ')
            print('are resolved')

        try:
            val.validate_ipmi()
        except UserException as exc:
            err = True
            print('{}Failure: Node IPMI validation error\n{}{}'.
                  format(COL.yellow, exc.message, COL.endc))
            print('Warning. POWER-Up can continue with deployment, but')
            print('Not all nodes will be deployed at this time')

        try:
            val.validate_pxe(self.args.cluster_hardware)
        except UserException as exc:
            err = True
            print('{}Failure: Node PXE validation error\n{}{}'.
                  format(COL.yellow, exc.message, COL.endc))
            print('Warning. POWER-Up can continue with deployment, but')
            print('Not all nodes will be deployed at this time')

        if err:
            print('Cluster hardware validation complete.')
        else:
            print('Successfully validated cluster hardware.\n')

    def _create_inventory(self):
        from lib.inventory import Inventory
        log = logger.getlogger()
        inv = Inventory()
        node_count = len(inv.inv['nodes'])
        if node_count > 0:
            log.info("Inventory already exists!")
            print("\nInventory already exists with {} nodes defined."
                  "".format(node_count))
            print("Press enter to continue using the existing inventory.")
            print("Type 'C' to continue creating a new inventory. "
                  "WARNING: Contents of current file will be overwritten!")
            resp = raw_input("Type 'T' to terminate Cluster Genesis ")
            if resp == 'T':
                sys.exit('POWER-Up stopped at user request')
            elif resp == 'C':
                log.info("'{}' entered. Creating new inventory file."
                         "".format(resp))
            else:
                log.info("Continuing with existing inventory.")
                return

        from lib.container import Container

        log = logger.getlogger()

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

        deployer_inv_file = gen.get_symlink_realpath()

        # If inventory file symlink is broken link remove it
        symlink_path = gen.get_symlink_path()
        if os.path.islink(symlink_path):
            if not os.path.exists(os.readlink(symlink_path)):
                os.unlink(symlink_path)

        # If inventory is an empty file delete it
        if os.stat(deployer_inv_file).st_size == 0:
            os.remove(deployer_inv_file)

        # Create a sym link on deployer to inventory inside container
        if not os.path.isfile(deployer_inv_file):
            cont_inv_file = os.path.join(gen.LXC_DIR, cont.name, 'rootfs',
                                         gen.CONTAINER_PACKAGE_PATH[1:],
                                         gen.INV_FILE_NAME)
            log.debug("Creating symlink on deployer to container inventory: "
                      "{} -> {}".format(deployer_inv_file, cont_inv_file))
            os.symlink(cont_inv_file, deployer_inv_file)
        print('Success: Created inventory file')

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
        local_os_images = gen.get_os_images_path()
        cont_os_images = gen.get_container_os_images_path()
        try:
            cont.copy_dir_to_container(local_os_images, cont_os_images)
        except UserException as exc:
            print('Fail:', exc.message, file=sys.stderr)
            sys.exit(1)
        print('Success: OS images downloaded and copied into container')

    def _inv_add_ports_ipmi(self):
        log = logger.getlogger()
        from lib.inventory import Inventory
        inv = Inventory()
        if (inv.check_all_nodes_ipmi_macs() and
                inv.check_all_nodes_ipmi_ipaddrs()):
            log.info("IPMI ports MAC and IP addresses already in inventory")
            return

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
        log = logger.getlogger()
        from lib.inventory import Inventory
        inv = Inventory()
        if (inv.check_all_nodes_pxe_macs() and
                inv.check_all_nodes_pxe_ipaddrs()):
            log.info("PXE ports MAC and IP addresses already in inventory")
            return

        power_time_out = gen.get_power_time_out()
        power_wait = gen.get_power_wait()
        ipmi_power_off(power_time_out, power_wait)
        ipmi_set_bootdev('network', False)
        ipmi_power_on(power_time_out, power_wait)

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

    def _reserve_ipmi_pxe_ips(self):
        from lib.container import Container

        cont = Container(self.args.reserve_ipmi_pxe_ips)
        cmd = []
        cmd.append(gen.get_container_venv_python_exe())
        cmd.append(os.path.join(
            gen.get_container_python_path(), 'inv_reserve_ipmi_pxe_ips.py'))
        try:
            cont.run_command(cmd)
        except UserException as exc:
            print('Fail:', exc.message, file=sys.stderr)
            sys.exit(1)
        print('Success: IPMI and PXE IP Addresses Reserved')

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
        _run_playbook("wait_for_clients_ping.yml")

        print('Success: Client OS installaion complete')

    def _ssh_keyscan(self):
        _run_playbook("ssh_keyscan.yml")
        print('Success: SSH host key scan complete')

    def _config_data_switches(self):
        import configure_data_switches

        print(COL.scroll_ten, COL.up_ten)
        print('{}Configuring data switches{}\n'.
              format(COL.header1, COL.endc))
        print('This may take a few minutes depending on the size'
              ' of the cluster')
        if gen.is_container_running():
            from lib.container import Container
            cont = Container(self.args.data_switches)
            cmd = []
            cmd.append(gen.get_container_venv_python_exe())
            cmd.append(os.path.join(
                gen.get_container_python_path(), 'configure_data_switches.py'))
            try:
                cont.run_command(cmd)
            except UserException as exc:
                print('\n{}Fail: {}{}'.format(COL.red, exc.message, COL.endc),
                      file=sys.stderr)
            else:
                print('\nSuccesfully configured data switches')
        else:
            try:
                configure_data_switches.configure_data_switch()
            except UserException as exc:
                print('\n{}Fail: {}{}'.format(COL.red, exc.message, COL.endc),
                      file=sys.stderr)
            except SwitchException as exc:
                print('\n{}Fail (switch error): {}{}'.format(
                      COL.red, exc.message, COL.endc), file=sys.stderr)
            else:
                print('\nSuccesfully configured data switches')

    def _gather_mac_addr(self):
        from lib.container import Container

        cont = Container(self.args.gather_mac_addr)
        cmd = []
        cmd.append(gen.get_container_venv_python_exe())
        cmd.append(os.path.join(
            gen.get_container_python_path(), 'clear_port_macs.py'))
        try:
            cont.run_command(cmd)
        except UserException as exc:
            print('Fail:', exc.message, file=sys.stderr)
            sys.exit(1)

        _run_playbook("activate_client_interfaces.yml")

        del cmd[-1]
        cmd.append(os.path.join(
            gen.get_container_python_path(), 'set_port_macs.py'))
        try:
            cont.run_command(cmd)
        except UserException as exc:
            print('Fail:', exc.message, file=sys.stderr)
            sys.exit(1)
        else:
            print('Success: Gathered Client MAC addresses')

    def _lookup_interface_names(self):
        try:
            _run_playbook("lookup_interface_names.yml")
        except UserException as exc:
            print('Fail:', exc.message, file=sys.stderr)
            sys.exit(1)

        print('Success: Interface names collected')

    def _config_client_os(self):
        _run_playbook("configure_operating_systems.yml")
        print('Success: Client operating systems are configured')

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
        try:
            if self.args.post_deploy:
                cmd = argparse_gen.Cmd.POST_DEPLOY.value
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
            self._check_non_root_user(cmd)
            if argparse_gen.is_arg_present(self.args.create_container):
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
                resp = raw_input("\nEnter or 'T': ")
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


def _run_playbook(playbook):
    log = logger.getlogger()
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
    GEN = Gen(args)
    GEN.launch()
