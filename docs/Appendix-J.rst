.. _running_paie:

Appendix - J Running the PowerAI Enterprise Software Install Module
===================================================================

Overview
--------
The POWER-Up software can run on OpenPOWER or x_86 architecture.

The PowerAI Enterprise Software Install Module provides for rapid installation of the PowerAI Enterprise software to a cluster of POWER8 or POWER9 servers.
The install module creates a web based software installation server on one of the cluster nodes or another node with access to the cluster.
The software server is populated with repositories and files needed for installation of PowerAI Enterprise.
Once the software server is setup, installation scripts orchestrate the software installation to one or more client nodes.
The POWER-Up software installer does not currently support installation of PowerAI Enterprise onto the node running the POWER-Up software installer.
If it is necessary to install PowerAI Enterprise onto the node running the POWER-Up software, this can be done manually or can be accomplished by running the POWER-Up software on an additional node in the cluster.
Hint: A second POWER-Up server can be quickly prepared by replicating the repositories from the first POWER-Up server.

Support
-------
Questions regarding the PowerAI Enterprise installation software, installation, or suggestions for improvement can be posted on IBM's developer community forum at https://developer.ibm.com/answers/index.html with the PowerAI tag.

Answered questions regarding PowerAI can be viewed at https://developer.ibm.com/answers/topics/powerai/

Set up of the POWER-Up Software Installer Node
----------------------------------------------

POWER-Up Node  Prerequisites;

#. The POWER-Up software installer currently runs under RHEL 7.2 or above.

#. The user account used to run the POWER-Up software needs sudo privileges.

#. Enable access to the Extra Packages for Enterprise Linux (EPEL) repository. (https://fedoraproject.org/wiki/EPEL#Quickstart)

#. Enable the common, optional and extras repositories.

    On POWER8::

    $ sudo subscription-manager repos --enable=rhel-7-for-power-le-rpms --enable=rhel-7-for-power-le-optional-rpms --enable=rhel-7-for-power-le-extras-rpms

    On POWER9::

    $ sudo subscription-manager repos --enable=rhel-7-for-power-9-rpms --enable=rhel-7-for-power-9-optional-rpms --enable=–enable=rhel-7-for-power-9-extras-rpms

#. Insure that there is at least 40 GB of available disk space in the partition holding the /srv directory::

    $ df -h /srv

From your home directory install the POWER-Up software and initialize the environment.
For additional information, see :ref:`installing`::

    $ sudo yum install git

    $ git clone https://github.com/open-power-ref-design-toolkit/power-up -b software-install-b1

    $ cd power-up

    $ ./scripts/install.sh

    $ source scripts/setup-env

Installation of PowerAI Enterprise
----------------------------------

Installation of the PowerAI Enterprise software involves the following steps;

#. Preparation of the client nodes

#. Preparation of the software server

#. Initialization of the cluster nodes

#. Installation of software on the cluster nodes


Preparation of the client nodes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Insure that the set up steps on IBM Knowledge Center up through and including 'Mount a shared file system' have been completed. Record the following information;

-  hostname for each client node
-  Userid and password or private ssh key for the client nodes. Note that for installation, the same user id and password must exist on all client nodes. The user id used for installation must be configured with sudo access.

https://www.ibm.com/support/knowledgecenter/SSFHA8_1.1.0/enterprise/powerai_setup.html

**Status of the Software Server**

At any time, you can check the status of the POWER-Up software server by running::

    $ pup software --status paie52

**Hint: The POWER-Up command line interface supports tab autocompletion.**

Preparation of the POWER-Up Software Server
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Before beginning installation of PowerAI Enterprise, the files listed below need to be copied onto the software server node.
The files can be copied anywhere, but the POWER-Up software can locate them quicker if the files are under one of the /home/ directories.

-  PowerAI Enterprise binary file. (powerai-enterprise-1.1.0_ppc64le.bin)
-  Cuda cudnn (cudnn-9.2-linux-ppc64le-v7.1.tgz)
-  Cuda nccl v2 (nccl_2.2.12-1+cuda9.2_ppc64le.tgz)

In addition, the POWER-Up software server needs access to the following repositories during the preparation phase;

-  Red Hat 'common', 'optional' and 'extras'
-  Extra Packages for Enterprise Linux (EPEL)
-  Cuda Toolkit
-  Anaconda

These can be accessed using the public internet (URL's are provided) or via an alternate web site such as an intranet mirror repository or from a mounted USB key.

Before beginning, extract the contents of the powerai-enterprise-1.1.0_ppc64le.bin file and accept the license by running the following on the installer node::

    $ sudo bash ./powerai-enterprise-1.1.0_ppc64le.bin

NOTE: Extraction and license acceptance must be run on an OpenPOWER node. If you are running the POWER-Up installer software on an x_86 node, you must first extract the files on an OpenPOWER node and then copy all of the extracted contents to the POWER-Up installer node.

Preparation is run with the following POWER-Up command::

    $ pup software --prep paie52

Preparation is interactive. Respond to the prompts as appropriate for your environment. Note that the EPEL, Cuda, dependencies and Anaconda repositories can be replicated from the public web sites or from alternate sites accessible on your intranet environment or from local disk (ie from a mounted USB drive). Most other files come from the local file system except for the Anaconda package which can be downloaded from the public internet during the preparation step.

**Dependent software packages**
The PowerAI Enterprise software is dependent on additional open source software that is not shipped with PowerAI Enterprise.
These dependent packages are downloaded to the POWER-Up software server from enabled yum repositories during the preparation phase and are subsequently available to the client nodes during the install phase.
Additional software packages can be installed in the 'dependencies' repo on the POWER-Up software server by listing them in the power-up/software/dependent-packages.list file.
Entries in this file can be delimited by spaces or commas and can appear on multiple lines.
Note that packages listed in the dependent-packages.list file are not automatically installed on client nodes unless needed by the PowerAI software.
They can be installed on a client node explicitly using yum on the client node (ie yum install pkg-name). Alternatively, they can be installed on all client nodes at once using Ansible (run from within the power-up/software/ directory)::

    $ ansible all -i software_hosts -m yum -a "name=pkg-name"

or on a subset of nodes (eg the master nodes) ::

    $ ansible master -i software_hosts -m yum -a "name=pkg-name"


Initialization of the Client Nodes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
During the initialization phase, you will need to enter a resolvable hostname for each client node. Optionally you may enter the path of a private ssh key file. If one is not available, an ssh key pair will be automatically generated. You will also be prompted for a password for the client nodes.

To initialize the client nodes and enable access to the POWER-Up software server::

    $ pup software --init-clients paie52

Installation
~~~~~~~~~~~~
To install the PowerAI base software Frameworks and prerequisites::

    $ pup software --install paie52

After completion of the installation of the PowerAI frameworks, continue installation of PowerAI Enterprise at the step labeled 'Configure the system for IBM Spectrum Conductor Deep Learning Impact' at https://www.ibm.com/support/knowledgecenter/SSFHA8_1.1.0/enterprise/powerai_install.html

**Note:** After installation of the PowerAI base components, Conductor with Spark and the DLI binary files can be copied to all client nodes at once, by executing the following Ansible commands on the installer node::

    $ ansible all -i software_hosts -m get_url -a 'owner=pai-user group=pai-user checksum=md5:f3d4e52ce23e7fbe6909ddc2e8a85166 url=http://installer-hostname/spectrum-conductor/cws-2.2.1.0_ppc64le.bin dest=/home/pai-user/'

    $ ansible all -i software_hosts -m get_url -a 'owner=pai-user group=pai-user checksum=md5:5529a3c74cea687e896e1d226570d799 url=http://installer-hostname/spectrum-dli/dli-1.1.0.0_ppc64le.bin dest=/home/pai-user/'

Adjust the owner, group and dest fields as appropriate for your installation.

**Hint: You can browse the content of the POWER-Up software server by pointing a web browser at the POWER-Up installer node. Individual files can be copied to client nodes using wget or curl.**
