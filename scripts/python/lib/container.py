#!/usr/bin/env python3
"""Container"""

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

import os
import sys
from Crypto.PublicKey import RSA
import docker
import tarfile
from netaddr import IPNetwork

import lib.logger as logger
from lib.config import Config
from lib.exception import UserException
import lib.genesis as gen
from lib.utilities import sub_proc_display, sha1sum


class Container(object):
    """Container"""

    ARCHITECTURE = {u'x86_64': 'amd64', u'ppc64le': 'ppc64el'}
    RSA_BIT_LENGTH = 2048
    PRIVATE_SSH_KEY_FILE = gen.get_ssh_private_key_file()
    PUBLIC_SSH_KEY_FILE = gen.get_ssh_public_key_file()
    DEFAULT_CONTAINER_NAME = gen.get_project_name()

    def __init__(self, config_path=None, name=None):
        self.log = logger.getlogger()
        self.cfg = Config(config_path)

        self.cont_package_path = gen.get_container_package_path()
        self.cont_id_file = gen.get_container_id_file()
        self.cont_venv_path = gen.get_container_venv_path()
        self.cont_scripts_path = gen.get_container_scripts_path()
        self.cont_python_path = gen.get_container_python_path()
        self.cont_os_images_path = gen.get_container_os_images_path()
        self.cont_playbooks_path = gen.get_container_playbooks_path()
        self.depl_package_path = gen.get_package_path()
        self.depl_scripts_path = gen.get_scripts_path()
        self.depl_python_path = gen.get_python_path()
        self.depl_playbooks_path = gen.get_playbooks_path()
        self.depl_dockerfile_path = gen.get_dockerfile_path()

        if name is True or name is None:
            for vlan in self.cfg.yield_depl_netw_client_vlan('pxe'):
                break
            self.name = '{}-pxe{}'.format(self.DEFAULT_CONTAINER_NAME, vlan)
        else:
            self.name = name

        self.client = docker.from_env()

        try:
            self.image = self.client.images.get('power-up')
        except docker.errors.ImageNotFound:
            self.image = None

        try:
            self.cont = self.client.containers.get(self.name)
        except docker.errors.NotFound:
            self.cont = None

    def run_command(self, cmd, interactive=False):
        self.log.debug(f"Exec container:'{self.cont.name}' cmd:'{cmd}'")
        if interactive:
            # TODO: Use docker.Container.exec_run() method for interactive cmds
            cmd_string = ' '.join(cmd)
            rc = sub_proc_display(f'docker exec -it {self.cont.name} '
                                  f'{cmd_string}')
            output = None
        else:
            environment = [logger.get_log_level_env_var_file(),
                           logger.get_log_level_env_var_print()]
            print('.', end="")
            rc, output = self.cont.exec_run(cmd,
                                            stderr=True,
                                            stdout=True,
                                            stdin=True,
                                            stream=interactive,
                                            detach=False,
                                            tty=True,
                                            environment=environment)
            print('.', end="")
            self.log.debug(f"rc:'{rc}' output:'{output.decode('utf-8')}'")
            sys.stdout.flush()
        if rc:
            msg = f"Failed running '{cmd}' in the container '{self.name}'"
            if output is not None:
                msg += f": {output}"
            self.log.error(msg)
            raise UserException(msg)
        else:
            self.log.debug(f"Successfully ran '{cmd}' in the container "
                           f"'{self.name}'")

    def create(self):
        # Check if container already exists
        if self.cont is not None:
            self.log.warning(f"Container '{self.name}' already exists")
            print("\nPress enter to continue with node configuration using ")
            print("existing container, or 'T' to terminate.")
            resp = input("\nEnter or 'T': ")
            if resp == 'T':
                sys.exit('POWER-Up stopped at user request')
        else:
            # Make sure image is built
            tag = self.build_image()

            # Create inventory mount
            source = gen.get_symlink_realpath(self.cfg.config_path)
            target = gen.get_container_inventory_realpath()

            if not os.path.isfile(source):
                os.mknod(source)

            switch_lock_path = gen.get_switch_lock_path()
            container_package_path = gen.get_container_package_path()
            dest_path = os.path.join(container_package_path[:1 +
                                     container_package_path[1:].find('/')],
                                     switch_lock_path[1:])
            volumes = {source: {'bind': target, 'mode': 'Z'},
                       switch_lock_path: {'bind': dest_path, 'mode': 'z'}}
            self.log.debug(f'Container volumes: {volumes}')

            # Create container
            try:
                self.log.info(f"Creating Docker container '{self.name}'")
                self.cont = (
                    self.client.containers.run(image=tag,
                                               name=self.name,
                                               cap_add=["NET_ADMIN"],
                                               tty=True,
                                               stdin_open=True,
                                               detach=True,
                                               volumes=volumes))
            except docker.errors.APIError as exc:
                msg = f"Failed to create container '{self.name}': {exc}"
                self.log.error(msg)
                raise UserException(msg)
            self.log.debug(f"Created container '{self.name}'")

        # Start container
        if self.cont.status != 'running':
            try:
                self.cont.restart()
            except docker.errors.APIError as exc:
                msg = f"Failed to start container '{self.name}': {exc}"
                self.log.error(msg)
                raise UserException(msg)
            self.log.debug("Re-started container '{self.name}'")

        # Copy current scripts into container
        self.copy(self.depl_scripts_path, self.cont_scripts_path)

        # Build current python venv
        self.copy(os.path.join(self.depl_package_path, 'requirements.txt'),
                  self.cont_package_path + '/')
        self.run_command([os.path.join(self.cont_scripts_path,
                                       'venv_install.sh'),
                          self.cont_package_path + '/'])

        # Create '/root/.ssh' directory
        self.run_command(['mkdir', '-p', '/root/.ssh'])

        # Create '/root/.ssh/authorized_keys' file
        self.run_command(['touch', '/root/.ssh/authorized_keys'])

        # Change '/root/.ssh' permissions to 0700
        self.run_command(['chmod', '700', '/root/.ssh'])

        # Change '/root/.ssh/authorized_keys' permissions to 0600
        self.run_command(['chmod', '600', '/root/.ssh/authorized_keys'])

        # Create new SSH private/public keys only if they don't exist
        if (not os.path.isfile(self.PRIVATE_SSH_KEY_FILE) and
                not os.path.isfile(self.PUBLIC_SSH_KEY_FILE)):
            key = RSA.generate(self.RSA_BIT_LENGTH)
            # Create user .ssh directory if needed
            if not os.path.exists(os.path.expanduser('~/.ssh')):
                os.mkdir(os.path.expanduser('~/.ssh'), 0o700)
            # Create private ssh key
            with open(self.PRIVATE_SSH_KEY_FILE, 'w') as ssh_key:
                ssh_key.write(key.exportKey().decode("utf-8"))
            os.chmod(self.PRIVATE_SSH_KEY_FILE, 0o600)
            # Create public ssh key
            public_key = key.publickey().exportKey(format='OpenSSH')
            with open(self.PUBLIC_SSH_KEY_FILE, 'w') as ssh_key:
                ssh_key.write(public_key.decode("utf-8"))
        # Throw exception if one of the key pair is missing
        elif (not os.path.isfile(self.PRIVATE_SSH_KEY_FILE) and
                os.path.isfile(self.PUBLIC_SSH_KEY_FILE)):
            raise UserException("Private SSH key is missing but public exists")
        elif (os.path.isfile(self.PRIVATE_SSH_KEY_FILE) and
                not os.path.isfile(self.PUBLIC_SSH_KEY_FILE)):
            raise UserException("Public SSH key is missing but private exists")

        # Copy private ssh key pair to container
        self.copy(self.PRIVATE_SSH_KEY_FILE, '/root/.ssh/')
        self.copy(self.PUBLIC_SSH_KEY_FILE, '/root/.ssh/')

        # Change private key file permissions to 0600
        cont_private_ssh_key_file = (
            '/root/.ssh/' + os.path.basename(self.PRIVATE_SSH_KEY_FILE))
        self.run_command(['chmod', '600', cont_private_ssh_key_file])

        # Add public ssh key to container's authorized_keys
        cont_public_ssh_key_file = (
            '/root/.ssh/' + os.path.basename(self.PUBLIC_SSH_KEY_FILE))
        authorized_keys = '/root/.ssh/authorized_keys'
        self.run_command(['/bin/bash', '-c',
                          f'grep -f {cont_public_ssh_key_file} '
                          f'{authorized_keys} ||'
                          f'(cat {cont_public_ssh_key_file} >> '
                          f'{authorized_keys} && echo "" >> '
                          f'{authorized_keys})'])

        # Start SSH service
        self.run_command(['service', 'ssh', 'restart'])

        # Create file to indicate whether project is installed in a container
        self.run_command(['touch', self.cont_id_file])

        # Create and connect to networks
        self.connect_networks()

    def build_image(self):
        repo_name = self.DEFAULT_CONTAINER_NAME
        dockerfile_tag = sha1sum(self.depl_dockerfile_path)
        tag = f"{repo_name}:{dockerfile_tag}"
        try:
            self.client.images.get(tag)
            self.log.info(f"Using existing Docker image '{tag}'")
        except docker.errors.ImageNotFound:
            self.log.info(f"Building Docker image '{repo_name}'")
            try:
                self.image, build_logs = self.client.images.build(
                    path=gen.get_package_path(),
                    tag=tag,
                    rm=True)
            except docker.errors.APIError as exc:
                msg = ("Failed to create image "
                       f"'{self.DEFAULT_CONTAINER_NAME}': {exc}")
                self.log.error(msg)
                raise UserException(msg)
            self.log.debug("Created image "
                           f"'{self.DEFAULT_CONTAINER_NAME}'")
        return tag

    def connect_networks(self):
        for network, ipaddr in self.create_networks():
            if self.cont not in network.containers:
                self.log.debug(f"Connecting container '{self.cont.name}' to "
                               f"network '{network.name}' with IP '{ipaddr}'")
                network.connect(container=self.cont, ipv4_address=ipaddr)

    def create_networks(self, remove=False):
        network_list = []

        dev_label = self.cfg.get_depl_netw_mgmt_device()
        interface_ipaddr = self.cfg.get_depl_netw_mgmt_intf_ip()
        container_ipaddr = self.cfg.get_depl_netw_mgmt_cont_ip()
        bridge_ipaddr = self.cfg.get_depl_netw_mgmt_brg_ip()
        vlan = self.cfg.get_depl_netw_mgmt_vlan()
        netprefix = self.cfg.get_depl_netw_mgmt_prefix()

        for i, dev in enumerate(dev_label):
            network = self._create_network(
                dev_label[i],
                interface_ipaddr[i],
                netprefix[i],
                container_ipaddr=container_ipaddr[i],
                bridge_ipaddr=bridge_ipaddr[i],
                vlan=vlan[i],
                remove=remove)
            if network is not None:
                network_list.append((network, container_ipaddr[i]))

        type_ = self.cfg.get_depl_netw_client_type()
        dev_label = self.cfg.get_depl_netw_client_device()
        interface_ipaddr = self.cfg.get_depl_netw_client_intf_ip()
        container_ipaddr = self.cfg.get_depl_netw_client_cont_ip()
        bridge_ipaddr = self.cfg.get_depl_netw_client_brg_ip()
        vlan = self.cfg.get_depl_netw_client_vlan()
        netprefix = self.cfg.get_depl_netw_client_prefix()

        for i, dev in enumerate(dev_label):
            network = self._create_network(
                dev_label[i],
                interface_ipaddr[i],
                netprefix[i],
                container_ipaddr=container_ipaddr[i],
                bridge_ipaddr=bridge_ipaddr[i],
                vlan=vlan[i],
                type_=type_[i],
                remove=remove)
            if network is not None:
                network_list.append((network, container_ipaddr[i]))

        return network_list

    def _create_network(
            self,
            dev_label,
            interface_ipaddr,
            netprefix,
            container_ipaddr=None,
            bridge_ipaddr=None,
            vlan=None,
            type_='mgmt',
            remove=False):

        network = None

        if container_ipaddr is not None and bridge_ipaddr is not None:
            name = 'pup-' + type_
            br_name = 'br-' + type_
            if vlan is not None:
                name += '-' + str(vlan)
                br_name += '-' + str(vlan)
            try:
                network = self.client.networks.get(name)
                if remove:
                    for container in network.containers:
                        self.log.debug("Disconnecting Docker network "
                                       f"'{network.name}' from container"
                                       f"'{container.name}'")
                        network.disconnect(container, force=True)
                    self.log.debug(f"Removing Docker network '{network.name}'")
                    network.remove()
                    network = None
            except docker.errors.NotFound:
                if not remove:
                    self.log.debug(f"Creating Docker network '{name}'")
                    subnet = str(IPNetwork(bridge_ipaddr + '/' +
                                           str(netprefix)).cidr)
                    ipam_pool = docker.types.IPAMPool(subnet=subnet,
                                                      gateway=bridge_ipaddr)
                    ipam_config = docker.types.IPAMConfig(
                        pool_configs=[ipam_pool])
                    try:
                        network = self.client.networks.create(
                            name=name,
                            driver='bridge',
                            ipam=ipam_config,
                            options={'com.docker.network.bridge.name':
                                     br_name})
                    except docker.errors.APIError as exc:
                        msg = (f"Failed to create network '{name}': {exc}")
                        self.log.error(msg)
                        raise UserException(msg)

        return network

    def copy(self, source_path, cont_dest_path):
        self.log.debug(f"Copy '{source_path}' into "
                       f"'{self.cont.name}:{cont_dest_path}'")
        os.chdir(os.path.dirname(source_path))
        source_base = os.path.basename(source_path)

        tar_file = tarfile.open(source_path + '.tar', mode='w')
        tar_file.add(source_base)
        tar_file.close()
        tar_data = open(source_path + '.tar', 'rb').read()
        if self.cont.put_archive(os.path.dirname(cont_dest_path), tar_data):
            os.remove(source_path + '.tar')
        else:
            self.log.error("Container 'put_archive' error!")
