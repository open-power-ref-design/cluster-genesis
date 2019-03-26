.. highlight:: none

.. _appendix_b:

Appendix - B WMLA Installation for Advanced Users
=================================================

This abbreviated instruction list is for advanced users already familiar with the WMLA install process.

#. Prepare the Client Nodes by completing the 'Setup for automated installer steps' at https://www.ibm.com/support/knowledgecenter/SSFHA8_1.2.0/wmla_auto_install_setup.html

#. Enable EPEL repositories. (https://fedoraproject.org/wiki/EPEL#Quickstart)::

    yum install https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm::

#. Enable Red Hat common, optional and extras repositories.

#. Install the PowerUp software::

    sudo yum install git

    git clone https://github.com/open-power-ref-design-toolkit/power-up -b wmla120-1.0

    cd power-up

    ./scripts/install.sh

    source scripts/setup-env

#. Install Miniconda (Power instructions shown. Accept the license and respond *no* to the prompt to modify your .bashrc file.)::

    wget https://repo.anaconda.com/miniconda/Miniconda2-latest-Linux-ppc64le.sh

    bash Miniconda2-latest-Linux-ppc64le.sh

#. Activate conda::

    . miniconda2/etc/profile.d/conda.sh
    conda activate base

#. Extract WMLA. Assuming the WMLA binary is in /home/user/wmla120bin::

    cd /home/user/wmla120bin
    bash ibm-wmla-1.2.0_ppc64le.bin

    for x86

    bash ibm-wmla-1.2.0_x86_64.bin

#. Deactivate Conda::

    conda deactivate

#. Install WMLA::

    pup software --prep wmla120
    pup software --status wmla120
    pup software --init-clients wmla120
    pup software --install wmla120
