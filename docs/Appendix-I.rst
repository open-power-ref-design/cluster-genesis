.. highlight:: none

Appendix - I Using the 'teardown' Program
=========================================


The 'teardown' program allows for select 'tear down' of the POWER-Up
environment on the deployer node and cluster switches. It is primarily used
when redeploying your cluster for test purposes, after taking corrective action
after previous deployment failures or for removing the POWER-Up environment
from the deployer node.

Similar to the pup program, teardown has built in help and supports tab completion.

Usage::

	teardown <command> [<args>] [options] [–help | -h]

The teardown program can perform the following
functions;

    - Destroy the container associated with the current config.yml file.
      $ teardown deployer --container
    - Undo the deployer network configuration associated with the current
      config.yml file
      $ teardown deployer --networks
    - Undo the configuration of the data switches associated with the current
      config.yml file.
      $ teardown switches --data

**NOTE:** teardown actions are driven by the current config.yml file. If you
wish to make changes to your cluster configuration, be sure to teardown the
existing cluster configuration before changing your config.yml file.

For a typical re-deploy where the POWER-Up software does not need
updating, you should teardown the deployer container and the data switches
configuration.
