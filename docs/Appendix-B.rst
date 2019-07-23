.. highlight:: none

.. _appendix_b:

Appendix - B WMLA Installation for Advanced Users
=================================================

This abbreviated instruction list is for advanced users already familiar with the WMLA install process.

#. Prepare the Client Nodes by completing the 'Setup for automated installer steps' at https://www.ibm.com/support/knowledgecenter/SSFHA8_1.2.1/wmla_auto_install_setup.html

#. Enable EPEL repositories. (https://fedoraproject.org/wiki/EPEL#Quickstart)::

    yum install https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm

#. Enable Red Hat common, optional and extras repositories.

#. Install the PowerUp software::

    sudo yum install git

    git clone https://github.com/ibm/power-up -b wmla121-1.0.0

    cd power-up

    ./scripts/install.sh

    source scripts/setup-env

#. Install Miniconda (Power instructions shown. Accept the license and respond *no* to the prompt to modify your .bashrc file.)::

    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-ppc64le.sh

    bash Miniconda3-latest-Linux-ppc64le.sh

#. Activate conda::

    . miniconda3/etc/profile.d/conda.sh
    conda activate base

#. Extract WMLA. Assuming the WMLA binary is in /home/user/wmla121bin::

    cd /home/user/wmla121bin
    bash ibm-wmla-1.2.1_ppc64le.bin


#. Deactivate Conda::

    conda deactivate

#. Install WMLA::

    pup software --prep wmla121
    pup software --status wmla121
    pup software --init-clients wmla121
    pup software --install wmla121
