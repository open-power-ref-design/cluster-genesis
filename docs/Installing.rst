.. highlight:: none

.. _installing:

Installing the POWER-Up Software
================================
#.  Verify that all the steps in :ref:`setup-deployer` have been executed.
#.  Login to the deployer node.
#.  Install git

    - Ubuntu::

        $ sudo apt-get install git

    - RHEL::

        $ sudo yum install git

#.  From your home directory, clone POWER-Up::

      $ git clone https://github.com/ibm/power-up

#.  Install the remaining software packages used by Power-Up and
    setup the environment::

      $ cd power-up
      $ ./scripts/install.sh

      (this will take a few minutes to complete)

      $ source scripts/setup-env

    **NOTE:** The setup-env script will ask for permission to add
    lines to your .bashrc file which modify the PATH environment variable.
    It is recommended that you allow this so that the POWER-Up environment
    is restored if you need to re-open the window or open and additional window.
