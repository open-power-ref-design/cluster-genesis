Building the Introspection Kernel and Filesystem
================================================

*Note:*  Introspection is not yet supported in POWER-Up 2.0

Introspection enables the clients to boot a Linux mini-kernel and filesystem
prior to deployment. This allows Cluster Genesis to extract client hardware
resource information and provides an environment for users to run configuration
scripts (e.g. RAID volume management).

Building
--------------------

#.  By default, the introspection kernel is built automatically whenever one of
    the following commands are executed, and the introspection option is enabled
    in the config.yml file ::

     cd cluster-genesis/playbooks
     ansible_playbook -i hosts lxc-create.yml -K
     ansible_playbook -i hosts lxc-introspect.yml -K
     ansible_playbook -i hosts introspection_build.yml -K

     or

     gen deploy #if introspection was specified in the config.yml file

#.  Wait for introspection_build.yml playbook to complete.  If the rootfs.cpio.gz and
    vmlinux images already exist, the playbook will not rebuild them.
#.  The final kernel and filesystem will be copied from the deployer container to the
    host filesystem under 'cluster-genesis/os_images/introspection'

Buildroot Config Files
~~~~~~~~~~~~~~~~~~~~~~

Introspection includes a default buildroot and linux kernel config files.

These files are located in introspection/configs directory under cluster-genesis.

If there are any additional features or packages that you wish to add to the
introspection kernel, they can be added to either of the configs prior to
setup.sh being executed.

Run Time
-------------------
Average load and build time on a POWER8 Server(~24 mins)

Public Keys
-------------------
To append a public key to the buildroot filesystem

#. Build.sh must have been run prior
#. Execute add_key.sh <key.pub>
#. The final updated filesystem will be placed into
   output/rootfs.cpio.gz

