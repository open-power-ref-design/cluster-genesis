.. highlight:: none

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

pup <command> [<args>] [options] [--help | -h]

Cluster POWER-Up has extensive logging capabilities. To enable detailed
logging of activities, you can set the log level to debug. To enable
detailed logging to the logs/gen file, add the -f debug option. To enable
detailed display of log information, add -p debug. For additional log level
help, enter -h at the end of a pup command. (ie pup setup -h)

Auto completion is enabled for the pup program. At any level of command
entry, a single tab will complete the current command if it is distinguishable.
Double tabbing after a space will list all available options for that level of
command input.

The following five top level commands are provided;

    - config
    - deploy
    - post-deploy
    - setup
    - validate

The deploy command deploys your cluster;

    pup deploy

POWER-Up goes through the following steps when you enter pup deploy;

    - validate the config file
    - sets up interfaces and networks on the deployer node
    - configures the management switches
    - discovers and validates the cluster hardware
    - creates a container for hosting the rest of the POWER-Up software
    - deploys operating systems to you cluster node
    - sets up ssh keys and user accounts on your cluster nodes
    - configures networking on your cluster nodes
    - configures your data switches

After installing the operating systems, POWER-Up will pause and wait for input
before executing the last 3 steps above. This provides a convenient place to
check on the cluster hardware before proceding. If desired, you can stop
POWER-Up at that point and re-start later by entering 'pup post-deploy'.

It is sometimes useful when first bringing up the cluster hardware to be able to
run the initial steps above individually. The following commands can be used to
individually run / re-run the first four steps above::

    pup validate --config-file
    pup setup --networks
    pup config --mgmt-switches
    pup validate --cluster-hardware

Note that the above steps must initially be run in order. After succesfully
completing the above steps in order, they can be re-run individually. When isolating
cluster hardware issues, it is useful to be able to re-run pup validate
--cluster-hardware.  pup validate --config-file may be run any time as often as
needed.


