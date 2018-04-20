#!/usr/bin/env python
"""Config schema validation"""

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

import jsonschema
from jsonschema import validate
import jsl

import lib.logger as logger
from lib.exception import UserException, UserCriticalException


def _string_int_field(**kwargs):
    return jsl.fields.AnyOfField(
        [
            jsl.fields.StringField(),
            jsl.fields.IntField()],
        **kwargs)


def _string_int_array_field(**kwargs):
    return jsl.fields.AnyOfField(
        [
            jsl.fields.StringField(),
            jsl.fields.IntField(),
            jsl.fields.ArrayField(_string_int_field())],
        **kwargs)


class Globals(jsl.Document):
    introspection = jsl.fields.BooleanField()
    env_variables = jsl.fields.DictField()
    switch_mode_mgmt = jsl.fields.StringField()
    switch_mode_data = jsl.fields.StringField()
    dhcp_lease_time = _string_int_field()


class LocationRacks(jsl.Document):
    label = _string_int_field()
    room = _string_int_field()
    row = _string_int_field()
    cell = _string_int_field()


class Location(jsl.Document):
    time_zone = jsl.fields.StringField()
    data_center = _string_int_field()
    racks = jsl.fields.ArrayField(
        jsl.fields.DocumentField(LocationRacks))


class DeployerNetworks(jsl.Document):
    mgmt = jsl.fields.ArrayField(jsl.fields.DictField(
        properties={
            'device': jsl.fields.StringField(required=True),
            'interface_ipaddr': jsl.fields.IPv4Field(),
            'container_ipaddr': jsl.fields.IPv4Field(),
            'bridge_ipaddr': jsl.fields.IPv4Field(),
            'vlan': jsl.fields.IntField(),
            'netmask': jsl.fields.IPv4Field(),
            'prefix': jsl.fields.IntField()},
        additional_properties=False,
        required=True))
    client = jsl.fields.ArrayField(jsl.fields.DictField(
        properties={
            'type': jsl.fields.StringField(required=True),
            'device': jsl.fields.StringField(required=True),
            'container_ipaddr': jsl.fields.IPv4Field(required=True),
            'bridge_ipaddr': jsl.fields.IPv4Field(required=True),
            'vlan': jsl.fields.IntField(required=True),
            'netmask': jsl.fields.IPv4Field(),
            'prefix': jsl.fields.IntField()},
        additional_properties=False,
        required=True))


class Deployer(jsl.Document):
    gateway = jsl.fields.BooleanField()
    networks = jsl.DocumentField(DeployerNetworks)


class SwitchesMgmtData(object):
    interfaces = jsl.fields.DictField(
        properties={
            'type': jsl.fields.StringField(required=True),
            'ipaddr': jsl.fields.IPv4Field(required=True),
            'vlan': jsl.fields.IntField(),
            'port': _string_int_field(),
            'netmask': jsl.fields.IPv4Field(),
            'prefix': jsl.fields.IntField()},
        additional_properties=False,
        required=True)

    links = jsl.fields.DictField(
        properties={
            'target': jsl.fields.StringField(required=True),
            'ports': _string_int_array_field(required=True),
            'ipaddr': jsl.fields.IPv4Field(),
            'vlan': jsl.fields.IntField(),
            'vip': jsl.fields.IPv4Field(),
            'netmask': jsl.fields.IPv4Field(),
            'prefix': jsl.fields.IntField()},
        additional_properties=False,
        required=True)

    mgmt_data = jsl.fields.DictField(
        properties={
            'label': jsl.fields.StringField(required=True),
            'hostname': jsl.fields.StringField(),
            'userid': jsl.fields.StringField(),
            'password': jsl.fields.StringField(),
            'ssh_key': jsl.fields.StringField(),
            'class': jsl.fields.StringField(),
            'rack_id': _string_int_field(),
            'rack_eia': _string_int_field(),
            'interfaces': jsl.fields.ArrayField(interfaces),
            'links': jsl.fields.ArrayField(links)},
        additional_properties=False,
        required=True)


class Switches(jsl.Document):
    mgmt = jsl.fields.ArrayField(SwitchesMgmtData.mgmt_data)
    data = jsl.fields.ArrayField(SwitchesMgmtData.mgmt_data)


class Interfaces(jsl.Document):
    label = jsl.fields.StringField()
    description = jsl.fields.StringField()
    iface = jsl.fields.StringField()
    address_start = jsl.fields.IPv4Field()
    address_list = jsl.fields.ArrayField()
    method = jsl.fields.StringField()
    dns_search = jsl.fields.StringField()
    dns_nameservers = jsl.fields.StringField()
    broadcast = jsl.fields.IPv4Field()
    netmask = jsl.fields.IPv4Field()
    gateway = jsl.fields.IPv4Field()
    mtu = jsl.fields.IntField()
    vlan_raw_device = jsl.fields.StringField()
    pre_up = jsl.fields.StringField()
    bridge_stp = jsl.fields.BooleanField()
    bridge_maxage = jsl.fields.IntField()
    bridge_fd = jsl.fields.IntField()
    bridge_ports = jsl.fields.StringField()
    bridge_hello = jsl.fields.IntField()
    bond_primary = jsl.fields.StringField()
    bond_master = jsl.fields.StringField()
    bond_mode = jsl.fields.StringField()
    bond_miimon = jsl.fields.IntField()
    bond_slaves = jsl.fields.StringField()
    DEVICE = jsl.fields.StringField()
    TYPE = jsl.fields.StringField()
    IPADDR_start = jsl.fields.IPv4Field()
    IPADDR_list = jsl.fields.ArrayField()
    BOOTPROTO = jsl.fields.StringField()
    ONBOOT = jsl.fields.BooleanField()
    ONPARENT = jsl.fields.BooleanField()
    SEARCH = jsl.fields.StringField()
    DNS1 = jsl.fields.IPv4Field()
    DNS2 = jsl.fields.IPv4Field()
    NETMASK = jsl.fields.IPv4Field()
    GATEWAY = jsl.fields.IPv4Field()
    BROADCAST = jsl.fields.IPv4Field()
    VLAN = jsl.fields.BooleanField()
    MTU = jsl.fields.IntField()
    STP = jsl.fields.BooleanField()
    MASTER = jsl.fields.StringField()
    SLAVE = jsl.fields.BooleanField()
    BRIDGE = jsl.fields.StringField()
    BONDING_OPTS = jsl.fields.StringField()
    BONDING_MASTER = jsl.fields.BooleanField()
    NM_CONTROLLED = jsl.fields.BooleanField()


class Networks(jsl.Document):
    label = jsl.fields.StringField()
    interfaces = jsl.fields.ArrayField(
        jsl.fields.StringField(),
        required=True)


class SoftwareBootstrap(jsl.Document):
    hosts = jsl.fields.StringField()
    executable = jsl.fields.StringField()
    command = jsl.fields.StringField()


class SchemaDefinition(jsl.Document):
    version = jsl.fields.StringField(required=True)

    globals = jsl.fields.DocumentField(Globals)

    location = jsl.fields.DocumentField(Location)

    deployer = jsl.DocumentField(Deployer)

    switches = jsl.fields.DocumentField(Switches)

    interfaces = jsl.fields.ArrayField(
        jsl.fields.DocumentField(Interfaces),
        required=True)

    networks = jsl.fields.ArrayField(jsl.fields.DocumentField(Networks))

    node_templates = jsl.fields.ArrayField(required=True)

    software_bootstrap = jsl.fields.ArrayField(
        jsl.fields.DocumentField(SoftwareBootstrap))


class ValidateConfigSchema(object):
    """Config schema validation

    Args:
        config (object): Config
    """

    def __init__(self, config):
        self.log = logger.getlogger()
        self.config = config

    def validate_config_schema(self):
        """Config schema validation

        Exception:
            If schema validation fails
        """

        schema = SchemaDefinition.get_schema(ordered=True)
        try:
            validate(
                self.config, schema, format_checker=jsonschema.FormatChecker())
        except jsonschema.exceptions.ValidationError as error:
            if error.cause is None:
                path = None
                for index, element in enumerate(error.path):
                    if isinstance(element, int):
                        path += '[{}]'.format(element)
                    else:
                        if index == 0:
                            path = '{}'.format(element)
                        else:
                            path += '.{}'.format(element)
                exc = 'Schema validation failed - {} - {}'.format(
                    path, error.message)
            else:
                exc = 'Schema validation failed - {} - {}'.format(
                    error.cause, error.message)
            if 'Additional properties are not allowed' in error.message:
                raise UserException(exc)
            else:
                raise UserCriticalException(exc)
