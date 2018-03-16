
Appendix - C The System Inventory File (needs update)
=====================================================

The inventory.yml file is created by the system genesis process. It can
be used by higher level software stacks installation tools to configure
their deployment. It is also used to seed the system inventory
information into the operations management environment.

inventory.yml File format:
--------------------------

---

userid-default: joedefault # default userid if no other userid is
specified

password-default: joedefaultpassword

redundant-network: 0 # indicates whether the data network is redundant
or not

ipaddr-mgmt-network: 192.168.16.0/20 #ipv4 address /20 provides 4096
addresses

ipaddr-mgmt-switch:

 -rack1: 192.168.16.2 #ipv4 address of the management switch in the
  first rack or cell.

 -rack2: 192.168.16.3

 -rack3: 192.168.16.4

 -rack4: 192.168.16.5

 -rack5: 192.168.16.6

 -aggregation: 192.168.16.18

userid-mgmt-switch: joemgmt # if not specified, the userid-default will
be used

password-mgmt-switch: joemgmtpassword # if not specified, the
password-default will be used.

ipaddr-data-switch:

 -rack1: 192.168.16.20 # if redundant-network is set to 1, genesis will
  look for an additional switch at the next sequential address.

 -rack2: 192.168.16.25

 -rack3: 192.168.16.30

 -rack4: 192.168.16.35

 -rack5: 192.168.16.40

 -spine: 192.168.16.45

userid-data-switch: joedata # if not specified, the userid-default will
be used

password-data-switch: joedatapassword # if not specified, the
password-default will be used.

userid-ipmi-new: userid

password-ipmi-new: password

# Base Network information

openstack-mgmt-network:

 addr: 172.29.236.0/22 #ipv4 openstack management network

 vlan: 10

 eth-port: eth10

openstack-stg-network:

 addr: 172.29.244.0/22 #ipv4 openstack storage network

 vlan: 20

 eth-port: eth10

openstack-tenant-network:

 addr: 172.29.240.0/22 #ipv4 openstack tenant network

 vlan: 30 # vxlan vlan id

 eth-port: eth11

ceph-replication-network:

 addr: 172.29.248.0/22 # ipv4 ceph replication network

 vlan: 40

 eth-port: eth11

swift-replication-network:

 addr: 172.29.252.0/22 # ipv4 ceph replication network

 vlan: 50

 eth-port: eth11

########## OpenStack Controller Node Section ################

userid-ipmi-ctrlr: userid

password-ipmi-ctrlr: password

hostname-ctrlr:

name-10G-ports-ctrlr:

 -ifc1: [ifcname1, ifcname2] # 2\ :sup:`nd` ifcname is optional.
  Multiple ports are bonded.

 -ifc2: [ifcname1, ifcname2]

list-ctrlr-ipmi-ports:

 -rack1: [port1, port2, port3]

 -rack2: [port1]

########## Compute Node Section #############################

userid-ipmi-compute: userid

password-ipmi-compute: password

hostname-compute:

name-10G-ports-compute:

 -ifc1: [ifcname1, ifcname2] # 2\ :sup:`nd` ifcname is optional.
  Multiple ports are bonded.

 -ifc2: [ifcname1, ifcname2]

list-compute-ipmi-ports:

 -rack1: [port1, port2, port3, port4]

 -rack2: [port1, port2, port3, port4, port5]

 -rack3: [port1, port2, port3, port4, port5]

 -rack4: [port1, port2, port3, port4, port5]

 -rack5: [port1, port2, port3, port4, port5]

########## Ceph OSD Node Section ###########################

userid-ipmi-ceph-osd: userid

password-ipmi-ceph-osd: password

hostname-ceph-osd:

name-10G-ports-ceph-osd:

 -ifc1: [ifcname1, ifcname2] # 2\ :sup:`nd` ifcname is optional.
  Multiple ports are bonded.

 -ifc2: [ifcname1, ifcname2]

list-ceph-osd-ipmi-ports:

 -rack1: [port1, port2, port3]

 -rack2: [port1, port2, port3]

 -rack3: [port1]

 -rack4: [port1]

 -rack5: [port1]

########## Swift Storage Node Section ######################

userid-ipmi-swift-stg: userid

password-ipmi-swift-stg: password

hostname-swift-stg:

name-10G-ports-swift-stg:

 -ifc1: [ifcname1, ifcname2] # 2\ :sup:`nd` ifcname is optional.
  Multiple ports are bonded.

 -ifc2: [ifcname1, ifcname2]

list-swift-stg-ipmi-ports:

 -rack1: [port2, port3, port4]

 -rack2: [port2, port3, port4]

 -rack3: [port1, port2]

 -rack4: [port1]

 -rack5: [port1]

...

---

hardware-mgmt-network: 192.168.0.0/20 # 4096 addresses

ip-base-addr-mgmt-switches: 2 # 20 contiguous ip addresses will be
reserved

ip-base-addr-data-switches: 21 # 160 contiguous ip addresses will be
reserved

redundant-network: 1

dns:

 - dns1-ipv4: address1

 - dns2-ipv4: address2

userid-default: user

password-default: passw0rd

userid-mgmt-switch: user # applied to all mgmt switches

password-mgmt-switch: passw0rd # applied to all mgmt switches

userid-data-switch: user

password-data-switch: passw0rd

ssh-public-key: # key used for access to all node types

ssh-passphrase: passphrase

openstack-mgmt-network:

 addr: 172.29.236.0/22 #ipv4 openstack management network

 vlan: 10

 eth-port: eth10

openstack-stg-network:

 addr: 172.29.244.0/22 #ipv4 openstack storage network

 vlan: 20

 eth-port: eth10

openstack-tenant-network:

 addr: 172.29.240.0/22 #ipv4 openstack tenant network

 vlan: 30 # vxlan vlan id

 eth-port: eth11

ceph-replication-network:

 addr: 172.29.248.0/22 # ipv4 ceph replication network

 vlan: 40

 eth-port: eth11

swift-replication-network:

 addr: 172.29.252.0/22 # ipv4 ceph replication network

 vlan: 50

 eth-port: eth11

racks:

 - rack-id: rack number or name

 data-center: data center name

 room: room id or name

 row: row id or name

 - rack-id: rack number or name

 data-center: data center name

 room: room id or name

 row: row id or name

switches:

 mgmt:

 - hostname: Device hostname

 ipv4-addr: ipv4 address of the management port

 userid: Linux user id for this controller

 password: Linux password for this controller

 rack-id: rack name or number

 rack-eia: rack eia location

 model: model # for this switch

 serial-number: Serial number for this switch

 - hostname: Device hostname

 ipv4-addr: ipv4 address of the management port

 userid: Linux user id for this controller

 password: Linux password for this controller

 rack-id: rack name or number

 rack-eia: rack eia location

 model: model # for this switch

 serial-number: Serial number for this switch

 leaf:

 - hostname: Device hostname

 ipv4-addr: ipv4 address of the management port

 userid: Linux user id for this controller

 password: Linux password for this controller

 rack-id: rack name or number

 rack-eia: rack eia location

 model: model # for this switch

 serial-number: Serial number for this switch

 - hostname: Device hostname

 ipv4-addr: ipv4 address of the management port

 userid: Linux user id for this controller

 password: Linux password for this controller

 rack-id: rack name or number

 rack-eia: rack eia location

 model: model # for this switch

 serial-number: Serial number for this switch

 spine:

 - hostname: Device hostname

 ipv4-addr: ipv4 address of the management port

 userid: Linux user id for this controller

 password: Linux password for this controller

 rack-id: rack name or number

 rack-eia: rack eia location

 model: model # for this switch

 serial-number: Serial number for this switch

 - hostname: Device hostname

 ipv4-addr: ipv4 address of the management port

 userid: Linux user id for this controller

 password: Linux password for this controller

 rack-id: rack name or number

 rack-eia: rack eia location

 model: model # for this switch

 serial-number: Serial number for this switch

nodes:

 controllers: # OpenStack controller nodes

 - hostname: hostname #(associated with ipv4-addr below)

 ipv4-addr: ipv4 address of this host # on the eth10 interface

 userid: Linux user id for this controller

 cobbler-profile: name of cobbler profile

 rack-id: rack name or number

 rack-eia: rack eia location

 chassis-part-number: part number # ipmi field value

 chassis-serial-number: Serial number # ipmi field value

 model: system model number # ipmi field value

 serial-number: system serial number # ipmi field value

 ipv4-ipmi: ipv4 address of the ipmi port

 mac-ipmi: mac address of the ipmi port

 userid-ipmi: userid for logging into the ipmi port

 password-ipmi: password for logging into the ipmi port

 userid-pxe: userid for logging into the pxe port

 password-pxe: password for logging into the pxe port

 ipv4-pxe: ipv4 address of the ipmi port

 mac-pxe: mac address of the ipmi port

 openstack-mgmt-addr: 172.29.236.2/22

 openstack-stg-addr: 172.29.244.2/22

 openstack-tenant-addr: 172.29.240.2/22

 - hostname: Linux hostname

 ipv4-addr: ipv4 address of this host # on the eth10 interface

 userid: Linux user id for this controller

 cobbler-profile: name of cobbler profile

 rack-id: rack name or number

 rack-eia: rack eia location

 chassis-part-number: part number # ipmi field value

 chassis-serial-number: Serial number # ipmi field value

 model: system model number # ipmi field value

 serial-number: system serial number # ipmi field value

 ipv4-ipmi: ipv4 address of the ipmi port

 mac-ipmi: mac address of the ipmi port

 userid-ipmi: userid for logging into the ipmi port

 password-ipmi: password for logging into the ipmi port

 userid-pxe: userid for logging into the pxe port

 password-pxe: password for logging into the pxe port

 ipv4-pxe: ipv4 address of the ipmi port

 mac-pxe: mac address of the ipmi port

 openstack-mgmt-addr: 172.29.236.3/22 #ipv4 mgmt network

 openstack-stg-addr: 172.29.244.3/22 #ipv4 storage network

 openstack-tenant-addr: 172.29.240.3/22 #ipv4 tenant network

 compute: # OpenStack compute nodes

 - hostname: Linux hostname

 ipv4-addr: ipv4 address of this host # on the eth11 port???

 userid: Linux user id for this controller

 cobbler-profile: name of cobbler profile

 rack-id: rack name or number

 rack-eia: rack eia location

 chassis-part-number: part number # ipmi field value

 chassis-serial-number: Serial number # ipmi field value

 model: system model number # ipmi field value

 serial-number: system serial number # ipmi field value

 ipv4-ipmi: ipv4 address of the ipmi port

 mac-ipmi: mac address of the ipmi port

 userid-ipmi: userid for logging into the ipmi port

 password-ipmi: password for logging into the ipmi port

 userid-pxe: userid for logging into the pxe port

 password-pxe: password for logging into the pxe port

 ipv4-pxe: ipv4 address of the ipmi port

 mac-pxe: mac address of the ipmi port

 openstack-mgmt-addr: 172.29.236.0/22 #ipv4 management network

 openstack-stg-addr: 172.29.244.0/22 #ipv4 storage network

 openstack-tenant-addr: 172.29.240.0/22 #ipv4 tenant network

 - hostname: Linux hostname

 ipv4-addr: ipv4 address of this host # on the eth11 port???

 userid: Linux user id for this controller

 cobbler-profile: name of cobbler profile

 rack-id: rack name or number

 rack-eia: rack eia location

 chassis-part-number: part number # ipmi field value

 chassis-serial-number: Serial number # ipmi field value

 model: system model number # ipmi field value

 serial-number: system serial number # ipmi field value

 ipv4-ipmi: ipv4 address of the ipmi port

 mac-ipmi: mac address of the ipmi port

 userid-ipmi: userid for logging into the ipmi port

 password-ipmi: password for logging into the ipmi port

 userid-pxe: userid for logging into the pxe port

 password-pxe: password for logging into the pxe port

 ipv4-pxe: ipv4 address of the ipmi port

 mac-pxe: mac address of the ipmi port

 openstack-mgmt-addr: 172.29.236.0/22 #ipv4 management network

 openstack-stg-addr: 172.29.244.0/22 #ipv4 storage network

 openstack-tenant-addr: 172.29.240.0/22 #ipv4 tenant network

 ceph-osd:

 - hostname: nameabc #Linux hostname

 ipv4-addr: ipv4 address of this host # on the eth10 interface

 userid: Linux user id for this controller

 cobbler-profile: name of cobbler profile

 rack-id: rack name or number

 rack-eia: rack eia location

 chassis-part-number: part number # ipmi field value

 chassis-serial-number: Serial number # ipmi field value

 model: system model number # ipmi field value

 serial-number: system serial number # ipmi field value

 ipv4-ipmi: ipv4 address of the ipmi port

 mac-ipmi: mac address of the ipmi port

 userid-ipmi: userid for logging into the ipmi port

 password-ipmi: password for logging into the ipmi port

 userid-pxe: userid for logging into the pxe port

 password-pxe: password for logging into the pxe port

 ipv4-pxe: ipv4 address of the ipmi port

 mac-pxe: mac address of the ipmi port

 openstack-stg-addr: 172.29.244.0/22 #ipv4 storage network

 ceph-replication-addr: 172.29.240.0/22 #ipv4 replication network

 journal-devices:

 - /dev/sdc

 - /dev/sdd

 osd-devices:

 - /dev/sde

 - /dev/sdf

 - /dev/sdg

 - /dev/sdh

 - hostname: nameabc

 ipv4-addr: ipv4 address of this host # on the eth11 port???

 userid: Linux user id for this controller

 cobbler-profile: name of cobbler profile

 rack-id: rack name or number

 rack-eia: rack eia location

 chassis-part-number: part number # ipmi field value

 chassis-serial-number: Serial number # ipmi field value

 model: system model number # ipmi field value

 serial-number: system serial number # ipmi field value

 ipv4-ipmi: ipv4 address of the ipmi port

 mac-ipmi: mac address of the ipmi port

 userid-ipmi: userid for logging into the ipmi port

 password-ipmi: password for logging into the ipmi port

 userid-pxe: userid for logging into the pxe port

 password-pxe: password for logging into the pxe port

 ipv4-pxe: ipv4 address of the ipmi port

 mac-pxe: mac address of the ipmi port

 openstack-stg-addr: 172.29.244.0/22 #ipv4 storage network

 ceph-replication-addr: 172.29.240.0/22 #ipv4 replication network

 journal-devices:

 - /dev/sdc

 - /dev/sdd

 osd-devices:

 - /dev/sde

 - /dev/sdf

 - /dev/sdg

 - /dev/sdh

 swift-storage:

 - hostname: Linux hostname

 ipv4-addr: ipv4 address of this host # on the eth11 port???

 userid: Linux user id for this controller

 cobbler-profile: name of cobbler profile

 rack-id: rack name or number

 rack-eia: rack eia location

 chassis-part-number: part number # ipmi field value

 chassis-serial-number: Serial number # ipmi field value

 model: system model number # ipmi field value

 serial-number: system serial number # ipmi field value

 ipv4-ipmi: ipv4 address of the ipmi port

 mac-ipmi: mac address of the ipmi port

 userid-ipmi: userid for logging into the ipmi port

 password-ipmi: password for logging into the ipmi port

 userid-pxe: userid for logging into the pxe port

 password-pxe: password for logging into the pxe port

 ipv4-pxe: ipv4 address of the ipmi port

 mac-pxe: mac address of the ipmi port

 openstack-mgmt-addr: 172.29.236.0/22 #ipv4 management network

 openstack-stg-addr: 172.29.244.0/22 #ipv4 storage network

 swift-replication-addr: 172.29.240.0/22 #ipv4 replication network

 - hostname: Linux hostname

 ipv4-addr: ipv4 address of this host # on the eth11 port???

 userid: Linux user id for this controller

 cobbler-profile: name of cobbler profile

 rack-id: rack name or number

 rack-eia: rack eia location

 chassis-part-number: part number # ipmi field value

 chassis-serial-number: Serial number # ipmi field value

 model: system model number # ipmi field value

 serial-number: system serial number # ipmi field value

 ipv4-ipmi: ipv4 address of the ipmi port

 mac-ipmi: mac address of the ipmi port

 userid-ipmi: userid for logging into the ipmi port

 password-ipmi: password for logging into the ipmi port

 userid-pxe: userid for logging into the pxe port

 password-pxe: password for logging into the pxe port

 ipv4-pxe: ipv4 address of the ipmi port

 mac-pxe: mac address of the ipmi port

 openstack-mgmt-addr: 172.29.236.0/22 #ipv4 management network

 openstack-stg-addr: 172.29.244.0/22 #ipv4 storage network

 openstack-tenant-addr: 172.29.240.0/22 #ipv4 tenant network

