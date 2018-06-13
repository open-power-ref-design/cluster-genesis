.. highlight:: none

Running the POWER-Up Software Installation Software
===================================================

**Under development. This functionality is not yet supported in the master
branch of POWER-Up. Development of this function is in the dev-software-install
branch.**

-  Verify that all the steps in :ref:`installing` have been executed.
-  Copy or download the software install module to be used to the power-up/software directory. POWER-Up currently ships with the installer module for PowerAI Enterprise vs 5.2. (paie52). See :ref:`running_paie`
-  Consult the README for the specific software install module for the names of any tar files, binaries or other files needed for the specific software installation. Copy these to the installer node before running the software install module. Installation files can be copied anywhere on the installer node but will be located more quickly if located in directories under a /home directory.

Run the prep phase::

    $ pup software --prep <install module name>

After successful completion, run the init or install phase. (Install will run the init phase prior to installation phase)::

    $ pup software --init-clients <install module name>

    $ pup software --install <install module name>


POWER-Up provides a simple framework for running user provided software install modules.
See :ref:`creating-install-modules` for guidance on how to create these modules.
