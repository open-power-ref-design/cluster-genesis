.. _creating_the_config_file:

Creating the Config File
========================

The config file drives the creation of the cluster. It is in YAML format which
is stored as readable text. The lines must be terminated with a newline
character (\\n).  When creating or editing the file on the Microsoft Windows
platform be sure to use an editor, such as *LibreOffice*, which supports saving
text files with the newline terminating character or use *dos2unix* to convert
the windows text file to unix format.

Sample config files can be found in the *power-up/sample-configs*
directory. Once a config file has been created, rename it to *config.yml* and
move it to the project root directory. YAML files support data structures such
as lists, dictionaries and scalars.  The *Cluster Configuration File
Specification* describes the various fields.

See :doc:`Config-Specification`.

YAML files use spaces as part of its syntax. For example, elements of the same
list must have the exact same number of spaces preceding them. When editing the
config file pay careful attention to spaces at the start of lines.  Incorrect
spacing can result in failure to parse the file.

Schema and logic validation of the config file can be performed with the
*pup.py* command::

    $ cd power-up
    $ source pup-venv/bin/activate
    $ ./scripts/python/pup.py validate --config-file

Switch Mode
-----------

Active Switch Mode
~~~~~~~~~~~~~~~~~~

This mode allows the switches to be automatically configured during deployment.

Passive Switch Mode
~~~~~~~~~~~~~~~~~~~

This mode requires the user to manually configure the switches and to write
switch MAC address tables to file.

Passive management switch mode and passive data switch mode can be configured
independently, but passive and active switches of the same classification
cannot be mixed (i.e. all data switches must either be active or passive).

See :ref:`Config Specification - Globals Section <Config-Specification:globals:>`.

**Passive Management Switch Mode**:

Passive management switch mode requires the user to configure the management
switch *before* initiating a deploy. The client network must be isolated from
any outside servers. IPMI commands will be issued to any system BMC that is set
to DHCP and has access to the client network.

**Passive Data Switch Mode**:

Passive data switch mode requires the user to configure the data switch in
accordance with the defined networks. The node interfaces of the cluster will
still be configured.

Networks
--------

The network template section defines the networks or groups of networks and
will be referenced by the *Node Template* members.

See :ref:`Config Specification - Networks Section <Config-Specification:networks:>`.

Node Templates
--------------

The order of the individual ports under the *ports* list is important since the
index represents a node and is referenced in the list elements under the *pxe*
and *data* keys.

See :ref:`Config Specification - Node Templates Section <Config-Specification:node_templates:>`.

Renaming Interfaces
~~~~~~~~~~~~~~~~~~~

The *rename* key provides the ability to rename ethernet interfaces. This
allows the use of heterogeneous nodes with software stacks that need consistent
interface names across all nodes. It is not necessary to know the existing
interface name. The cluster configuration code will find the MAC address of the
interface cabled to the specified switch port and change it accordingly.

Install Device
~~~~~~~~~~~~~~

The *install_device* key is the disk to which the operating system will be
installed. Specifying this disk is not always obvious because Linux naming is
inconsistent between boot and final OS install. For OpenPOWER S812LC, the two
drives in the rear of the unit are typically used for OS install. These drives
should normally be specified as */dev/sdj* and */dev/sdk*.

Post POWER-Up Activities
------------------------

Once deployment has completed it is possible to launch additional commands or
scripts specified in the *Software Bootstrap* section.  These can perform
configuration actions or bootstrap install of additional software packages.
Commands can be specified to run on all cluster nodes or only specific nodes
determined by the compute template name.

See :ref:`Config Specification - Software Bootstrap Section <Config-Specification:software_bootstrap:>`.
