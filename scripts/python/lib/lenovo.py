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

import re
import os.path
import datetime

import lib.logger as logger
from lib.switch_exception import SwitchException
from lib.switch_common import SwitchCommon
from lib.genesis import GEN_PASSIVE_PATH, GEN_PATH
from lib.utilities import get_col_pos


class Lenovo(SwitchCommon):
    """Class for configuring and retrieving information for a Lenovo
    switch.  This class works with the Lenovo G8052.  Similar
    Lenovo switches may work or may need some methods overridden.
    This class can be instantiated in 'active' mode, in which case the
    switch will be configured or in 'passive' mode in which case the
    commands needed to configure the switch are written to a file.
    When in passive mode, information requests will return 'None'.
    In passive mode, a filename can be generated which
    will contain the active mode switch commands used for switch
    configuration. This outfile will be written to the
    'cluster-genesis/passive' directory if it exists or to the
    'cluster-genesies' directory if the passive directory does not
    exist. If no outfile name is provided a default name is used.
    In active mode, the 'host, userid and password named variables
    are required. If 'mode' is not provided, it is defaulted to 'passive'.

    Args:
        host (string): Management switch management interface IP address
        or hostname or if in passive mode, a fully qualified filename of the
        acquired mac address table for the switch.
        userid (string): Switch management interface login user ID.
        password (string): Switch management interface login password.
        mode (string): Set to 'passive' to run in passive switch mode.
            Defaults to 'active'
        outfile (string): Name of file to direct switch output to when
        in passive mode.
        access_list (list of str): Optional list containing host, userid
        and password.
    """
    ENABLE_REMOTE_CONFIG = 'en ; configure terminal ; {} '
    SEP = ';'
    IFC_ETH_CFG = 'no prompting ; interface port {}'
    SHOW_PORT = 'show interface trunk'
    PORT_PREFIX = ''
    CLEAR_MAC_ADDRESS_TABLE = 'clear mac-address-table'
    SHOW_MAC_ADDRESS_TABLE = 'show mac-address-table'
    MGMT_INTERFACE_CONFIG = 'interface ip {}'
    SET_INTERFACE_IPADDR = ';ip address {}'
    SET_INTERFACE_MASK = ';ip netmask {}'
    SET_VLAN = ';vlan {}'
    ENABLE_INTERFACE = ';enable'
    CREATE_INTERFACE = MGMT_INTERFACE_CONFIG + SET_INTERFACE_IPADDR +\
        SET_INTERFACE_MASK + SET_VLAN + ENABLE_INTERFACE
    REMOVE_IFC = 'no interface ip {}'
    SHOW_INTERFACE = 'show interface ip {}'
    UP_STATE_IFC = 'up'
    MAX_INTF = 128

    def __init__(self, host=None, userid=None, password=None, mode=None,
                 outfile=None):
        self.log = logger.getlogger()
        self.mode = mode
        self.host = host
        if self.mode == 'active':
            self.userid = userid
            self.password = password
        elif self.mode == 'passive':
            if os.path.isdir(GEN_PASSIVE_PATH):
                self.outfile = GEN_PASSIVE_PATH + '/' + outfile
            else:
                self.outfile = GEN_PATH + '/' + outfile
            f = open(self.outfile, 'a+')
            f.write(str(datetime.datetime.now()) + '\n')
            f.close()
        super(Lenovo, self).__init__(host, userid, password, mode, outfile)

    def show_ports(self, format='raw'):
        def _get_avlans(line):
            avlans = ''
            line = line.split(' ')
            for item in line:
                if '-' in item:
                    item = item.split('-')
                    n = int(item[0])
                    while n <= int(item[1]):
                        avlans = avlans + ', ' + str(n)
                        n += 1
                else:
                    avlans = avlans + ', ' + item
            return avlans[2:]

        if self.mode == 'passive':
            return None
        ports = {}
        port_info = self.send_cmd(self.SHOW_PORT)
        if format == 'raw' or format is None:
            return port_info
        elif format == 'std':
            indcs = get_col_pos(port_info, ('Port', 'Tag', 'PVID', 'VLAN\(s'))
            port_info = port_info.splitlines()
            for line in port_info:
                # pad to 86 chars
                line = f'{line:<86}'
                # look for rows (look for first few fields)
                match = re.search(r'^\s*\w+\s+\d+\s+(y|n)', line)
                if match:
                    port = str(int(line[indcs['Port'][0]:indcs['Port'][1]]))
                    mode = line[indcs['Tag'][0]:indcs['Tag'][1]]
                    mode = 'access' if 'n' in mode else 'trunk'
                    pvid = str(int(line[indcs['PVID'][0]:indcs['PVID'][1]]))
                    avlans = line[indcs['VLAN\(s'][0]:indcs['VLAN\(s'][1]].strip(' ')
                    avlans = _get_avlans(avlans)
                    ports[port] = {'mode': mode, 'nvlan': pvid, 'avlans': avlans}
                # look for avlan continuation lines
                # look for leading spaces (10 is arbitrary)
                if f"{' ':<10}" == line[:10]:
                    avlans = line[indcs['VLAN\(s'][0]:indcs['VLAN\(s'][1]].strip(' ')
                    match = re.search(r'^(\d+ |(\d+-\d+ ))+\d+', avlans)
                    if match:
                        avlans = _get_avlans(match.group(0))
                        ports[port]['avlans'] += f', {avlans}'
            return ports

    def remove_interface(self, vlan, host, netmask):
        """Removes an in-band management interface.
        Args:
            host (string): hostname or ipv4 address in dot decimal notation
            netmask (string): netmask in dot decimal notation
            vlan (int or string): value between 1 and 4094.
        raises:
            SwitchException if unable to remove interface
        """
        vlan = str(vlan)
        interfaces = self.show_interfaces(vlan, host, netmask, format='std')
        if interfaces[-1][0]['configured']:
            self.send_cmd(self.REMOVE_IFC.format(interfaces[-1][0]['found ifc']))
            interfaces = self.show_interfaces(vlan, host, netmask, format='std')
            if interfaces[-1][0]['configured']:
                self.log.debug('Failed to remove interface Vlan {}.'.format(vlan))
                raise SwitchException('Failed to remove interface Vlan {}.'.format(vlan))
        else:
            self.log.debug('Interface vlan {} does not exist.'.format(vlan))
        return

    def show_interfaces(self, vlan='', host=None, netmask=None, format=None):
        """Gets from the switch a list of programmed in-band interfaces. The
        standard format consists of a list of lists. Each list entry contains
        the vlan number, the ip address, netmask and the number of the interface.
        which do not number the in-band interfaces, the last item in each list
        is set to '-'. When vlan, host and netmask are specified, the last list
        item contains 'True' or 'False' indicating whether an interface already
        exists with the specified vlan, host and netmask. For switches which do
        number the interfaces, (ie Lenovo) the last list item also contains the
        next available interface number and the number of the found interface.
        Args:
            vlan (string): String representation of integer between
                1 and 4094. If none specified, usually the default vlan is used.
            host (string): hostname or ipv4 address in dot decimal notation
            netmask (string): netmask in dot decimal notation
            format (string): 'std' If format is not specified, The native (raw)
                format is returned. If format is set to 'std', a 'standard' format
                is returned.
        Returns:
        If format is unspecified, returns a raw string of data as it
        comes from the switch. If format == 'std' a standard format is returned.
        Standard format consists of a list of lists. Each list entry contains
        the vlan number, the ip address, netmask and the number of the interface.
        For switches which do not number the in-band interfaces, the last item
        in each list is set to '-'. When vlan, host and netmask are specified,
        the last list item contains a dictionary. The dictionary has three entries;
            'configured' : set to True or False indicating whether an
                interface already exists with the specified vlan, host and netmask.
            'avail ifc' : For switches which do number the interfaces, (ie Lenovo)
                this dictioanary entry contains the next available interface number.
            'found ifc' : For switches which do number the interfaces, this entry
                contains the number of the found interface.
        """
        if self.mode == 'passive':
            return None
        ifcs = []
        vlan = str(vlan)
        found = False
        ava_ifc, fnd_ifc, cnt = 0, 0, 0
        ifc_info = self.send_cmd(self.SHOW_INTERFACE.format(''))
        if format is None:
            return ifc_info
        ifc_info = ifc_info.splitlines()
        for line in ifc_info:
            match = re.search(r'^(\d+):\s+IP4\s+(\w+.\w+.\w+.\w+)\s+(\w+.\w+.\w+.\w+)'
                              '\s+\w+.\w+.\w+.\w+,\s+vlan\s(\d+),', line)
            if match:
                cnt += 1
                ifcs.append(
                    [match.group(4), match.group(2), match.group(3), match.group(1)])
                if [vlan, host, netmask, match.group(1)] in ifcs:
                    fnd_ifc = match.group(1)
                    found = True
                if cnt != int(match.group(1)) and ava_ifc == 0:
                    ava_ifc = cnt
        ifcs.append(
            [{'configured': found,
                'avail ifc': str(ava_ifc),
                'found ifc': str(fnd_ifc)}])
        return ifcs

    def configure_interface(self, host, netmask, vlan=1, intf=None):
        """Configures a management interface. This implementation checks
        if the host ip is already in use. If it is, a check is made to
        see if it is configured as specified. If not, an exception is raised.
        Lenovo numbers interfaces. If no interface number is specified,
        the next available unconfigured interface is used. The specified
        vlan will be created if it does not already exist.

        When implementing this method for a new switch, minimally this method
        should configure (overwrite if necessary) the specified interface.

        Args:
            host (string): hostname or ipv4 address in dot decimal notation
            netmask (string): netmask in dot decimal notation
            vlan (string): Optional. string representation of integer between
            1 and 4094. If none specified, usually the default vlan is used.
            intf (string): optional. String representation of integer between
            1 and 128.
        raises:
            SwitchException if unable to program interface
        """
        interfaces = self.show_interfaces(vlan, host, netmask, format='std')
        if self.mode == 'active' and interfaces[-1][0]['configured']:
            self.log.debug(
                'Switch interface {} already configured'.format(
                    interfaces[-1][0]['found ifc']))
            return
        if vlan is not None:
            self.create_vlan(vlan)
        if self.mode == 'active' and intf is None:
            intf = interfaces[-1][0]['avail ifc']
        self.send_cmd(self.CREATE_INTERFACE.format(intf, host, netmask, vlan))
        interfaces = self.show_interfaces(vlan, host, netmask, format='std')
        if self.mode == 'active' and not interfaces[-1][0]['configured']:
            self.log.error(
                'Failed configuring management interface ip {}'.format(intf))
            raise SwitchException(
                'Failed configuring management interface ip {}'.format(intf))
        return


class switch(object):
    @staticmethod
    def factory(host=None, userid=None, password=None, mode=None,
                outfile=None):
        return Lenovo(host, userid, password, mode, outfile)
