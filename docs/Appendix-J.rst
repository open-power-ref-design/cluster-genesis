
Appendix - J Transferring Deployement Container to New Host
===========================================================
**Stil in Development**

TODO: general description

Save Container Files
--------------------

#. Note container name from LXC status::

    user@origin-host:~$ sudo lxc-ls -f

#. Archive LXC files::

    user@origin-host:cluster-genesis/scripts $ ./container_save.sh [container_name]

#. Save config.yml, inventory.yml, and known_hosts files::

    origin-host:<cluster-genesis>/config.yml
    origin-host:/var/oprc/inventory.yml
    origin-host:<cluster-genesis>/playbooks/known_hosts

Prepare New Host
----------------

#. Install git

    - Ubuntu::

        user@new-host:~$ sudo apt-get install git

    - RHEL::

        user@new-host:~$ sudo yum install git

#. From your home directory, clone Cluster Genesis::

    user@new-host:~$ git clone https://github.com/open-power-ref-design-toolkit/cluster-genesis

#. Install the remaining software packages used by Cluster Genesis and
   setup the environment::

    user@new-host:~$ cd cluster-genesis
    user@new-host:~/cluster-genesis$ ./scripts/install.sh

    (this will take a few minutes to complete)::

    user@new-host:~/cluster-genesis$ source scripts/setup-env

    **NOTE:** anytime you leave and restart your shell session, you need to
    re-execute the set-env script. Alternately, (recommended) add the following
    to your .bashrc file; *PATH=~/cluster-genesis/pup-venv/bin:$PATH*

    ie::

    user@new-host:~$ echo "PATH=~/cluster-genesis/pup-venv/bin:\$PATH" >> ~/.bashrc

#. Copy config.yml, inventory.yml, and known_hosts files from origin to new
   host::

    new-host:<cluster-genesis>/config.yml
    new-host:/var/oprc/inventory.yml
    new-host:<cluster-genesis>/playbooks/known_hosts

#. If needed, modify config.yml and inventory.yml 'port-mgmt-network'. This
   value represents the port number that the deployer is connected to the
   management switch.

#. Append cluster-genesis host keys to user's known_hosts::

    user@new-host:~/cluster-genesis$ cat playbooks/known_hosts >> ~/.ssh/known_hosts

    **NOTE:** If user@new-host:~/.ssh/known_hosts already includes keys for
    any of these host IP address this action will result in SSH refusing to
    connect to the host (with host key checking enabled).

#. Make the ~/cluster-genesis/playbooks directory the current working directory::

    user@new-host:~/cluster-genesis$ cd ~/cluster-genesis/playbooks/

#. Setup host networking::

    user@new-host:~/cluster-genesis/playbooks$ ansible-playbook -i hosts lxc-create.yml -K --extra-vars "networks_only=True"

#. Configure management switch::

    user@new-host:~/cluster-genesis/playbooks$ ansible-playbook -i hosts container/set_mgmt_switch_config.yml

Restore container from archive
------------------------------

#. Copy LXC file archive from origin to new host

#. Run 'container_restore.sh' script to install and start container::

    user@new-host:cluster-genesis/scripts $ ./container_restore.sh container_archive [new_container_name]

#. Use LXC status to verify container is running::

    user@new-host:~$ sudo lxc-ls -f
