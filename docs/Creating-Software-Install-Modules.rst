.. highlight:: none

.. _creating-install-modules:

Creating Software Install Modules
=================================

POWER-Up provides a simple framework for running user provided software install modules. Software install modules are Python modules.  The module may be given any valid Python module name. A POWER-Up software install module can contain any user provided code, but it must implement a class named 'software' and the software class must implement the following methods;

-  setup
-  init
-  install

The setup method is generally intended to provide setup of repositories and directories and installation and configuration of a web server. POWER-Up provides support for setting up an EPEL mirror and supports installation of the nginx web server. In order to facilitate software installation to clusters without internet access, the setup method is intended to be able to run without access to the cluster nodes to facilitate preloading of required software on a laptop or other node prior to being connected to the cluster.

The init method should provide for license accept activities and setting up client nodes to use the POWER-Up node for any implemented repositories. POWER-Up install includes Ansible.  The init method may make use of any Ansible modules or POWER-Up provided playbooks.

The install method needs to implement the logic for installing the desired software packages and binaries on the cluster nodes.
