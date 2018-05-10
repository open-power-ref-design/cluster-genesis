.. highlight:: none

Running the POWER-Up Software Installation Software
===================================================

**Under development. This functionality is not yet supported in the master
branch of POWER-Up. Development of this function is in the dev-software-install
branch.**

-  Verify that all the steps in :ref:`installing` have been executed.
-  Copy or download the software install module to be used.
-  Copy the tar files, binaries and other files needed to be installed or gather
   the necessary web links where files can be accessed.

Run the prep phase::

    $ pup software --prep <install module name>

After successful completion, run the init or install phase. (Install will run the init phase prior to installation phase)::

    $ pup software --init <install module name>

    $ pup software --install <install module name>


POWER-Up provides a simple framework for running user provided software install modules.
See :ref:`creating-install-modules` for guidance on how to create these modules.
