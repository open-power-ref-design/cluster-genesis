.. _wmla_airgap_install:

Running the WMLA install module in an air-gapped environment
============================================================

Overview
--------
POWER-Up can be used to install Watson Machine Learning Accelerator in an
air-gapped environment (i.e. isolated network without access to public software
repositories).

Required dependencies first must be collected using
`pup software wmla121 --prep` in an environment with access repositories. Once
collected the dependencies can be bundled into an archive to facilitate easy
transfer into the air-gapped environment.

Collect and bundle dependencies
-------------------------------

#. :ref:`Setup installer node <Running-paie:Set up of the POWER-Up Software Installer Node>`

#. :ref:`Collect WMLA software<Running-paie:Copy or Extract the WMLA software packages onto the PowerUp installation node.>`

#. Run --prep to collect WMLA dependencies::

    $ pup software wmla121 --prep

#. Run --download-install-deps to collect POWER-Up install dependencies::

    $ pup software wmla121 --download-install-deps

#. Run --status to verify all dependencies are present::

    $ pup software wmla121 --status

#. Run --bundle-to to archive dependencies in single file::

    $ pup software wmla121 --bundle-to ./

#. Archive can now be transferred::

    $ ls wmla.*.tar

Install and run POWER-Up using dependency archive
-------------------------------------------------

#. Extract archive::

    $ sudo mkdir -p /srv/pup/wmla121-ppc64le/
    $ sudo tar xvf wmla.*.tar -C /srv/pup/wmla121-ppc64le/

#. Enable local yum repository::

    $ echo "[pup-install]
    name=POWER-Up Installation Dependencies
    baseurl=file:///srv/pup/wmla121-ppc64le/repos/pup_install_yum/rhel/7/family/pup_install_yum/
    enabled=1
    gpgcheck=0" | sudo tee /etc/yum.repos.d/pup-install.repo

#. Update yum cache::

    $ sudo yum makecache

#. Install Git::

    $ sudo yum -y install git

#. Clone POWER-UP from local repo::

    $ git clone /srv/pup/wmla121-ppc64le/power-up.git/

#. Checkout POWER-UP release tag::

    $ cd power-up
    $ git checkout wmla121-1.0.1

#. Install POWER-Up software::

    $ ./scripts/install.sh -p /srv/pup/wmla121-ppc64le/repos/pup_install_pip/
    $ source ./scripts/setup-env

#. Verify all dependencies are present::

    $ pup software wmla121 --status

Continue with '--init-clients' and '--install'
----------------------------------------------

#. :ref:`Initialize Client Nodes <Running-paie:Initialization of the Client Nodes>`

#. :ref:`Installation <Running-paie:Installation>`
