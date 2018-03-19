
Appendix - H Recovering from Genesis Issues
===========================================

Playbook "lxc-create.yml" fails to create lxc container.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  Verify python virtual environment is activated by running *which
   ansible-playbook*. This should return the path
   \*/cluster-genesis/deployenv/bin/ansible-playbook. If something else
   is returned (including nothing) cd into the cluster-genesis directory
   and re-run *source scripts/setup-env*.

Verify that the Cluster Genesis network bridges associated with the management
and client vlans specified in the config.yml file are up and that there are
two interfaces attached to each bridge.  One of these interfaces should be a
tagged vlan interface associated with the physical port to be used by by 
Cluster Genesis.  The other should be a veth pair attached to the Cluster Genesis
container::

    $ gen status

Verify than both bridges have an ip address assigned::

    ip address show brn  (n whould be the vlan number)

Switch connectivity Issues:
~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  Verify connectivity from deployer container to management interfaces
   of both management and data switches. Be sure to use values assigned
   to the [ipaddr,userid,password]-[mgmt,data]-switch keys in the
   config.yml. These switches can be on any subnet except the one to be
   used for your cluster management network, as long as they're
   accessible to the deployer system.
-  Verify SSH is enabled on the data switch and that you can ssh
   directly from deployer to the switch using the ipaddr,userid, and
   password keys defined in the config.yml

Missing Hardware
~~~~~~~~~~~~~~~~~

Hardware can fail to show up for various reasons. Most of the time these
are do to miscabling or mistakes in the config.yml file. The Node
discovery process starts with discovery of mac addresses and DHCP hand
out of ip addresses to the BMC ports of the cluster nodes. This process
can be monitored by checking the DHCP lease table after booting the BMCs
of the cluster nodes. During execution of the install_1.yml playbook, at
the prompt;

"Please reset BMC interfaces to obtain DHCP leases. Press <enter> to
continue"

After rebooting the BMCs and before pressing <enter>, you can execute
from a second shell::

    gen status

Alternately to see just the leases table, log into the deployer container::

    $ ssh ~/.ssh/id_rsa_ansible-generated deployer@address

The address used above can be read from the 'gen status' display.  It is
the second address of the subnet specified by the ipaddr-mgmt-network: key
in the config.yml file.  After logging in::

    deployer@ubuntu-14-04-deployer:~$ cat /var/lib/misc/dnsmasq.leases

*1471870835 a0:42:3f:30:61:cc 192.168.3.173 \* 01:a0:42:3f:30:61:cc*

*1471870832 70:e2:84:14:0a:10 192.168.3.153 \* 01:70:e2:84:14:0a:10*

*1471870838 a0:42:3f:32:6f:3f 192.168.3.159 \* 01:a0:42:3f:32:6f:3f*

*1471870865 a0:42:3f:30:61:fe 192.168.3.172 \* 01:a0:42:3f:30:61:fe*

**To follow the progress continually you can execute;**

*deployer@ubuntu-14-04-deployer:~$ tail -f /var/lib/misc/dnsmasq.leases*

**You can also check what switch ports these mac addresses are connected
to by logging into the management switch and executing;**

*RS G8052>show mac-address-table*

* MAC address VLAN Port Trnk State Permanent Openflow*

* ----------------- -------- ------- ---- ----- --------- --------*

* 00:00:5e:00:01:99 1 48 FWD N *

* 00:16:3e:53:ae:19 1 20 FWD N *

* 0c:c4:7a:76:c8:ec 1 37 FWD N *

* 40:f2:e9:23:82:be 1 11 FWD N *

* 40:f2:e9:24:96:5e 1 1 FWD N *

* 5c:f3:fc:31:05:f0 1 15 FWD N *

* 5c:f3:fc:31:06:2a 1 18 FWD N *

* 5c:f3:fc:31:06:2c 1 17 FWD N *

* 5c:f3:fc:31:06:ec 1 13 FWD N *

* 70:e2:84:14:02:92 1 3 FWD N *

**For missing mac addresses, verify that port numbers in the above
printout match the ports specified in the config.yml file. Mistakes can
be corrected by correcting cabling, correcting the config.yml file and
rebooting the BMCs.**

Mistakes in the config.yml file require a restart of the deploy process.
(ie rerunning gen deploy.)  Before doing so remove the existing Genesis container
by running the 'tear-down' script and answering yes to the prompt to destroy the container
and it's associated bridges.

Depending on the error, it may be possible to rerun the deploy playbooks individually::

    $ gen install_1
    $ gen install_2

Alternately, from the cluster-genesis/playbooks directory::

    $ ansible-playbook -i hosts install_1.yml -K
    $ ansible-playbook -i hosts install_2.yml -K

Before rerunning the above playbooks, make a backup of any existing
inventory.yml files and then create an empty inventory.yml file::

    $ mv inventory.yml inventory.yml.bak
    $ touch inventory.yml

**Once all the BMC mac addresses have been given leases, press return in
the genesis execution window.**

**Common Supermicro PXE bootdev Failure**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Supermicro servers often fail to boot PXE devices on first try. In
order to get the MAC addresses of the PXE ports our code sets the
bootdev on all nodes to pxe and initiates a power on. Supermicro servers
do *\ **not**\ * reliably boot pxe (usually will instead choose one of
the disks). This *\ *will usually show up as a python key error in the
"container/inv\_add\_pxe\_ports.yml" playbook. The only remedy is to
retry the PXE boot until it's successful (usually *\ *within*\ * 2-3
tries). To retry use ipmitool from the deployer. The tricky part,
however, is determining 1) which systems failed to PXE boot and 2) what
the current BMC IP address is. **

****

**To determine which systems have failed to boot, go through the
following bullets in this section (starting with "Verify port
lists...")**

****

**To determine what the corresponding BMC addresss is view the
inventory.yml file. At this point the BMC ipv4 and mac address will
already be populated in the inventory.yml within the container. To find
out:**

*ubuntu@bloom-deployer: cluster-genesis/playbooks$ grep "^deployer"
hosts*

*deployer ansible\_user=deployer
ansible\_ssh\_private\_key\_file=/home/ubuntu/.ssh/id\_rsa\_ansible-generated
ansible\_host=192.168.16.2*


*ubuntu@bloom-deployer:~/cluster-genesis/playbooks$ ssh -i
/home/ubuntu/.ssh/id\_rsa\_ansible-generated deployer@192.168.16.2*


*Welcome to Ubuntu 14.04.4 LTS (GNU/Linux 4.2.0-42-generic x86\_64)*

* \* Documentation: https://help.ubuntu.com/*

*Last login: Mon Aug 22 12:14:17 2016 from 192.168.16.3*


*deployer@ubuntu-14-04-deployer:~$ grep -e hostname -e ipmi
cluster-genesis/inventory.yml*

* - hostname: mgmtswitch1*

* - hostname: dataswitch1*

* - hostname: controller-1*

* userid-ipmi: ADMIN*

* password-ipmi: ADMIN*

* port-ipmi: 29*

* mac-ipmi: 0c:c4:7a:4d:88:26*

* ipv4-ipmi: 192.168.16.101*

* - hostname: controller-2*

* userid-ipmi: ADMIN*

* password-ipmi: ADMIN*

* port-ipmi: 27*

* mac-ipmi: 0c:c4:7a:4d:87:30*

* ipv4-ipmi: 192.168.16.103*

*~snip~*


**Verify port lists within cluster-genesis/config.yml are correct:**

*~snip~*

*node-templates:*

*controller1:*

*~snip~*

* ports:*

* ipmi:*

* rack1:*

* - 9*

* - 11*

* - 13*

* pxe:*

* rack1:*

* - 10*

* - 12*

* - 14*

* eth10:*

* rack1:*

* - 5*

* - 7*

* - 3*

* eth11:*

* rack1:*

* - 6*

* - 8*

* - 4*

*~snip~*

**On the management switch;**

*RS G8052>show mac-address-table*

*in the mac address table, look for the missing pxe ports. Also note the
mac address for the corresponding BMC port. Use ipmitool to reboot the
nodes which have not pxe booted succesfully.*



*Stopping and resuming progress*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In general, to resume progress after a play stops on error (presumably
after the error has been understood and corrected!) the failed playbook
should be re-run and subsequent plays run as normal. In the case of
"cluster-genesis/playbooks/install_1.yml" and
"cluster-genesis/playbooks/install_2.yml" around 20 playbooks are
included. If one of these playbooks fail then edit the .yml file and
and comment plays that have passed by writing a "#" at the front of the
line. Be sure *not* to comment out the playbook that failed so that it
will re-run. Here's an example of a modified
"cluster-genesis/playbooks/install.yml" where the
user wishes to resume after a data switch connectivity problem caused
the "container/set\_data\_switch\_config.yml" playbook to fail:

* 1 ---*

* 2 # Copyright 2018, IBM US, Inc.*

* 3 *

*~ 4 #- include: lxc-update.yml*

*~ 5 #- include: container/cobbler/cobbler\_install.yml*

*~ 6 #- include: pause.yml message="Please reset BMC interfaces to
obtain DHCP leases. Press <enter> to continue"*

* 7 - include: container/set\_data\_switch\_config.yml log\_level=info*

* 8 - include: container/inv\_add\_switches.yml log\_level=info*

* 9 - include: container/inv\_add\_ipmi\_ports.yml log\_level=info*

* 10 - include: container/ipmi\_set\_bootdev.yml log\_level=info
       bootdev=network persistent=False*

* 11 - include: container/ipmi\_power\_on.yml log\_level=info*

* 12 - include: pause.yml minutes=5 message="Power-on Nodes"*

* 13 - include: container/inv\_add\_ipmi\_data.yml log\_level=info*

* 14 - include: container/inv\_add\_pxe\_ports.yml log\_level=info*

* 15 - include: container/ipmi\_power\_off.yml log\_level=info*

* 16 - include: container/inv\_modify\_ipv4.yml log\_level=info*

* 17 - include: container/cobbler/cobbler\_add\_distros.yml*

* 18 - include: container/cobbler/cobbler\_add\_profiles.yml*

* 19 - include: container/cobbler/cobbler\_add\_systems.yml*

* 20 - include: container/inv\_add\_config\_file.yml*

* 21 - include: container/allocate\_ip\_addresses.yml*

* 22 - include: container/get\_inv\_file.yml dest=/var/oprc*

* 23 - include: container/ipmi\_set\_bootdev.yml log\_level=info
       bootdev=network persistent=False*

* 24 - include: container/ipmi\_power\_on.yml log\_level=info*

* 25 - include: pause.yml minutes=5 message="Power-on Nodes"*

* 26 - include: container/ipmi\_set\_bootdev.yml log\_level=info
       bootdev=default persistent=True*

Recovering from Wrong IPMI userid and /or password
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**If the userid or password for the ipmi ports are wrong, genesis will
fail. To fix this, first correct the userid and or password in the
config.yml file (~/cluster-genesis/config.yml in both the host OS and
the container). Also correct the userid and or password in the container
at ~/cluster-genesis/inventory.yml. Then modify the
~/cluster-genesis/playbooks/install.yml file, commenting out the
playbooks shown below. Then rerstart genesis from step 15(rerun the
install playbook)**

**---**

**# Copyright 2018 IBM Corp.**

**#**

**# All Rights Reserved.**

**#**

**# Licensed under the Apache License, Version 2.0 (the "License");**

**# you may not use this file except in compliance with the License.**

**# You may obtain a copy of the License at**

**#**

**# http://www.apache.org/licenses/LICENSE-2.0**

**#**

**# Unless required by applicable law or agreed to in writing,
software**

**# distributed under the License is distributed on an "AS IS" BASIS,**

**# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
implied.**

**# See the License for the specific language governing permissions
and**

**# limitations under the License.**

****

**#- include: lxc-update.yml**

**#- include: container/cobbler/cobbler\_install.yml**

**- include: pause.yml message="Please reset BMC interfaces to obtain
DHCP leases"**

**#- include: container/set\_data\_switch\_config.yml**

**#- include: container/inv\_add\_switches.yml**

**#- include: container/inv\_add\_ipmi\_ports.yml**

**- include: container/ipmi\_set\_bootdev.yml bootdev=network
persistent=False**

**- include: container/ipmi\_power\_on.yml**

**- include: pause.yml minutes=20 message="Power-on Nodes"**

**- include: container/inv\_add\_ipmi\_data.yml**

**- include: container/inv\_add\_pxe\_ports.yml**

**- include: container/ipmi\_power\_off.yml**

**- include: container/inv\_modify\_ipv4.yml**

**- include: container/cobbler/cobbler\_add\_distros.yml**

**- include: container/cobbler/cobbler\_add\_profiles.yml**

**- include: container/cobbler/cobbler\_add\_systems.yml**

**- include: container/inv\_add\_config\_file.yml**

**- include: container/allocate\_ip\_addresses.yml**

**- include: container/get\_inv\_file.yml dest=/var/oprc**

**- include: container/ipmi\_set\_bootdev.yml bootdev=network
persistent=False**

**- include: container/ipmi\_power\_on.yml**

**- include: pause.yml minutes=5 message="Power-on Nodes"**

**- include: container/ipmi\_set\_bootdev.yml bootdev=default
persistent=True**

**Recreating the Genesis Container**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**To destroy the Genesis container and restart Genesis from that
point**::

    $ tear-down

**Respond yes to prompts to destroy the container and remove it's associated bridges.
Restart genesis from step 9 of the step by step instructions.**


OpenPOWER Node issues
~~~~~~~~~~~~~~~~~~~~~

Specifying the target drive for operating system install;

In the config.yml file, the *os-disk* key is the disk to which the
operating system will be installed. Specifying this disk is not always
obvious because Linux naming is inconsistent between boot and final OS
install. For OpenPOWER S812LC, the two drives in the rear of the unit
are typically used for OS install. These drives should normally be
specified as /dev/sdj and /dev/sdk

PXE boot: OpenPOWER nodes need to have the Ethernet port used for PXE
booting enabled for DHCP in petitboot.

Be sure to specify a disk configured for boot as the bootOS drive in the
config.yml file.

When using IPMI, be sure to specify the right user id and password. IPMI
will generate an "unable to initiate IPMI session errors" if the
password is not correct.

| ipmitool -I lanplus -H 192.168.x.y -U ADMIN -P ADMIN chassis power off
| ipmitool -I lanplus -H 192.168.x.y -U ADMIN -P ADMIN chassis bootdev
  pxe
| ipmitool -I lanplus -H 192.168.x.y -U ADMIN -P ADMIN chassis power on

ipmitool -I lanplus -H 192.168.x.y -U ADMIN -P ADMIN chassis power
status

To monitor the boot window using the serial over lan capability;

ipmitool -H 192.168.0.107 -I lanplus -U ADMIN -P admin sol activate

Be sure to use the correct password.

You can press Ctrl-D during petit boot to bring up a terminal.

To exit the sol window, enter "~." enter (no quotes)
