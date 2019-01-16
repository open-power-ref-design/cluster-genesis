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

import argparse
import netaddr
import socket
from pyroute2 import IPRoute

import lib.logger as logger


def ip_route_get_to(host):
    """Get interface IP that routes to hostname or IP address

    Args:
        host (str): Hostname or IP address

    Returns:
        str: Interface IP with route to host
    """
    log = logger.getlogger()

    # Check if host is given as IP address
    if netaddr.valid_ipv4(host, flags=0):
        host_ip = host
    else:
        try:
            host_ip = socket.gethostbyname(host)
        except socket.gaierror as exc:
            log.warning("Unable to resolve host to IP: '{}' exception: '{}'"
                        .format(host, exc))
    with IPRoute() as ipr:
        route = ipr.route('get', dst=host_ip)[0]['attrs'][3][1]

    return route


if __name__ == '__main__':
    logger.create()
    parser = argparse.ArgumentParser(description='Get interface IP that '
                                     'routes to hostname or IP address.')
    parser.add_argument('host', type=str, help='Hostname or IP address')
    args = parser.parse_args()

    print(ip_route_get_to(args.host))
