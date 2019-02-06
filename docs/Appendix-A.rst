.. highlight:: none

.. _appendix_a:

Appendix - A Using the 'pup' Program
====================================


The 'pup' program is the primary interface to the Cluster POWER-Up software.
Help can be accessed by typing::

    pup -h
    or
    pup --help

Help is context sensitive and will give help appropriate for the argument.
For example, 'pup setup -h' will provide help on the setup function.

Usage;

pup [command] [<args>] [options] [--help | -h]

Cluster POWER-Up has extensive logging capabilities. Logging can take place to
the screen and a log file (power-up/logs/gen) and the logging level can be
set individually for the screen and file. By default, file logging is set to
debug and screen logging is set to info.

To enable detailed logging to the screen, add the -p debug option. For additional
log level help, enter -h at the end of a pup command. (ie pup setup -h)

Auto completion is enabled for the pup program. At any level of command
entry, a single tab will complete the current command if it is distinguishable.
Double tabbing will list all available options for that level of
command input.

The following top level commands are provided;

    - config
    - deploy
    - post-deploy
    - setup
    - software
    - utils
    - validate

Bare Metal Deployment
~~~~~~~~~~~~~~~~~~~~~

The deploy command deploys your cluster;

    pup deploy [config-file-name]

For bare metal deploy, POWER-Up goes through the following steps when you enter pup deploy;

    - validate the config file
    - sets up interfaces and networks on the deployer node
    - configures the management switches
    - discovers and validates the cluster hardware
    - creates a container for hosting the rest of the POWER-Up software
    - deploys operating systems to your cluster node
    - sets up ssh keys and user accounts on your cluster nodes
    - configures networking on your cluster nodes
    - configures your data switches

After installing the operating systems, POWER-Up will pause and wait for input
before executing the last 3 steps above. This provides a convenient place to
check on the cluster hardware before proceeding. If desired, you can stop
POWER-Up at that point and re-start later by entering 'pup post-deploy'.

It is sometimes useful when first bringing up the cluster hardware to be able to
run the initial steps above individually. The following commands can be used to
individually run / re-run the first four steps above::

    pup validate --config-file [config-file-name]
    pup setup --networks [config-file-name]
    pup config --mgmt-switches [config-file-name]
    pup validate --cluster-hardware [config-file-name]

Note that the above steps must initially be run in order. After successfully
completing the above steps in order, they can be re-run individually. When isolating
cluster hardware issues, it is useful to be able to re-run pup validate
--cluster-hardware.  pup validate --config-file may be run any time as often as
needed.

Software Installation
~~~~~~~~~~~~~~~~~~~~~

POWER-Up provides the ability to install software to a cluster of nodes.

To deploy software;

pup software [{--prep, --install}] [software-name]

Software installation is broken into two phases.  The 'prep' phase copies / downloads
packages and binaries and syncs any specified repositories to the POWER-Up node. The
nginx web server is installed and software is moved to the /srv directory and made available via the web server. The install phase creates linkages on the client nodes to repositories
on the POWER-Up node and then installs and configures the software.

After software is installed in /srv/ or directory associated with the software dependent package. The software can be archived 
by using this command::
   
   pup software <software>.py --bundle_to "/path/to/directory/"

This will take some time depending on size of directory and will produce a tarfile 
so it can be stored in a device or transferred to other operating system::
    
   INFO - /tmp/srv/tmp8cut_euk
   INFO - not compressing
   INFO - archiving /srv/ to /tmp/srv/tmp8cut_euk
   INFO - created: /tmp/srv/tmp8cut_euk, size in bytes: 1075200, total time: 0 seconds

To extract tar file simply use linux command::

   tar -xvf /tmp/srv/tmp8cut_euk # to extract the file to the current directory or directory of choice.

if pup software is installed run command on deployment node::

   pup software  <software>.py --extract_from /path/to/your/tarfile/tmp8cut_euk

this will extract software to assigned pup software directory as described in the <software>.py file


Utilities
~~~~~~~~~~~~~~~~~~~~~

POWER-Up provides utility functions to be used on deployer node.


To archive a software directory::

   pup utils <config-file>.yml --bundle_to "/tmp/srv" --bundle_from "/srv/"

