.. _running_paie:

Running the Watson Machine Learning (WML) Accelerator Software Install Module
===================================================================

Overview
--------
The WML Accelerator software installation can be automated using the POWER-Up software. POWER-Up can run on OpenPOWER or x_86 architecture.

The WML Accelerator Software Install Module provides for rapid installation of the WML Accelerator software or WML Accelerator evaluation software to a cluster of POWER8 or POWER9 servers.
The install module creates a web based software installation server on one of the cluster nodes or another node with access to the cluster.
The software server is populated with repositories and files needed for installation of WML Accelerator.
Once the software server is setup, installation scripts orchestrate the software installation to one or more client nodes. Note that the software installer node requires access to several open source repositories during the 'preparation' phase. During the preparation phase, packages which WML Accelerator is dependent on are staged on the POWER-Up installer node. After completion of the preparation phase, the installation requires no further access to the open source repositories and can thus enable installation to servers which do not have internet access.

The POWER-Up software installer does not currently support installation of WML Accelerator onto the node running the POWER-Up software installer.
If it is necessary to install WML Accelerator onto the node running the POWER-Up software, this can be done manually or can be accomplished by running the POWER-Up software on an additional node in the cluster.
Hint: A second POWER-Up server can be quickly prepared by replicating the repositories from the first POWER-Up server.

Support
-------
Questions regarding the WML Accelerator installation software, installation, or suggestions for improvement can be posted on IBM's developer community forum at https://developer.ibm.com/answers/index.html with the PowerAI tag.

Answered questions regarding PowerAI can be viewed at https://developer.ibm.com/answers/topics/powerai/

Set up of the POWER-Up Software Installer Node
----------------------------------------------

POWER-Up Node  Prerequisites;

#. The POWER-Up software installer currently runs under RHEL 7.4 or above.

#. The user account used to run the POWER-Up software needs sudo privileges.

#. Enable access to the Extra Packages for Enterprise Linux (EPEL) repository. (https://fedoraproject.org/wiki/EPEL#Quickstart)

#. Enable the common, optional and extras repositories.

    # On POWER8::

       $ sudo subscription-manager repos --enable=rhel-7-for-power-le-rpms --enable=rhel-7-for-power-le-optional-rpms --enable=rhel-7-for-power-le-extras-rpms

    # On POWER9::

       $ sudo subscription-manager repos --enable=rhel-7-for-power-9-rpms --enable=rhel-7-for-power-9-optional-rpms --enable=–enable=rhel-7-for-power-9-extras-rpms
    
    # On x86_64::

       $ subscription-manager repos --enable "rhel-*-optional-rpms" --enable "rhel-*-extras-rpms"  --enable "rhel-ha-for-rhel-*-server-rpms"

#. Insure that there is at least 45 GB of available disk space in the partition holding the /srv directory::

    $ df -h /srv

#. Install the version of POWER-Up software appropriate for the version of WML Accelerator you wish to install. The versions listed in the table below are the versions tested with the corresponding release of WML Accelerator;

.. csv-table::
   :header: "WML Accelerator Release", "POWER-Up software installer vs", "Notes", "EOL date"

   "1.1.0", "software-install-b2.5", "", "14 Sep 2018"
   "1.1.1", "software-install-b2.9"
   "1.1.1", "software-install-b2.10", "Updates for x86 based installer node"
   "1.1.1", "software-install-b2.11", "Enable cuda replicate on x86 installer node"
   "1.1.2", "software-install-b2.12", "Support for installation of PAIE 1.1.2"
   "1.2.0", "wmla120",                "Support for installation of WMLA 1.2.0"

From your home directory install the POWER-Up software and initialize the environment. For additional information see :ref:`installing`::

    $ sudo yum install git

    $ git clone https://github.com/open-power-ref-design-toolkit/power-up -b wmla120 

    $ cd power-up

    $ ./scripts/install.sh

    $ source scripts/setup-env

**NOTES:**

- The latest functional enhancements and defect fixes can be obtained by cloning the software installer without specifying the tag release. Generally, you should use a release level specified in the table above unless you are experiencing problems.::

    git clone https://github.com/open-power-ref-design-toolkit/power-up -b wmla120 

- Multiple users can install and use the WMLA installer software, however there is only one software server created and there are no safeguards built in to protect against concurrent modifications of the software server content, data files or client nodes.
- Each user of the WMLA installer software must install the POWER-Up software following the steps above.


Installation of WML Accelerator
----------------------------------

Installation of the WML Accelerator software involves the following steps;

#. Preparation of the client nodes

#. Preparation of the software server

#. Initialization of the cluster nodes

#. Installation of software on the cluster nodes


Preparation of the client nodes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Before beginning automated installation, you should have completed the 'Setup for automated installer steps' at https://www.ibm.com/support/knowledgecenter/SSFHA8_1.1.1/enterprise/powerai_auto_install_setup.html

Before proceeding with preparation of the POWER-Up server, you will need to gather the following information;

-  Fully qualified domain name (FQDN) for each client node
-  Userid and password or private ssh key for accessing the client nodes. Note that for running an automated installation, the same user id and password must exist on all client nodes and must be configured with sudo access.

Preparation of the POWER-Up Software Server
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Before beginning installation of WML Accelerator, the files listed below need to be copied onto the software server node.
The files can be copied anywhere, but the POWER-Up software can locate them quicker if the files are under a subdirectory of one of the /home/ directories or the /root directory.
Note that the WMLA installer will stop searching for installation files if required files are found under one of the directories mentioned above.

-  WML Accelerator binary file. (ibm-wmla-\*_\*.bin)

In addition, the POWER-Up software server needs access to the following repositories during the preparation phase;

-  Red Hat 'common', 'optional' and 'extras'
-  Extra Packages for Enterprise Linux (EPEL)
-  Cuda Toolkit
-  Anaconda

These can be accessed using the public internet (URL's are provided) or via an alternate web site such as an intranet mirror repository, another POWER-Up server or from a mounted USB key. Because the software installer can run on x_86 architecture, a laptop can be used as an installer node, allowing preparation at a location with internet access and installation at a location without internet access.

Before beginning, extract the contents of the powerai-enterprise-\*_*.bin file and accept the license by running the following on the installer node::

    $ sudo bash ./ibm-wmla-*_*.bin

**NOTES:**

-  Extraction and license acceptance of WML Accelerator must be performed on an OpenPOWER node. If you are running the POWER-Up installer software on an x_86 node, you must first extract the files on an OpenPOWER node and then copy all of the extracted contents to the POWER-Up installer node.
-  If running the WML Accelerator installer from an x_86 node, you must download the Red Hat dependent packages on a Power node and copy them to a directory on the x_86 installer node. A utility script is included to facilitate this process. To use the script, insure you have ssh access with sudo privileges to a Power node which has a subscription to the Red Hat 'common', 'optional' and 'extras' channels. (One of the cluster nodes or any other suitable Power node can be used for this purpose). To run the script from the power-up directory on the installer node::

    $ ./software/get-dependent-packages.sh userid hostname

The hostname can be a resolvable hostname or ip address. The get-dependent-packages script will download the required packages on the specified Power node and then move them to the ~/tempdl directory on the installer node. After running the script, run/rerun the --prep phase of installation. For dependent packages, choose option D (Create from files in a local Directory) and enter the full absolute path to the /tempdl directory.

**Status of the Software Server**

At any time, you can check the status of the POWER-Up software server by running::

    $ pup software --status wmla*


To use the automated installer with the evaluation version of WML Accelerator, include the --eval switch in all pup commands. ie::

    $ pup software --status --eval wmla*

Note: The POWER-Up software installer runs python installation modules. Inclusion of the '.py' in the software module name is optional. ie For WML Accelerator version 1.1.1, paie111 or paie111.py are both acceptable.

**Hint: The POWER-Up command line interface supports tab autocompletion.**

Preparation is run with the following POWER-Up command::

    $ pup software --prep wmla*

Preparation is interactive and may be rerun if needed. Respond to the prompts as appropriate for your environment. Note that the EPEL, Cuda, dependencies and Anaconda repositories can be replicated from the public web sites or from alternate sites accessible on your intranet environment or from local disk (ie from a mounted USB drive). Most other files come from the local file system except for the Anaconda package which can be downloaded from the public internet during the preparation step.


Initialization of the Client Nodes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
During the initialization phase, you will need to enter a resolvable hostname for each client node. Optionally you may enter the path of a private ssh key file. If one is not available, an ssh key pair will be automatically generated. You will also be prompted for a password for the client nodes.

To initialize the client nodes and enable access to the POWER-Up software server::

    $ pup software --init-clients wmla*

Note: Initialization of client nodes can be rerun if needed.

Installation
~~~~~~~~~~~~
To install the WML Accelerator software and prerequisites::

    $ pup software --install wmla*

NOTES:

-  During the installation phase you will be required to provide values for certain environment variables needed by Spectrum Conductor with Spark and Spectrum Deep Learning Impact. An editor window will be automatically opened to enable this.
    -  If left blank, the CLUSTERADMIN variable will be automatically populated with the cluster node userid provided during the init-client phase of installation.
    -  The DLI_SHARED_FS environment variable should be the full absolute path to the shared file system mount point. (eg DLI_SHARED_FS: /mnt/my-mount-point). The shared file system and the client node mount points need to be configured prior to installing WML Accelerator.
    -  If left blank, the DLI_CONDA_HOME environment variable will be automatically populated. If entered, it should be the full absolute path of the install location for Anaconda. (ie DLI_CONDA_HOME: /opt/anaconda2)
-  Installation of WML Accelerator can be rerun if needed.

After completion of the installation of the WML Accelerator software, you must configure Spectrum Conductor Deep Learning Impact and apply any outstanding fixes.
Go to https://www.ibm.com/support/knowledgecenter/SSFHA8, choose your version of WML Accelerator and then use the search bar to search for ‘Configure IBM Spectrum Conductor Deep Learning Impact’.

Additional Notes
~~~~~~~~~~~~~~~~

You can browse the content of the POWER-Up software server by pointing a web browser
at the POWER-Up installer node. Individual files can be copied to client nodes using wget or
curl if desired.

**Dependent software packages**
The WML Accelerator software is dependent on additional open source software that is not shipped with WML Accelerator.
Some of these dependent packages are downloaded to the POWER-Up software server from enabled yum repositories during the preparation phase and are subsequently available to the client nodes during the install phase.
Additional software packages can be installed in the 'dependencies' repo on the POWER-Up software server by listing them in the power-up/software/dependent-packages.list file.
Entries in this file can be delimited by spaces or commas and can appear on multiple lines.
Note that packages listed in the dependent-packages.list file are not automatically installed on client nodes unless needed by the PowerAI software.
They can be installed on a client node explicitly using yum on the client node (ie yum install pkg-name). Alternatively, they can be installed on all client nodes at once using Ansible (run from within the power-up/playbooks/ directory)::

    $ ansible all -i software_hosts -m yum -a "name=pkg-name"

or on a subset of nodes (eg the master nodes) ::

    $ ansible master -i software_hosts -m yum -a "name=pkg-name"

Uninstalling the POWER-Up Software
----------------------------------
To uninstall the POWER-Up software and remove the software repositories, follow the instructions below;
#. Identify platform to remove::

    $ PLATFORM="ppc64le" # or could be x86_64

#. Stop and remove the nginx web server::

    $ sudo nginx -s stop
    $ sudo yum erase nginx -y

#. If you wish to remove the http service from the firewall on this node::

    $ sudo firewall-cmd --permanent --remove-service=http
    $ sudo firewall-cmd --reload

#. If you wish to stop and disable the firewall service on this node::

    $ sudo systemctl stop firewalld.service
    $ sudo systemctl disable firewalld.service

#. Remove the yum.repo files created by the WMLA installer::

    $ sudo rm /etc/yum.repos.d/cuda-local.repo
    $ sudo rm /etc/yum.repos.d/cuda.repo
    $ sudo rm /etc/yum.repos.d/dependencies-local.repo
    $ sudo rm /etc/yum.repos.d/dependencies.repo
    $ sudo rm /etc/yum.repos.d/epel-${PLATFORM}-local.repo
    $ sudo rm /etc/yum.repos.d/epel-*.repo
    $ sudo rm /etc/yum.repos.d/power-ai-local.repo
    $ sudo rm /etc/yum.repos.d/nginx.repo

#. Remove the software server content and repositories::

    $ sudo rm -rf /srv/anaconda
    $ sudo rm -rf /srv/power-ai
    $ sudo rm -rf /srv/wmla-license
    $ sudo rm -rf /srv/spectrum-dli
    $ sudo rm -rf /srv/spectrum-conductor
    $ sudo rm -rf /srv/repos

#. Remove the yum cache data depending on Computer Architecture::
    
    $ sudo rm -rf /var/cache/yum/${PLATFORM}/7Server/cuda/
    $ sudo rm -rf /var/cache/yum/${PLATFORM}/7Server/cuda-local/
    $ sudo rm -rf /var/cache/yum/${PLATFORM}/7Server/dependencies/
    $ sudo rm -rf /var/cache/yum/${PLATFORM}/7Server/dependencies-local/
    $ sudo rm -rf /var/cache/yum/${PLATFORM}/7Server/epel-${PLATFORM}/
    $ sudo rm -rf /var/cache/yum/${PLATFORM}/7Server/epel-${PLATFORM}-local/
    $ sudo rm -rf /var/cache/yum/${PLATFORM}/7Server/power-ai-local/
    $ sudo rm -rf /var/cache/yum/${PLATFORM}/7Server/nginx/

#. Uninstall the WML Accelerator license program from the installer node. If you extracted the WML Accelerator package on this node and accepted the enterprise license::

    $ sudo yum erase wmla-license -y

#. Uninstall the PowerUp Software
    - Assuming you installed from your home directory, execute::

        $ sudo rm -rf ~/power-up
