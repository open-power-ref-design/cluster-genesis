.. highlight:: none

Introduction
============

The PowerUp suite of deployment software enables greatly simplified deployment
and configuration of OpenPOWER servers running Linux and installation of software
to groups of servers. It leverages widely used open
source tools such as Cobbler, Ansible and Python. Because it relies
solely on industry standard protocols such as IPMI and PXE boot, hybrid
clusters of OpenPOWER and x86 nodes can readily be supported.

PowerUp currently has three primary functional capabilities;

    - Operating system installation (in beta)
    - Software installation
    - Bare metal deploy of openPOWER clusters
    - Basic configuration of groups of nodes (under development)

Operating System Installation Overview
--------------------------------------

PowerUp uses a windowed text based user interface (TUI) to provide a user
friendly, easy to use facility for quickly deploying an OS to a group of similar
nodes from a user provided ISO image file. Both Red Hat and Ubuntu are supported.
After entering the subnet information for the BMC and PXE networks and selecting
the installation ISO file, the PowerUp software scans the subnet for BMCs and
displays a list of discovered nodes.  Nodes are listed with serial number, model
and BMC MAC address. The user can select nodes from the list by simply scrolling
through the list, pressing the space bar to select the desired nodes and click on
'OK' to begin installation. A status screen shows installation status.

Software Installation Overview
------------------------------
PowerUp's software installer provides a framework for 'pluggable' software
install modules which can be user created. Python classes are provided to
facilitate the creation of yum, conda and pypi simple repositories. The nginx
web server is used to serve software binaries and packages to the nodes being
installed.

Node Configuration
------------------
Basic configuration of groups of similar nodes is under development. A simple
to use TUI will allow setting of hostnames, setup of network interfaces, basic firewall
configuration and basic setup of network attached shared storage. Ansible is used
to handle configuration tasks across a cluster.

Cluster Deploymment Overview
----------------------------
PowerUp's bare metal cluster deployment deploys a heterogeneous cluster of
compute nodes and Ethernet switches across one or more racks. PowerUp can
configure simple flat networks for typical HPC
environments or more advanced networks with VLANS and bridges for
OpenStack environments. Complex heterogeneous clusters can be easily deployed
using PowerUp's interface and node templates. PowerUp configures
the switches in the cluster with support for multiple switch vendors.

Cluster PowerUp is designed to be easy to use. If you are implementing
one of the supported architectures with supported hardware, it eliminates
the need for custom scripts or programming. It does this via a text
configuration file (config.yml) which drives the cluster configuration.
The configuration file is a YAML text file which the user edits. Several
example config files are included docs directory. The configuration
process is driven from a "deployer" node which can be removed from the
cluster when finished. The PowerUp process is as follows;

#. Rack and cable the hardware.
#. Initialize hardware.

   - initialize switches with static IP address, userid and password.
   - insure that all cluster compute nodes are set to obtain a DHCP
     address on their BMC ports and they are configured to support
     PXE boot on one of their network adapters.

#. Install the Cluster PowerUp software on the deployer node.
#. Edit an existing config.yml file to drive the configuration.
#. Run the PowerUp software

When finished, Cluster PowerUp generates a YAML formatted inventory file
with detailed information about your cluster nodes. This file can
be read by operational management software and used to seed
configuration files needed for installing a solution software stack.

Hardware and Architecture Overview
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The PowerUp software supports clusters of servers
interconnected with Ethernet. The
servers must support IPMI and PXE boot. Multiple racks can
be configured with traditional two tier access-aggregation
networking. PowerUp configures both a management and
data network. In simple / cost sensitive setups, the management
and data networks can be configured on the same physical switch.
Power-Up can configure VLANs and bonded networks with as many ports
as the hardware supports. Redundant data switches (ie MLAG) are also
supported. (Currently only implemented on Mellanox switches.)

Networking
~~~~~~~~~~

Cluster PowerUp provides basic layer 2 configuration of Cisco, Mellanox
and Lenovo switches. Not all functionality is enabled on all switch types.
Currently redundant networking (MLAG) is only implemented on Mellanox
switches. Port channel support is only implemented on Cisco (NX-OS) and
Mellanox switches. PowerUp can configure any number of node interfaces
on cluster nodes. To facilitate installation of higher level software,
network interfaces can be optionally renamed.

Interface templates are used to define network configurations
in the config.yml file. These can be physical ports, bonded ports,
Linux bridges or VLANS. Interface templates can be entered using
Ubuntu or Red Hat network configuration syntax. Once defined, interface
templates can be applied to any node template. Node interfaces can
optionally be configured with static IP addresses. These can be assigned
sequentially or from a list.

Compute Nodes
~~~~~~~~~~~~~

Cluster PowerUp supports clusters of heterogeneous compute nodes. Users
can define any number of node types by creating templates in a config file.
Node templates can include any network templates defined in the network
templates section. The combination of node templates and network templates
allows great flexibility in building heterogeneous clusters with nodes
dedicated to specific purposes.

.. _supported-hardware:

Supported Hardware
~~~~~~~~~~~~~~~~~~~

**Compute Nodes**

OpenPOWER Compute Nodes;

-  S812LC
-  S821LC
-  S822LC (Minsky)
-  SuperMicro OpenPOWER servers

x86 Compute Nodes;

-  Lenovo x3550
-  Lenovo x3650

Many other x86 nodes should work, but we have only tested with Lenovo and some Supermicro nodes.

**Switches**

For information on adding additional switch support using
PowerUp's switch class API, (see :ref:`developerguide`)

Supported Switches;

-  Mellanox SX1410
-  Mellanox SX1710
-  Cisco 5K (FEXes supported)
-  Lenovo G8052, G7028, G7052 (bonding not currently supported)

**Note**
Other Mellanox switches may work but have not been tested
Lenovo G8264 has not been tested
Other Cisco NX-OS based switches may work but have not been tested

