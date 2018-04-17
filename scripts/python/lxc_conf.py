#!/usr/bin/env python
"""Create lxc-conf.yml"""

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

import sys
import os
import platform
import pwd
import re
import os.path
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, \
    TemplateSyntaxError, TemplateAssertionError

import lib.logger as logger
from lib.config import Config
from lib.genesis import GEN_PLAY_PATH, HOME, OPSYS

USERNAME = pwd.getpwuid(os.getuid())[0]


class LxcConf(object):
    """Create lxc-conf.yml"""

    TEMPLATE_DIR = GEN_PLAY_PATH + 'templates/localhost'
    TEMPLATE_FILE = 'lxc-conf.j2'
    LXC_CONF = GEN_PLAY_PATH + 'lxc-conf.yml'
    TYPE = 'type'
    VLAN = 'vlan'
    IPADDR = 'ipaddr'
    PREFIX = 'prefix'

    def __init__(self, config_path=None):
        self.log = logger.getlogger()
        self.cfg = Config(config_path)
        if OPSYS not in ('Ubuntu', 'redhat'):
            raise Exception('Unsupported Operating System')

    def create(self):
        """Create lxc-conf.yml"""
        env = Environment(loader=FileSystemLoader(self.TEMPLATE_DIR))
        try:
            template = env.get_template(self.TEMPLATE_FILE)
        except TemplateNotFound as exc:
            self.log.error('Template not found: %s' % exc.name)
            print('Template not found: %s' % exc.name)
            sys.exit(1)
        except TemplateAssertionError as exc:
            self.log.error('Template assertion error: %s in %s, line %d' % (
                exc.message, exc.filename, exc.lineno))
            print('Template assertion error: %s in %s, line %d' % (
                exc.message, exc.filename, exc.lineno))
            sys.exit(1)
        except TemplateSyntaxError as exc:
            self.log.error('Template syntax error: %s in %s, line %d' % (
                exc.message, exc.filename, exc.lineno))
            print('Template syntax error: %s in %s, line %d' % (
                exc.message, exc.filename, exc.lineno))
            sys.exit(1)

        nets = []
        for index, vlan in enumerate(self.cfg.yield_depl_netw_mgmt_vlan()):
            if vlan is not None:
                net = {}
                net[self.VLAN] = vlan
                net[self.IPADDR] = self.cfg.get_depl_netw_mgmt_cont_ip(index)
                net[self.PREFIX] = self.cfg.get_depl_netw_mgmt_prefix(index)
                nets.append(net)
        for index, type_ in enumerate(self.cfg.yield_depl_netw_client_type()):
            if type_ is not None:
                net = {}
                net[self.TYPE] = type_
                net[self.VLAN] = self.cfg.get_depl_netw_client_vlan(index)
                net[self.IPADDR] = self.cfg.get_depl_netw_client_cont_ip(index)
                net[self.PREFIX] = self.cfg.get_depl_netw_client_prefix(index)
                nets.append(net)
        distname, _, _ = platform.linux_distribution()

        uid_range, gid_range = self.get_lxc_uid_gid_range()
        assert(int(uid_range.split()[0]) + int(uid_range.split()[1]) > 101000)
        assert(int(gid_range.split()[0]) + int(gid_range.split()[1]) > 101000)

        try:
            with open(self.LXC_CONF, 'w') as lxc_conf:
                lxc_conf.write(template.render(
                    distribution=distname, networks=nets,
                    uidrange=uid_range, gidrange=gid_range))
        except:
            self.log.error('Failed to create: %s' % self.LXC_CONF)
            sys.exit(1)

        self.log.debug('Successfully created: %s' % self.LXC_CONF)

        if not os.path.exists(os.path.join(HOME, '.config', 'lxc')):
            self.log.debug('Creating path(s) {}'.format('.config/lxc'))
            os.makedirs(os.path.join(HOME, '.config', 'lxc'))
        os.system('cp ' + os.path.join(GEN_PLAY_PATH, 'lxc-conf.yml') + ' ' +
                  os.path.join(HOME, '.config', 'lxc', 'default.conf'))

        if not os.path.exists(os.path.join(HOME, '.local', 'share', 'lxc')):
            self.log.debug('Creating path(s) {}'.format('.local/share/lxc'))
            os.makedirs(os.path.join(HOME, '.local', 'share', 'lxc'))

    def get_lxc_uid_gid_range(self):
        username = pwd.getpwuid(os.getuid())[0]
        if OPSYS == 'Ubuntu':
            try:
                f = open('/etc/subuid', 'r')
                data = f.read()
                uid_range = re.search(username + r':(\d+):(\d+)',
                                      data, re.MULTILINE)
                uid_range = uid_range.group(1) + ' ' + uid_range.group(2)
            except IOError as e:
                self.log.error(e)
                raise Exception(e)
            except AttributeError as e:
                self.log.error('Error getting uid for user: {}'.format(username))
                raise Exception(e)

            try:
                f = open('/etc/subgid', 'r')
                data = f.read()
                gid_range = re.search(username + r':(\d+):(\d+)',
                                      data, re.MULTILINE)
                gid_range = gid_range.group(1) + ' ' + gid_range.group(2)
            except IOError as e:
                self.log.error(e)
                raise
            except AttributeError as e:
                self.log.error('Error getting uid for user: {}'.format(username))
                raise

            return uid_range, gid_range


if __name__ == '__main__':
    logger.create()
    LXC_CONF = LxcConf()
    LXC_CONF.create()
