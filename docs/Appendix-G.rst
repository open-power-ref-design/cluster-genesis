.. _appendix_g:

Appendix - G Configuring Management Access on the Lenovo G8052 and Mellanox SX1410
==================================================================================

For the Lenovo G8052 switch, the following commands can be used to
configure management access on interface 1.  Initially the switch should be
configured with a serial cable so as to avoid loss of communication with the switch
when configuring management access.  Alternately you can configure a second
management interface on a different subnet and vlan.

Enable configuration mode and create vlan::

        RS 8052> enable
        RS 8052# configure terminal
        RS 8052 (config)# vlan 16     (sample vlan #)
        RS G8052(config-vlan)# enable
        RS G8052(config-vlan)# exit

Enable IP interface mode for the management interface::

        RS 8052 (config)# interface ip 1

Assign a static ip address, netmask and gateway address to the management interface.
This must match the address specified in
the config.yml file (keyname: ipaddr-mgmt-switch:) and be in a
*different* subnet than your cluster management subnet. Place this
interface in the above created vlan::

        RS 8052 (config-ip-if)# ip address 192.168.16.20 (example IP address)
        RS 8052 (config-ip-if)# ip netmask 255.255.255.0
        RS 8052 (config-ip-if)# vlan 16
        RS 8052 (config-ip-if)# enable
        RS 8052 (config-ip-if)# exit

Configure the default gateway and enable the gateway::

        ip gateway 1 address 192.168.16.1  (example ip address)
        ip gateway 1 enable

Note: if you are SSH'd into the switch on interface 1, be careful not to
cut off access if changing the ip address. If needed, additional
management interfaces can be set up on interfaces 2, 3 or 4.

For the Mellanox switch, the following commands can be used to configure
the MGMT0 management port;

switch (config) # no interface mgmt0 dhcp

switch (config) # interface mgmt0 ip address <IP address> <netmask>

For the Mellanox switch, the following commands can be used to configure
an in-band management interface on an existing vlan ; (example vlan 10)

switch (config) # interface vlan 10

switch (config interface vlan 10) # ip address 10.10.10.10 /24

To check the config;

switch (config) # show interfaces vlan 10
