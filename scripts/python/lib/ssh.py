#!/usr/bin/env python3
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

import sys
import os.path
import socket
import paramiko

import lib.logger as logger
from lib.genesis import GEN_LOGS_PATH

SSH_LOG = os.path.join(GEN_LOGS_PATH, 'ssh_paramiko')


class SSH_Exception(Exception):
    pass


class SSH(object):
    SWITCH_PORT = 22

    def __init__(self):
        self.log = logger.getlogger()

    def exec_cmd(self, ip_addr, username, password, cmd,
                 ssh_log=False, look_for_keys=True, key_filename=None):
        self.ssh_log = SSH_LOG
        if ssh_log and logger.is_log_level_file_debug():
            paramiko.util.log_to_file(self.ssh_log)

        ssh = paramiko.SSHClient()
        ssh.load_system_host_keys()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(
                ip_addr,
                port=self.SWITCH_PORT,
                username=username,
                password=password,
                look_for_keys=look_for_keys,
                key_filename=key_filename)
        except (
                paramiko.BadHostKeyException,
                paramiko.AuthenticationException,
                paramiko.SSHException,
                socket.error,
                BaseException) as exc:
            self.log.error('%s: %s' % (ip_addr, str(exc)))
            raise SSH_Exception('SSH connection Failure - {}'.format(exc))
            # sys.exit(1)
        try:
            _, stdout, stderr = ssh.exec_command(cmd)
        except paramiko.SSHException as exc:
            self.log.error('%s: %s, %s' % (ip_addr, str(exc), stderr.read()))
            sys.exit(1)
        stdout_ = stdout.read()
        stderr_ = stderr.read()
        status = stdout.channel.recv_exit_status()
        ssh.close()
        return status, stdout_, stderr_


class SSH_CONNECTION(paramiko.SSHClient):
    """Returns a connected paramiko SSHClient
    Use send_cmd to run paramiko exec_command with additional error handling
    Application must close the connection with paramiko close()

    Args:
        host (string): host ip address or name (paramiko hostname)
        log (Logger object): Logging.
        ssh_log (string): filepath for paramiko log
        see paramiko documentation for other args
    """

    def __init__(self, host, ssh_log=False, username=None,
                 password=None, look_for_keys=True, key_filename=None):
        paramiko.SSHClient.__init__(self)
        self.host = host
        self.log = logger.getlogger()
        self.ssh_log = SSH_LOG
        if ssh_log and logger.is_log_level_file_debug():
            paramiko.util.log_to_file(self.ssh_log)

        if key_filename is None:
            self.load_system_host_keys()
        self.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            self.connect(
                host,
                username=username,
                password=password,
                look_for_keys=look_for_keys,
                key_filename=key_filename)
        except (
                paramiko.BadHostKeyException,
                paramiko.AuthenticationException,
                paramiko.SSHException,
                socket.error,
                BaseException) as exc:
            self.log.error('%s: %s' % (host, str(exc)))
            raise SSH_Exception('Connection Failure - {}'.format(exc))

    def close_ssh(self):
        return self.close()

    def send_cmd(self, cmd):
        try:
            _, stdout, stderr = self.exec_command(cmd)
        except paramiko.SSHException as exc:
            if self.log is not None:
                self.log.error('%s: %s' % (self.host, str(exc)))
            else:
                print('%s: %s' % (self.host, str(exc)))
            sys.exit(1)
        stdout_ = stdout.read()
        stderr_ = stderr.read()
        status = stdout.channel.recv_exit_status()
        return status, stdout_, stderr_

    def open_sftp_session(self):
        return self.open_sftp()
