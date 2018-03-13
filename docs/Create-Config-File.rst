.. _creating_the_config_file:

Creating the config.yml File
============================

The config.yml file drives the creation of the cluster. It uses YAML
syntax which is stored as readable text. As config.yml is a Linux file,
lines must terminate with a line feed character (/n). If using a windows
editor to create or edit the file, be sure to use an editor such as Open
Office which supports saving text files with new line characters or use
dos2unix to convert the windows text file to linux format.

YAML files support data structures such as lists, dictionaries and
scalars. A complete definition of the config.yml file along with
detailed documentation of the elements used are given in appendix B.

The config.yml file has 5 main sections. These are;

#. General Settings
#. Cluster definition
#. Network templates
#. Node templates
#. Post Genesis activities

Notes:

-  Usually it is easier to start with an existing config.yml file rather
   than create one from scratch.
-  YAML files use spaces as part of syntax. This means for example that
   elements of the same list must have the exact same number of spaces
   preceeding them. When editing a .yml file pay careful attention to
   spaces at the start of lines. Incorrect spacing can result in failure
   to load messages during genesis.

General Settings
----------------

The top part of the config.yml file contains a group of key value pairs that
define general settings.

.. _config-file-version:

**Config file version**::

    version: 1.1

+----------------+-------------------------------+
| Release Branch | Supported Config File Version |
+================+===============================+
| release-0.9    | version: 1.0                  |
+----------------+-------------------------------+
| release-1.x    | version: 1.1                  |
+----------------+-------------------------------+
| release-2.x    | version: 2.0 (planned)        |
+----------------+-------------------------------+


.. _config-file-log-level:

**Default log level**::

    log_level: debug


.. _config-file-introspection:

**Introspection**:

Introspection consists of loading a lightweight in-memory OS (linux buildroot)
on all client nodes prior to OS installation on disk. This feature can be
enabled via the 'introspection-enabled' key in 'config.yml' to a boolean
value. If omitted or set to 'false' the introspection components will not be
run. Initially it is only supported on clusters with all ppc64el deployer and
client nodes.::

    introspection-enabled: true   # Introspection Mode Enabled
    introspection-enabled: false  # Introspection Mode Disabled


.. _config-file-write-switch:

**Write switch configuration to flash memory**

The manangement and data switches can automatically write the configuration
to flash memory using the 'write-switch-memory' key.::

    write-switch-memory: true   # Write Switch Memory Enabled
    write-switch-memory: false  # Write Switch Memory Disabled


.. _config-file-deployment-env:

**Deployment Environment**

The 'deployment-environment' key in 'config.yml' can be used to define
environment variables (as key: values) to be set during deployment::

    deployment-environment:
        https_proxy: "http://192.168.1.2:3128"
        http_proxy: "http://192.168.1.2:3128"
        no_proxy: "localhost,127.0.0.1"

This was implemented to enable http/https proxy configuration but could be used
for anything that utilized environment variables. The 'deployment-environment'
dictionary is copied into 'playbooks/group_vars/all' as
'deployment_environment' (note the "-" is changed to "_").



Cluster definition
-------------------

The next section of the config.yml file contains a group of key value pairs
that define the overall cluster layout. Each rack in a cluster is
assumed to have a management switch and one or two data switches.
Note that keywords with a leading underscore can be changed by the end
user as appropriate for your application. (e.g. "_rack1" could be changed to
"base-rack")


The following keys must be included in the cluster definition section::

    ipaddr-mgmt-network: a.b.c.d/n
    ipaddr-mgmt-client-network: a.b.e.f/n
    container-mgmt-ipaddr-offset: 4
    container-bridge-ipaddr-offset: 5
    vlan-mgmt-network: 16
    vlan-mgmt-client-network: 20
    port-mgmt-network: 1
    ipaddr-mgmt-switch:
        rackname: a.b.c.d
    ipaddr-data-switch:
        rackname: a.b.c.d
    redundant-network: false #  "true" for redundant network (future release)
    userid-default: joeuser
    password-default: passw0rd
    userid-mgmt-switch: admin
    password-mgmt-switch: admin
    userid-data-switch: admin
    password-data-switch: admin

Notes:

-  OpenPOWER Cluster Genesis creates two VLANs on the management switch(es) in your cluster.
   These are used to isolate access of the management interfaces on the cluster switches from the
   BMC and PXE ports of the cluster nodes.  The VLAN in which the switch management interfaces reside
   is defined by the vlan-mgmt-network: keyword.  The VLAN in which the cluster BMC and PXE ports
   reside in is defined by the vlan-mgmt-client-network: keyword.
-  The ipaddr-mgmt-network: keyword defines the subnet that the PXE and BMC ports for
   your cluster nodes will reside in. addresses a.b.c.1 and a.b.c.2 are reserved for
   use by the linux container on the deployer node. Cluster node address assignments
   will begin at a.b.c.101.
-  The ipaddr-mgmt-client-network: keyword defines the subnet that the BMC and PXE ports
   of the cluster nodes reside in.
-  The management ip addresses for the management switch and the data
   switch must not reside in the same subnet as the nodes management
   network.
-  It is permitted to include addititonal application specific key value
   pairs at the end of the cluster definition section. Additional keys
   will be copied to the inventory.yml file which can be read by
   software stack installation scripts.
-  a.b.c.d is used above to represent any ipv4 address. The user must
   supply a valid ipv4 address. a.b.c.d/n is used to represent any valid
   ipv4 address in CIDR format.
-  The default container and corresponding bridge ipv4 address offsets are set
   to 2 and 3, respectively. On any additional deployers nodes these settings
   must be changed to unique values. This can be accomplished using the
   container-mgmt-ipaddr-offset and container-bridge-ipaddr-offset keywords.

**Passive Switch Mode**:

Cluster Genesis can deal with management and/or data switches in "passive" mode
to allow deployments without requiring access to the switch management
interfaces. This mode requires the user to manually configure the switches and
to write switch MAC address tables to files.

Passive management switch mode and passive data switch mode can be configured
independent of each other, but passive and active switches of the same
classification cannot be mixed (i.e. all data switches must either be
active or passive).

**Passive Management Switch Mode**:

Passive management switch mode requires the user to configure the management
switch *before* starting a Cluster Genesis deploy. The client network must be
isolated from any outside servers. Cluster Genesis will attempt to issue IPMI
commands to any system BMC that is set to DHCP and has access to the client
network.

To configure passive switches simply omit 'userid-mgmt-switch' from
'config.yml'. The 'ipaddr-mgmt-switch' dictionary still needs to be defined
in order to be used as a switch identifier. In place of IP addresses anything
may be used as long as each switch has a unique value. These unique values will
be used by Cluster Genesis to identify the files containing MAC address information.

Passive management switch example configuration::

    ipaddr-mgmt-switch:
        base-rack: passive_mgmt_1
        rack2: passive_mgmt_2
        rack3: passive_mgmt_3
    ipaddr-data-switch:
        base-rack: passive_data_1
        rack2: passive_data_2
        rack3: passive_data_3


**Passive Data Switch Mode**:

Passive data switch mode requires the user to configure the data switch in
accordance with the defined networks. The node interfaces of the cluster will
still be configured by Cluster Genesis.

To configure passive switches simply omit 'userid-data-switch' from
'config.yml'. The 'ipaddr-data-switch' dictionary still needs to be defined
in order to be used as a switch identifier. In place of IP addresses anything
may be used as long as each switch has a unique value. These unique values will
be used by Cluster Genesis to identify the files containing MAC address information.

Passive data switch example configuration::

    ipaddr-mgmt-switch:
        base-rack: 192.168.16.5
        rack2: 192.168.16.6
        rack3: 192.168.16.7
    ipaddr-data-switch:
        base-rack: passive1
        rack2: passive2
        rack3: passive3


Network Templates
-----------------

The network template section of the config.yml file defines the cluster
networks. The OpenPower cluster configuration software can configure
multiple network interfaces, bridges and vlans on the cluster nodes.
vlans setup on cluster nodes will be configured on the data switches
also. Network templates are called out in compute templates to create
the desired networks on your cluster.

The network template section of the config file begins with the
following key::

  networks:

This key is then followed by the name of an individual interface or
bridge definitions. Users are free to use any name for a network
template. Bridge definitions may optionally include vlans, in which case
a virtual vlan port will be added to the specified interface and
attached to the bridge. There may be as many network definitions as
desired.

Simple static ip address assignement
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following definition shows how to specify a simple static ip address
assignement to ethernet port 2::

 external1: your-ifc-name
    description: Organization site or external network
    addr: a.b.c.d/n
    broadcast: a.b.c.e
    gateway: a.b.c.f
    dns-nameservers: e.f.g.h
    dns-search: your.search.domain
    method: static
    eth-port: eth2

**Note**: Addresses to be assigned to cluster nodes can be entered in
the config file as individual addresses or multiple ranges of addresses.

Bridge creation
~~~~~~~~~~~~~~~

The following definition shows how to create a bridge with a VLAN
attached to the physical port eth2 defined above::

 mybridge:
    description: my-bridge-name
    bridge: br-mybridge
    method: static
    tcp_segmentation_offload: off
    addr: a.b.c.d/n
    vlan: n
    eth-port: eth2

The above definition will cause the creation of a bridge called
br-mybridge with a connection to a virtual vlan port eth2.n which is
connected to physical port eth2.

Node Templates
--------------

Renaming Interfaces
~~~~~~~~~~~~~~~~~~~

The *name-interfaces:* key provides the ability to rename ethernet
interfaces. This allows the use of heterogeneous nodes with software
stacks that need consistent interface names across all nodes. It is not
necessary to know the existing interface name. The cluster configuration
code will find the MAC address of the interface cabled to the specified
switch port and change it as specified. In the example below, the first
node has a pxe port cabled to management switch port 1. The genesis code
reads the MAC address attached to that port from the management switch
and then changes the name of the physical port belonging to that MAC
address to the name specified. (in this case "eth15"). Note also that
the key pairs under name-interfaces: must correlate to the interfaces
names listed under "ports:" ie "mac-pxe" correlates to "pxe" etc.

In the example compute node template below, the node ethernet ports
connected to management switch ports 1 and 3 (the pxe ports) will be
renamed to eth15, the node ethernet ports connected to management switch
ports 5 and 7 (the eth10 ports) will be renamed to eth10::

 compute:
     hostname: compute
     userid-ipmi: ADMIN
     password-ipmi: ADMIN
     cobbler-profile: ubuntu-14.04.4-server-amd64.sm
     os-disk: /dev/sda
     name-interfaces:
         mac-pxe: eth15
         mac-eth10: eth10
     ports:
         pxe:
             rack1:
                 - 1
                 - 3
         ipmi:
             rack1:
                 - 2
                 - 4
         eth10:
             rack1:
                 - 5
                 - 7

Node Template Definition
~~~~~~~~~~~~~~~~~~~~~~~~

The node templates section of the config file starts with the following
key::

 node-templates:

Template definitions begin with a user chosen name followed by the key
values which define the node::

 compute:
     hostname: compute
     userid-ipmi: ADMIN
     password-ipmi: ADMIN
     cobbler-profile: ubuntu-14.04.4-server-amd64.sm
     os-disk: /dev/sda
     name-interfaces:
         mac-pxe: eth15
         mac-eth10: eth10
         mac-eth11: eth11
     ports:
         pxe:
             rack1:
                 - 1
                 - 3
         ipmi:
             rack1:
                 - 2
                 - 4
         eth10:
             rack1:
                 - 5
                 - 7
         eth11:
             rack1:
                 - 6
                 - 8
     networks:
         - external1
         - mybridge

Notes:

-  The order of ports under the "ports:" dictionary are important and
   must be in order for each node. In the above example, the first
   node's pxe, ipmi, eth10 and eth11 ports are connected to the data
   switch ports 1, 2, 5 and 6.
-  The *os-disk* key is the disk to which the operating system will be
   installed. Specifying this disk is not always obvious because Linux
   naming is insconsistent between boot and final OS install. For
   OpenPOWER S812LC, the two drives in the rear of the unit are
   typically used for OS install. These drives should normally be
   specified as /dev/sdj and /dev/sdk

Post Genesis Activities
-----------------------

The section of the config.yml file allows you to execute additional commands on your
cluster nodes after Genesis completes.  These can perform various additional configuration
activities or bootstrap additional software package installation.  Commands can be specified
to run on all cluster nodes or only specific nodes specified by the compute template name.

The following config.yml file entries run the "apt-get update" command on all cluster
nodes and then runs the "apt-get upgrade -y" command on the first compute node and runs
"apt-get install vlan" on all controller nodes::

    software-bootstrap:
        all: apt-get update
        compute[0]: |
            apt-get update
            apt-get upgrade -y
        controllers:
            apt-get install vlan

OpenPOWER reference design recipes
==================================

Many OpenPOWER reference design recipes are available on github.  These recipes
include bill of materials, system diagrams and config.yml files;

- openstack-recipes
- acclerated-db

`OpenPOWER reference designs <https://github.com/open-power-ref-design>`_
