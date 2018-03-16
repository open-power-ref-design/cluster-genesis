
Appendix - E Example system 2 - Simple Cluster with High Availability Network
=============================================================================

.. figure:: _images/simple-ha-cluster.png
   :alt:
   :width: 6.94650in
   :height: 4.87170in
   :align: center

   High Availability Network using MLAG

The config file below defines two compute node templates and multiple network
templates.  The sample cluster can be configured with the provided config.yml file.
The deployer node needs to have access to the internet for accessing packages.

Various OpenPOWER nodes can be used such as the S821LC.  The deployer node can be OpenPOWER
or alternately a laptop which does not need to remain in the cluster.  The data switch can be
Mellanox SX1700 or SX1410. The management switch must be a
Lenovo G8052 switch::

    # This sample configuration file documents all of the supported key values
    # supported by the genesis software.  It can be used as the basis for creating
    # your own config.yml file.  Note that keywords with a leading underscore
    # can be changed by the end user as appropriate for your application. (e.g.
    # "_rack1" could be changed to "base-rack")

    version: 1.1

    ipaddr-mgmt-network: 192.168.16.0/24
    ipaddr-mgmt-client-network: 192.168.20.0/24
    vlan-mgmt-network: 16
    vlan-mgmt-client-network: 20
    port-mgmt-network: 19
    # Note: The "_rack:" keywords must match the the corresponding rack keyword
    # under the keyword;
    # node-templates:
    #     _node name:
    #         ports:
    port-mgmt-data-network:
        _rack1:
            - 45
            - 47
    ipaddr-mgmt-switch:
        _rack1: 192.168.16.20
    cidr-mgmt-switch-external-dev: 10.0.48.3/24
    ipaddr-mgmt-switch-external:
        _rack1: 10.0.48.20      # must be present on the switch to start
    ipaddr-data-switch: # With MLAG
        _rack1:
            - passmlagdsw1_192.168.16.25
            - passmlagdsw2_192.168.16.30
    ipaddr-mlag-vip:
        _rack1: 192.168.16.254
    cidr-mlag-ipl:
        _rack1:
            - 10.0.0.1/24
            - 10.0.0.2/24
    mlag-vlan:
        _rack1: 4000
    mlag-port-channel:
        _rack1: 6
    mlag-ipl-ports:
        _rack1:
            -
                - 35
                - 36
            -
                - 35
                - 36
    redundant-network: false
    userid-default: ubuntu
    password-default: passw0rd
    userid-mgmt-switch: admin        # applies to all mgmt switches
    password-mgmt-switch: admin      # applies to all mgmt switches
    userid-data-switch: admin
    password-data-switch: admin
    networks:
        _external1:
            description: Interface for eth10
            method: manual
            eth-port: eth10
            mtu: 9000
        _external2:
            description: Interface for eth11
            method: manual
            eth-port: eth11
            mtu: 9000
        _external3:
            description: Interface for eth12
            method: manual
            eth-port: eth12
            mtu: 9000
        _external4:
            description: Interface for eth13
            method: manual
            eth-port: eth13
            mtu: 9000
        _pxe-dhcp:
            description: Change pxe port(eth15) to dhcp
            method: dhcp
            eth-port: eth15
        _standalone-bond0:
            description: Multilink bond
            bond: mybond0
            addr: 10.0.16.0/22
            available-ips:
                - 10.0.16.150              # single address
                - 10.0.16.175 10.0.16.215  # address range
            broadcast: 10.0.16.255
            gateway: 10.0.16.1
            dns-nameservers: 10.0.16.200
            # dns-search: mycompany.domain.com
            method: static
            # name of physical interfaces to bond together.
            bond-interfaces:
                - eth10
                - eth11
            mtu: 9000
            # if necessary not all bond modes support a primary slave
            bond-primary: eth10
            # bond-mode, needs to be one of 7 types
            # either name or number can be used.
            # 0 balance-rr
            # 1 active-backup
            # 2 balance-xor
            # 3 broadcast
            # 4 802.3ad
            # 5 balance-tlb
            # 6 balance-alb
            # bond-mode: active-backup
            bond-mode: 4
            # there is a long list of optional bond arguments.
            # Specify them here and they will be added to end of bond definition
            optional-bond-arguments:
                bond-miimon: 100
                bond-lacp-rate: 1
        _standalone-bond1:
            description: bond network to be used by future bridges
            bond: mybond1
            method: manual
            bond-interfaces:
                - eth12
                - eth13
            mtu: 9000
            bond-primary: eth12
            bond-mode: 4
            optional-bond-arguments:
                bond-miimon: 100
                bond-lacp-rate: 1
    node-templates:
        node-type1:
            hostname: gandalf
            userid-ipmi: ADMIN
            password-ipmi: admin
            cobbler-profile: ubuntu-16.04.2-server-ppc64el
            os-disk: /dev/sdj
            name-interfaces:
                mac-pxe: eth15    # This keyword is paired to ports: pxe: keyword
                mac-eth10: eth10  # This keyword is paired to ports: eth10: keyword
                mac-eth11: eth11  # This keyword is paired to ports: eth11: keyword
                mac-eth12: eth12  # This keyword is paired to ports: eth12: keyword
                mac-eth13: eth13  # This keyword is paired to ports: eth13: keyword
            # Each host has one network interface for each of these ports and
            # these port numbers represent the switch port number to which the host
            # interface is physically cabled.
            # To add or remove hosts for this node-template you add or remove
            # switch port numbers to these ports.
            ports:
                pxe:
                    _rack1:
                        - 1
                ipmi:
                    _rack1:
                        - 2
                eth10:          # switch one, 1st bond
                    _rack1:
                        - 4     # 1st node
                eth11:          # switch two, 1st bond
                    _rack1:
                        - 4
                eth12:          # switch one, 2nd bond
                    _rack1:
                        - 5
                eth13:          # switch two, 2nd bond
                    _rack1:
                        - 5
            networks:
                - _external1
                - _external2
                - _external3
                - _external4
                - _pxe-dhcp
                - _standalone-bond0
                - _standalone-bond1
        node-type2:
            hostname: radagast
            userid-ipmi: ADMIN
            password-ipmi: admin
            cobbler-profile: ubuntu-16.04.2-server-ppc64el
            os-disk: /dev/sdj
            name-interfaces:
                mac-pxe: eth15
                mac-eth10: eth10
                mac-eth11: eth11
                mac-eth12: eth12
                mac-eth13: eth13
            # Each host has one network interface for each of these ports and
            # these port numbers represent the switch port number to which the host
            # interface is physically cabled.
            # To add or remove hosts for this node-template you add or remove
            # switch port numbers to these ports.
            ports:
                pxe:
                    _rack1:
                        - 3
                        - 5
                ipmi:
                    _rack1:
                        - 4
                        - 6
                eth10:          # switch one, 1st bond
                    _rack1:
                        - 6     # 1st node
                        - 8     # 2nd node
                eth11:          # switch two, 1st bond
                    _rack1:
                        - 6
                        - 8
                eth12:          # switch one, 2nd bond
                    _rack1:
                        - 7
                        - 9
                eth13:          # switch two, 2nd bond
                    _rack1:
                        - 7
                        - 9
            networks:
                - _external1
                - _external2
                - _external3
                - _external4
                - _pxe-dhcp
                - _standalone-bond0
                - _standalone-bond1
