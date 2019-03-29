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

import os
import sys
import code
import getpass
import yaml

import lib.logger as logger
from lib.utilities import Color
from lib.genesis import GEN_PATH

from lib.utilities import sub_proc_display, sub_proc_exec

def main():

    print('\n')
    log = logger.getlogger()
    log.debug('log this')

    sub_proc_display('ls ~/power-up | grep inv', shell=True)
    inv_file = input('\nInfo - Select inventory file: ')
    invntory_file_path = os.path.join(GEN_PATH, f'{inv_file}')

    try:
        print(f"\nINFO - Loading {inv_file} data \n")
        load_inv = open(f'{invntory_file_path}')
        with load_inv as f:
            grab = yaml.load(f)
            hostname = grab['nodes'][0]['hostname']
            pxe_ip = grab['nodes'][0]['pxe']['ipaddrs'][0]
            user = grab['nodes'][0]['os']['users'][0]['name']
            base = f'ssh root@{hostname} '

    except FileNotFoundError as exc:
        print(f'File not found: {invntory_file_path}. Err: {exc}')
        sys.exit()

    def cmd(process):
        sub_proc_display(f'{base}{process}', shell=True)

                        #Updating '/etc/hosts' file

    client_info = f'{hostname} {pxe_ip} {hostname}.lan'

    print ("\nINFO - Formatting to append to hosts files:\n"
           f"\n   >>>>    {client_info}\n")

    opt_menu = True
    while opt_menu == True:
        opt = input('\nWould you like to update localhost information? y or n \n')
        if opt == 'y':
            print("\nINFO - Appending to localhost '/etc/hosts' file \n")
            sub_proc_display(f'echo "{client_info} >> /etc/hosts"',shell=True)
            opt_menu = False
        elif opt == 'n':
            print("\nINFO - *CAUTION* will cause communication errors with client! ")
            opt_menu = False
        else:
            print('Try again')

    opt_menu = True
    while opt_menu == True:
        opt = input('\nWould you like to update client information? y or n \n')
        if opt == 'y':
            print("\nINFO - Appending to client '/etc/hosts' file \n")
            cmd(f'echo "{client_info} >> /etc/hosts"')
            opt_menu = False
        elif opt == 'n':
            print("\nINFO - *CAUTION* will cause communication errors with client! ")
            opt_menu = False
        else:
            print('Try again')

#                        #remove default routes

    opt0_menu = True
    while opt0_menu == True:
        print("\nINFO - remove default routes \n")
        opt_0 = input('Would you like to remove default route on client? y or n \n')
        if opt_0 == 'y':
            cmd('ip route del default')
            print("\nINFO - Checking client default route \n")
            cmd('ip route')
            opt0_menu = False
        elif opt_0 == 'n':
            print("\nINFO - Procceding")
            opt0_menu = False
        else:
            print('Try again')

                        #interfaces for bootmode

    opt1_menu = True
    print("\nINFO - Check interfaces for bootmode \n")
    cmd('cat /etc/sysconfig/network-scripts/ifcfg-en* | grep BOOTPROTO')
    input('\nPress any key to continue')

    while opt1_menu == True:
        print("\nINFO - Edit interfaces for bootmode \n")
        opt_1 = input('Would you like to update bootmode status? y or n \n')
        if opt_1 == 'y':
            interface = input('Select interface: ')
            cmd(f'vi /etc/sysconfig/network-scripts/ifcfg-{interface}')
            print('Verifing.\n')
            cmd('cat /etc/sysconfig/network-scripts/ifcfg-* | grep BOOTPROTO')
        elif opt_1 == 'n':
            print("\nINFO - Procceding")
            opt1_menu = False
        else:
            print('Try again')

 #                       #Add a route to the NFS share

    opt2_menu = True
    print("\nINFO - Add a route to the NFS share \n")
    opt_2 = input('Would you like to update NFS share? y or n \n')

    while opt2_menu == True:
        if opt_2 == 'y':
            cmd('ip route add 9.3.89.00/24 via 192.168.47.3')
            print('Verifing.\n')
            cmd('ip route')
            opt2_menu = False
        elif opt_2 == 'n':
            print("\nINFO - Procceding")
            opt2_menu = False
        else:
            print('Try again')

                        #edit PXE interface on client

    opt3_menu = True
    print("\nINFO - Edit information for PXE interface on client  \n")
    opt_3 = input("Would you like to edit PXE interface on client ? y or n \n")

    while opt3_menu == True:
        if opt_3 == 'y':
            interface = input('Select interface: ')
            ifcfg_loc = f'/etc/sysconfig/network-scripts/ifcfg-{interface}'

            cmd('echo "GATEWAY0=192.168.47.3 >> {ifcfg_loc}"')
            cmd('echo "NETMASK0=255.255.255.0 >> {ifcfg_loc}"')
            cmd('echo "ADDRESS0=9.3.89.0 >> {ifcfg_loc}"')

            print('Verifing.\n')

           cmd(f'cat /etc/sysconfig/network-scripts/ifcfg-{interface}')
            opt3_menu = False
        elif opt_3 =='n':
            print("\nINFO - Procceding")
            opt3_menu = False
        else:
            print('Try again')

#                        #Install nfs-utils

    opt4_menu = True
    print("\nINFO - Install nfs-utils \n")
    opt_4 = input("Install nfs-utils? y or n \n")

    while opt4_menu == True:
        if opt_4 == 'y':
            cmd('yum install nfs-utils')
            opt4_menu = False
        elif opt_4 =='n':
            print("\nINFO - Procceding")
            opt4_menu = False
        else:
            print('Try again')

    input('Press any key to continue')

# 1 of 2                        #Create Mount

    opt5_menu = True
    print("\nINFO - Create Mount  \n")
    opt_5 = input("Would you like to create '/nfs/pwrai' mount on client ? y or n \n")

    while opt5_menu == True:
        if opt_5 == 'y':
            cmd('mkdir -p /nfs/pwrai && sudo mount -t nfs -o vers=3 9.3.89.51:'
                '/media/shnfs_sdo/nfs/pwrai /nfs/pwrai')
            cmd('echo 9.3.89.51:/media/shnfs_sdo/nfs/pwrai  /nfs/pwrai  '
                'nfs nolock,acl,rsize=8192,wsize=8192,timeo=14,intr,nfsvers=3 0 0 '
                '>> /etc/fstab')
            print('Verifing.\n')
            cmd('df')
            opt5_menu = False
        elif opt_5 =='n':
            print("\nINFO - Procceding")
            opt5_menu = False
        else:
            print('Try again')

 #                       #Move dvd1.repo from 'yum.repos.d' directory

    print ('\nINFO - Moving the iso cd repo setup\n')
    try:
        cmd('mv /etc/yum.repos.d/*dvd1.repo ~ ')
    except FileNotFoundError as exc:
        print(f'dvd iso not found. Err: {exc}')
        cmd('rm -rf /etc/yum.repos.d/*dvd1.repo')

#                        #Reboot Client

    print('INFO - Client Reboot')
    input('Press any key to continue')
    cmd('reboot')
    print('Completed')


#    optx_menu = True
#    print("\nINFO -  \n")
#    opt_x = input(" ? y or n \n")

#    while optx_menu == True:
#        if opt_x == 'y':
#            cmd('')
#            print('Verifing.\n')
#            cmd('')
#            optx_menu = False
#        elif opt_x =='n':
#            print("\nINFO - Procceding")
#            optx_menu = False
#        else:
#            print('Try again')
#    input('Press any key to continue')


if __name__ == '__main__':
    """Simple python template
    """

    logger.create('nolog', 'info')
    log = logger.getlogger()

main()
