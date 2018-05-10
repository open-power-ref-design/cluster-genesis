.. highlight:: none

Running the POWER-Up Cluster Deployment Software
====================================================

Installing and Running the POWER-Up code. Step by Step Instructions
-------------------------------------------------------------------

#.  Verify that all the steps in section `4 <#anchor-5>`__ `Prerequisite Hardware Setup
    <#anchor-5>`__ have been executed.  POWER-Up can not run if addresses have
    not been configured on the cluster switches and recorded in the config.yml
    file.
#.  Login to the deployer node.
#.  Install git

    - Ubuntu::

        $ sudo apt-get install git

    - RHEL::

        $ sudo yum install git

#.  From your home directory, clone POWER-Up::

      $ git clone https://github.com/open-power-ref-design-toolkit/power-up

#.  Install the remaining software packages used by Power-Up and
    setup the environment::

      $ cd power-up
      $ ./scripts/install.sh

      (this will take a few minutes to complete)

      $ source scripts/setup-env

    **NOTE:** The setup-env script will ask for permission to add
    lines to your .bashrc file.  It is recommended that you allow this
    so that the POWER-Up environment is restored if you open a new window.
    These lines can be removed using the "teardown" script.

#. If introspection is enabled then follow the instructions in
   `Building Necessary Config Files <Build-Introspection.rst#building-necessary-config-files>`_
   to set the 'IS_BUILDROOT_CONFIG' and 'IS_KERNEL_CONFIG' environment
   variables.  (Introspection NOT YET ENABLED for POWER-Up 2.0)
#. Copy your config.yml file to the ~/power-up directory (see
   section `4 <#anchor-4>`__ `Creating the config.yml
   File <#anchor-4>`__ for how to create the config.yml file)
#. Copy any needed os image files (iso format) to the
   '~/power-up/os-images' directory. Symbolic links to image
   files are also allowed.

   **NOTE:**
   Before beginning the next step, be sure all BMCs are configured to obtain a
   DHCP address then reset (reboot) all BMC interfaces of your cluster nodes.
   As the BMCs reset, the POWER-Up DHCP server will assign new addresses to them.

   One of the following options can be used to reset the BMC interfaces;

   - Cycle power to the cluster nodes. BMC ports should boot and wait to obtain
     an IP address from the deployer node.
   - Use ipmitool run as root local to each node; ipmitool bmc reset warm OR
     ipmitool mc reset warm depending on server
   - Use ipmitool remotely such as from the deployer node. (this assumes a known
     ip address already exists on the BMC interface)::

        ipmitool -I lanplus -U <username> -P <password> -H <bmc ip address> mc reset cold

   If necessary, use one of the following options to configure the BMC
   port to use DHCP;

   -  From a local console, reboot the system from the host OS, use the
      UEFI/BIOS setup menu to configure the BMC network configuration to
      DHCP, save and exit.
   -  use IPMItool to configure BMC network for DHCP and reboot the BMC

#. Copy your config.yml file to the ~/power-up directory.

#. To validate your config file::

      $ pup validate --config-file

   *Note:* Most of POWER-Up's capabilities are accessed using the 'pup' program.
    For a complete overview of the pup program, see :ref:`Appendix-A <appendix_a>`.

#. To deploy operating systems to your cluster nodes::

      $ pup deploy

   *Note*: If running with passive management switch(es) follow special
   instructions in :ref:`deploy-passive` instead. (NOTE:
   passive management switches are not yet supported in POWER-Up 2.0)


#. This will create the management networks, install the container that runs most of the POWER-Up
   functions and then optionally launch the introspection OS and then install OS's on the cluster nodes.
   This process can take as little as 40 minutes or as much as multiple hours depending on
   the size of the cluster, the capabilities of the deployer and the complexity of the deployment.

   - To monitor progress of the deployment, open an additional terminal session
     into the deployment node and run the pup program with a status request.  (Running
     POWER-Up utility functions in another terminal window will not work if you did not
     allow POWER-Up to make updates to your .bashrc file)::

      $ pup util --status (NOT yet implemented in POWER-Up 2.0)


   After a few minutes POWER-Up will have initialized and will start discovering
   and validating your cluster hardware. During discovery and validation, POWER-Up
   will first verify that it can communicate with all of the switches defined in
   the config file. Next it will create a DHCP server attached to the IPMI network
   and wait for all of the cluster nodes defined in the config file to request a
   DHCP address. After several minutes, a list of responding nodes will be
   displayed. (display order will match the config file order). If there are missing
   nodes, POWER-Up will pause so that you can take corrective actions.
   You will then be given the option to continue discovering the nodes or to
   continue on. POWER-Up will also verify that all nodes respond to IPMI commands.
   Next, POWER-Up will verify that all cluster nodes are configured to request PXE boot.
   POWER-Up will set the boot device to PXE on all discovered
   nodes, cycle power and then wait for them to request PXE boot.
   Note that POWER-Up will not initiate
   PXE boot at this time, it is only verifying that all the nodes are configured
   to request PXE boot. After several minutes all nodes requesting PXE boot
   will be listed (again in the same order that they are entered in the config file)
   POWER-Up will again pause to give you an opportunity to make any necessary
   corrections or fixes. You can
   also choose to have POWER-Up re-cycle power to nodes that have not yet
   requested PXE boot. For nodes that are missing, verify cabling and verify the
   config.yml file. See "Recovering from POWER-Up Issues" in the
   appendices for additional debug help.  You can check which nodes have obtained IP
   addresses, on their BMC's and or PXE ports by executing the following from another
   window::

      $ pup util --scan-ipmi (not yet implemented in POWER-Up 2.0)
      $ pup util --scan-pxe  (not yet implemented in POWER-Up 2.0)

   **NOTES:**
   The DHCP addresses issued by POWER-Up during discovery and validation have a
   short 5 minute lease and POWER-Up dismantles the DHCP servers after validation.
   You will lose the ability to scan these networks within a few minutes after
   validation ends. After deploy completes, you will again be able to scan these
   networks.

   Note that cluster validation can be re-run as often as needed. Note that if
   cluster validation is run after deploy, the cluster nodes will be power cycled
   which will of course interrupt any running work.

   After discovery and validation complete, POWER-Up will create a container
   for the POWER-Up deployment software to run in. Next it installs the deployment
   software and operating system images in the container and then begins the
   process of installing operating systems to the cluster nodes.
   Operating system install happens in parallel and overall install time is
   relatively independent of the number of nodes up to tens of nodes.

#. Introspection  (NOT yet enabled in POWER-Up 2.0)

   If introspection is enabled then all client systems will be booted into the
   in-memory OS with ssh enabled. One of the last tasks of this phase of POWER-Up
   will print a table of all introspection hosts, including their
   IP addresses and login / ssh private key credentials. This list is maintained
   in the 'power-up/playbooks/hosts' file under the 'introspections' group.
   POWER-Up will pause after the introspection OS deployment to allow for customized
   updates to the cluster nodes.  Use ssh (future: or Ansible) to run custom scripts
   on the client nodes.

   .. _deploy-passive-continue:

#. To continue the POWER-Up process after introspection, press enter.

   Again, you can monitor the progress of operating system installation from an
   additional terminal window::

     $ pup util --status

   It will usually take several minutes for all the nodes to load their OS.
   If any nodes do not appear in the cobbler status, see "Recovering from
   POWER-Up Issues" in the Appendices

   POWER-Up creates logs of it's activities. A file (gen) external to the
   POWER-Up container is written in the power-up/log directory.

   An additional log file is created within the deployer container.
   This log file can be viewed::

     $ pup util --log-container  (NOT yet implemented in POWER-Up 2.0)


**Configuring networks on the cluster nodes**

*Note*: If running with passive data switch(es) follow special instructions in
:ref:`post-deploy-passive <post-deploy-passive>` instead.

After completion of OS installation, POWER-Up will pause and wait for user input
before continuing. You can press enter to continue on with cluster node
and data switch configuration or stop the POWER-Up process. After stopping, you
can readily continue the node and switch configuration by entering::

   $ pup post-deploy

During post-deploy, POWER-Up performs several additional activities such
as setting up networking on the cluster nodes, setting up SSH keys and
copying them to cluster nodes, and configures the data switches.


If data switches are configured with MLAG verify that;

  * Only one IPL link is connected. (Connecting multiple IPL links before
    configuration can cause loop problems)
  * No ports used by you cluster nodes are configured in port channels.
    (If ports are configured in port channels, MAC addresses can not be
    acquired, which will prevent network configuration)


.. _deploy-passive:

Passive Switch Mode Special Instructions
----------------------------------------

**Deploying operating systems to your cluster nodes with passive management
switches**

When prompted, it is advisable to clear the mac address table on the management
switch(es).

When prompted, write each switch MAC address table to file in the
'power-up/passive' directory. The files should be named to match the unique
switch label values set in the 'config.yml' 'switches:' dictionary. For example,
for the following management switch definitions::

    switches:
        mgmt:
            - label: passive_mgmt_1
              userid: admin
              password: abc123
              interfaces:
                :
                :
                :
        mgmt:
            - label: passive_mgmt_2
              userid: admin
              password: abc123
              interfaces:


The user would need to write two files:
	1. 'power-up/passive/passive_mgmt_1'
	2. 'power-up/passive/passive_mgmt_2'

If the user has ssh access to the switch management interface, writing the MAC
address table to file can be readily accomplished by redirecting stdout. Here is
an example of the syntax for a Lenovo G8052::

    $ ssh <mgmt_switch_user>@<mgmt_switch_ip> \
    'show mac-address-table' > ~/power-up/passive/passive_mgmt_1

Note that this command would need to be run for each individual mgmt switch,
writing to a separate file for each. It is recommended to verify each file has
a complete table for the appropriate interface configuration and only one mac
address entry per interface.

See :ref:`MAC address table file formatting rules <mac-table-file-rules>` below.

After writing MAC address tables to file press enter to continue with OS
installation. :ref:`Resume normal instructions <deploy-passive-continue>`.

If deploy-passive fails due to incomplete MAC address table(s) use the
following command to reset all servers (power off / set bootdev pxe / power on)
and attempt to collect MAC address table(s) again when prompted::

    $ pup util --cycle-power-pxe (NOT yet implemented)

.. _post-deploy-passive:

**Configuring networks on the cluster nodes with passive data switches**

When prompted, it is advisable to clear the mac address table on the data
switch(es). This step can be skipped if the operating systems have just been
installed on the cluster nodes and the mac address timeout on the switches is
short enough to insure that no mac addresses remain for the data switch ports
connected to cluster nodes. If in doubt, check the acquired mac address file
(see below) to insure that each data port for your cluster has only a single
mac address entry.::

    $ pup post-deploy

When prompted, write each switch MAC address table to file in
'power-up/passive'. The files should be named to match the unique label
values set in the 'config.yml' 'switches:' dictionary. For example,
take the following data switch definitions::

    switches:
          :
          :
        data:
            - label: passive1
              class: cisco
              userid: admin
              password: passw0rd
          :
          :
            - label: passive2
              class: cisco
              userid: admin
              password: passw0rd
          :
          :
            - label: passive3
              class: cisco
              userid: admin
              password: passw0rd

The user would need to write three files:
	1. '~/power-up/passive/passive1'
	2. '~/power-up/passive/passive2'
	3. '~/power-up/passive/passive3'

If the user has ssh access to the switch management interface writing the MAC
address table to file can easily be accomplished by redirecting stdout. Here is
an example of the syntax for a Mellanox SX1400 / SX1710::

    $ ssh <data_switch_user>@<data_switch_ip> \
    'cli en "conf t" "show mac-address-table"' > ~/power-up/passive/passive1

For a Cisco NX-OS based switch::

    $ ssh <data_switch_user>@<data_switch_ip> \
    'conf t ; show mac address-table' > ~/power-up/passive/passive1


Note that this command would need to be run for each individual data switch,
writing to a separate file for each. It is recommended to verify each file has
a complete table for the appropriate interface configuration and only one mac
address entry per interface.

See :ref:`MAC address table file formatting rules <mac-table-file-rules>` below.

.. _mac-table-file-rules:

**MAC Address Table Formatting Rules**

Each file must be formatted according to the following rules:

    * MAC addresses and ports are listed in a tabular format.
        - Columns can be in any order
        - Additional columns (e.g. vlan) are OK as long as a header is
          provided.
    * If a header is provided and it includes the strings "mac address" and
      "port" (case insensitive) it will be used to identify column positions.
      Column headers must be delimited by at least two spaces. Single spaces
      will be considered a continuation of a single column header (e.g. "mac
      address" is one column, but "mac address  vlan" would be two).
    * If a header is provided, it must include a separator row consisting of
      dashes '-' to delineate columns. One or more spaces or plus symbols '+'
      are to be used to separate columns.
    * If a header is not provided then only MAC address and Port columns are
      allowed.
    * MAC addresses are written as (case-insensitive):
      	- Six pairs of hex digits delimited by colons (:) [e.g. 01:23:45:67:89:ab]
      	- Six pairs of hex digits delimited by hyphens (-) [e.g. 01-23-45-67-89-ab]
      	- Three quads of hex digits delimited by periods (.) [e.g. 0123.4567.89ab]
    * Ports are written either as:
        - An integer
        - A string starting with 'Eth1/' followed by one or more numeric digits
          without white space. (e.g. "Eth1/25" will be saved as "25")
        - A string starting with 'Eth' and containing multiple numbers separated
          by "/". The 'Eth' portion of the string will be removed)
          removed. (e.g. "Eth100/1/5" will be saved as "100/1/5").

Cisco, Lenovo and Mellanox switches currently supported by POWER-Up follow
these rules. An example of a user generated "generic" file would be::

    mac address        Port
    -----------------  ----
    0c:c4:7a:20:0d:22    38
    0c:c4:7a:76:b0:9b    19
    0c:c4:7a:76:b1:16    9
    0c:c4:7a:76:c8:ec    37
    40:f2:e9:23:82:ba    18
    40:f2:e9:23:82:be    17
    40:f2:e9:24:96:5a    22
    40:f2:e9:24:96:5e    21
    5c:f3:fc:31:05:f0    13
    5c:f3:fc:31:06:2a    12
    5c:f3:fc:31:06:2c    11
    5c:f3:fc:31:06:ea    16
    5c:f3:fc:31:06:ec    15
    6c:ae:8b:69:22:24    2
    70:e2:84:14:02:92    5
    70:e2:84:14:0f:57    1


SSH Keys
--------

The OpenPOWER POWER-Up Software will generate a passphrase-less SSH
key pair which is distributed to
each node in the cluster in the /root/.ssh directory. The public key is
written to the authorized\_keys file in the /root/.ssh directory and
also to the /home/userid-default/.ssh directory. This key pair can be
used for gaining passwordless root login to the cluster nodes or
passwordless access to the userid-default. On the deployer node, the
key pair is written to the ~/.ssh directory as gen
and gen.pub. To login to one of the cluster nodes
as root from the deployer node::

    ssh -i ~/.ssh/gen root@a.b.c.d

As root, you can log into any node in the cluster from any other node in
the cluster as::

    ssh root@a.b.c.d

Where a.b.c.d is the IP address of the port used for pxe install. These
addresses are stored under the key name *ipv4-pxe* in the inventory file.
The inventory file is stored on every node in the cluster at
/var/oprc/inventory.yml. The inventory file is also stored on the
deployer in the deployer container in the /opt/power-up
directory. A symbolic link to this inventory file is created in
the ~/power-up directory as 'inventorynn.yml', where nn is the number of
the pxe vlan.

Note that you can also log into any node in the cluster using the
credentials specified in the config.yml file (key names *userid-default*
and *password-default*)
