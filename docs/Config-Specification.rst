.. _config_file_spec:

Cluster Configuration File Specification
=========================================

**Specification Version: v2.0**

Genesis of the OpenPOWER Cloud Reference Cluster is controlled by the
'config.yml' file. This file is stored in YAML format. The definition of
the fields and the YAML file format are documented below.

Each section represents a top level dictionary key:

| `version:`_
| `globals:`_
| `location:`_
| `deployer:`_
| `switches:`_
| `interfaces:`_
| `networks:`_
| `node_templates:`_
| `software_bootstrap:`_

Additional key/value pairs are not processed by Cluster Genesis, but are
copied into the inventory.yml file and made available to post-Genesis
scripts and/or playbooks.

version:
---------

+-------------+------------------+--------------------------------------------------------------------------------------------------------------------------------------+----------+
| Element     | Example(s)       | Description                                                                                                                          | Required |
+=============+==================+======================================================================================================================================+==========+
|             |                  |                                                                                                                                      |          |
| ::          | ::               | Config file version.                                                                                                                 | **yes**  |
|             |                  |                                                                                                                                      |          |
|   version:  |   version: v2.0  |                                                                                                                                      |          |
|             |                  |    Release Branch   Supported Config File Version                                                                                    |          |
|             |                  |                                                                                                                                      |          |
|             |                  |    release-2.x           version: v2.0                                                                                               |          |
|             |                  |                                                                                                                                      |          |
|             |                  |    release-1.x           version: 1.1                                                                                                |          |
|             |                  |                                                                                                                                      |          |
|             |                  |    release-0.9           version: 1.0                                                                                                |          |
|             |                  |                                                                                                                                      |          |
|             |                  |                                                                                                                                      |          |
+-------------+------------------+--------------------------------------------------------------------------------------------------------------------------------------+----------+

globals:
--------

::

  globals:
      introspection:
      env_variables:
      switch_mode_mgmt:
      switch_mode_data:
      dhcp_lease_time:

+-----------------------------------+--------------------------------------------+--------------------------------------------------------------------------------------------+----------+
| Element                           | Example(s)                                 | Description                                                                                | Required |
+-----------------------------------+--------------------------------------------+--------------------------------------------------------------------------------------------+----------+
|                                   |                                            |                                                                                            |          |
| ::                                | ::                                         | Introspection shall be enabled. Evaluates to *false* if missing.                           | no       |
|                                   |                                            |                                                                                            |          |
|   globals:                        |   introspection: true                      |   | *false*                                                                                |          |
|      introspection:               |                                            |   | *true*                                                                                 |          |
|      ...                          |                                            |                                                                                            |          |
|                                   |                                            |                                                                                            |          |
+-----------------------------------+--------------------------------------------+--------------------------------------------------------------------------------------------+----------+
|                                   |                                            |                                                                                            |          |
| ::                                | ::                                         | Apply environmental variables to the shell.                                                | no       |
|                                   |                                            |                                                                                            |          |
|   globals:                        |   env_variables:                           | The example to the left would give the following result in bash:                           |          |
|      env_variables:               |       https_proxy: http://192.168.1.2:3128 |                                                                                            |          |
|      ...                          |       http_proxy: http://192.168.1.2:3128  | | export https_proxy="http://192.168.1.2:3128"                                             |          |
|                                   |       no_proxy: localhost,127.0.0.1        | | export http_proxy="http://192.168.1.2:3128"                                              |          |
|                                   |                                            | | export no_proxy="localhost,127.0.0.1"                                                    |          |
|                                   |                                            |                                                                                            |          |
|                                   |                                            |                                                                                            |          |
+-----------------------------------+--------------------------------------------+--------------------------------------------------------------------------------------------+----------+
|                                   |                                            |                                                                                            |          |
| ::                                | ::                                         | Sets Cluster Genesis management switch mode. Evaluates to *active* if missing.             | no       |
|                                   |                                            |                                                                                            |          |
|   globals:                        |   switch_mode_mgmt: active                 | | *passive*                                                                                |          |
|      switch_mode_mgmt:            |                                            | | *active*                                                                                 |          |
|      ...                          |                                            |                                                                                            |          |
|                                   |                                            |                                                                                            |          |
|                                   |                                            |                                                                                            |          |
+-----------------------------------+--------------------------------------------+--------------------------------------------------------------------------------------------+----------+
|                                   |                                            |                                                                                            |          |
| ::                                | ::                                         | Sets Cluster Genesis data switch mode. Evaluates to *active* if missing.                   | no       |
|                                   |                                            |                                                                                            |          |
|   globals:                        |   switch_mode_data: active                 | | *passive*                                                                                |          |
|      switch_mode_data:            |                                            | | *active*                                                                                 |          |
|      ...                          |                                            |                                                                                            |          |
|                                   |                                            |                                                                                            |          |
|                                   |                                            |                                                                                            |          |
+-----------------------------------+--------------------------------------------+--------------------------------------------------------------------------------------------+----------+
|                                   |                                            |                                                                                            |          |
| ::                                | ::                                         | Sets DHCP lease time given to client nodes. Value can be in seconds, minutes (e.g. "15m"), | no       |
|                                   |                                            | hours (e.g. "1h") or "infinite" (lease does not expire).                                   |          |
|   globals:                        |   dhcp_lease_time: 15m                     |                                                                                            |          |
|      dhcp_lease_time:             |                                            |                                                                                            |          |
|      ...                          | ::                                         |                                                                                            |          |
|                                   |                                            |                                                                                            |          |
|                                   |   dhcp_lease_time: 1h                      |                                                                                            |          |
|                                   |                                            |                                                                                            |          |
+-----------------------------------+--------------------------------------------+--------------------------------------------------------------------------------------------+----------+

location:
----------

::

  location:
      time_zone:
      data_center:
      racks:
          - label:
            room:
            row:
            cell:

+----------------------+-------------------------------+----------------------------------------------------------------------------------------------------------------+----------+
| Element              | Example(s)                    | Description                                                                                                    | Required |
+======================+===============================+================================================================================================================+==========+
|                      |                               |                                                                                                                |          |
| ::                   | ::                            | Cluster time zone in `tz database                                                                              | no       |
|                      |                               | <https://en.wikipedia.org/wiki/List_of_tz_database_time_zones>`_ format.                                       |          |
|   location:          |   time_zone: UTC              |                                                                                                                |          |
|       time_zone:     |                               |                                                                                                                |          |
|       ...            | ::                            |                                                                                                                |          |
|                      |                               |                                                                                                                |          |
|                      |   time_zone: America/Chicago  |                                                                                                                |          |
|                      |                               |                                                                                                                |          |
+----------------------+-------------------------------+----------------------------------------------------------------------------------------------------------------+----------+
|                      |                               |                                                                                                                |          |
| ::                   | ::                            | Data center name to be associated with cluster inventory.                                                      | no       |
|                      |                               |                                                                                                                |          |
|   location:          |   data_center: East Coast     |                                                                                                                |          |
|       data_center:   |                               |                                                                                                                |          |
|       ...            |                               |                                                                                                                |          |
|                      | ::                            |                                                                                                                |          |
|                      |                               |                                                                                                                |          |
|                      |   data_center: Austin, TX     |                                                                                                                |          |
|                      |                               |                                                                                                                |          |
+----------------------+-------------------------------+----------------------------------------------------------------------------------------------------------------+----------+
| .. _location_racks:  |                               |                                                                                                                |          |
|                      |                               |                                                                                                                |          |
| ::                   | ::                            | List of cluster racks.                                                                                         | **yes**  |
|                      |                               |                                                                                                                |          |
|   location:          |   racks:                      | | Required keys:                                                                                               |          |
|       racks:         |       - label: rack1          | |   *label* - Unique label used to reference this rack elsewhere in the config file.                           |          |
|           - label:   |         room: lab41           |                                                                                                                |          |
|             room:    |         row: 5                | | Optional keys:                                                                                               |          |
|             row:     |         cell: B               | |   *room*  - Physical room location of rack.                                                                  |          |
|             cell:    |       - label: rack2          | |   *row*   - Physical row location of rack.                                                                   |          |
|       ...            |         room: lab41           | |   *cell*  - Physical cell location of rack.                                                                  |          |
|                      |         row: 5                |                                                                                                                |          |
|                      |         cell: C               |                                                                                                                |          |
|                      |                               |                                                                                                                |          |
+----------------------+-------------------------------+----------------------------------------------------------------------------------------------------------------+----------+

deployer:
----------

::

  deployer:
      gateway:
      networks:
          mgmt:
              - device:
                interface_ipaddr:
                container_ipaddr:
                bridge_ipaddr:
                vlan:
                netmask:
                prefix:

          client:
              - type:
                device:
                container_ipaddr:
                bridge_ipaddr:
                vlan:
                netmask:
                prefix:

+-----------------------------------+--------------------------------------------+--------------------------------------------------------------------------------------------+----------+
| Element                           | Example(s)                                 | Description                                                                                | Required |
+-----------------------------------+--------------------------------------------+--------------------------------------------------------------------------------------------+----------+
|                                   |                                            |                                                                                            |          |
| ::                                | ::                                         | Deployer shall act as cluster gateway. Evaluates to *false* if missing.                    | no       |
|                                   |                                            |                                                                                            |          |
|   deployer:                       |   gateway: true                            |   | *false*                                                                                |          |
|      gateway:                     |                                            |   | *true*                                                                                 |          |
|      ...                          |                                            |                                                                                            |          |
|                                   |                                            | The deployer will be configured as the default gateway for all client nodes.               |          |
|                                   |                                            |                                                                                            |          |
|                                   |                                            | Configuration includes adding a 'MASQUERADE' rule to the deployer's 'iptables'             |          |
|                                   |                                            | NAT chain and setting the 'dnsmasq' DHCP service to serve the deployer's client            |          |
|                                   |                                            | management bridge address as the default gateway.                                          |          |
|                                   |                                            |                                                                                            |          |
|                                   |                                            | | Note: Specifying the 'gateway' explicitly on any of the data networks will override      |          |
|                                   |                                            | | this behaviour.                                                                          |          |
|                                   |                                            |                                                                                            |          |
+-----------------------------------+--------------------------------------------+--------------------------------------------------------------------------------------------+----------+
| .. _deployer_networks_mgmt:       |                                            |                                                                                            |          |
|                                   |                                            |                                                                                            |          |
| ::                                | ::                                         | Management network interface configuration.                                                | **yes**  |
|                                   |                                            |                                                                                            |          |
|   deployer:                       |   mgmt:                                    | | Required keys:                                                                           |          |
|       networks:                   |       - device: enp1s0f0                   | |   *device* - Management network interface device.                                        |          |
|           mgmt:                   |         interface_ipaddr: 192.168.1.2      |                                                                                            |          |
|               - device:           |         netmask: 255.255.255.0             | | Optional keys:                                                                           |          |
|                 interface_ipaddr: |       - device: enp1s0f0                   | |   *vlan* - Management network vlan (tagged).                                             |          |
|                 container_ipaddr: |         container_ipaddr: 192.168.5.2      |                                                                                            |          |
|                 bridge_ipaddr:    |         bridge_ipaddr: 192.168.5.3         | | IP address must be defined with:                                                         |          |
|                 vlan:             |         vlan: 5                            | |   *interface_ipaddr* - Management interface IP address (non-tagged).                     |          |
|                 netmask:          |         prefix: 24                         | |   --- or ---                                                                             |          |
|                 prefix:           |                                            | |   *container_ipaddr* - Container management interface IP address (tagged).               |          |
|           ...                     |                                            | |   *bridge_ipaddr*    - Deployer management bridge interface IP address (tagged).         |          |
|       ...                         |                                            |                                                                                            |          |
|                                   |                                            | | Subnet mask must be defined with:                                                        |          |
|                                   |                                            | |   *netmask* - Management network bitmask.                                                |          |
|                                   |                                            | |   --- or ---                                                                             |          |
|                                   |                                            | |   *prefix*  - Management network bit-length.                                             |          |
|                                   |                                            |                                                                                            |          |
+-----------------------------------+--------------------------------------------+--------------------------------------------------------------------------------------------+----------+
| .. _deployer_networks_client:     |                                            |                                                                                            |          |
|                                   |                                            |                                                                                            |          |
| ::                                | ::                                         | Client node BMC (IPMI) and OS (PXE) network interface configuration. Ansible               | **yes**  |
|                                   |                                            | communicates with clients using this network during "post deploy" operations.              |          |
|   deployer:                       |   client:                                  |                                                                                            |          |
|       networks:                   |       - type: ipmi                         | | Required keys:                                                                           |          |
|           client:                 |         device: enp1s0f0                   | |   *type*             - IPMI or PXE network (ipmi/pxe).                                   |          |
|               - type:             |         container_ipaddr: 192.168.10.2     | |   *device*           - Management network interface device.                              |          |
|                 device:           |         bridge_ipaddr: 192.168.10.3        | |   *container_ipaddr* - Container management interface IP address.                        |          |
|                 container_ipaddr: |         vlan: 10                           | |   *bridge_ipaddr*    - Deployer management bridge interface IP address.                  |          |
|                 bridge_ipaddr:    |         netmask: 255.255.255.0             | |   *vlan*             - Management network vlan.                                          |          |
|                 vlan:             |       - type: pxe                          |                                                                                            |          |
|                 netmask:          |         device: enp1s0f0                   | | Subnet mask must be defined with:                                                        |          |
|                 prefix:           |         container_ipaddr: 192.168.20.2     | |   *netmask* - Management network bitmask.                                                |          |
|                                   |         bridge_ipaddr: 192.168.20.3        | |   --- or ---                                                                             |          |
|                                   |         vlan: 20                           | |   *prefix*  - Management network bit-length.                                             |          |
|                                   |         prefix: 24                         |                                                                                            |          |
|                                   |                                            |                                                                                            |          |
+-----------------------------------+--------------------------------------------+--------------------------------------------------------------------------------------------+----------+

switches:
----------

::

    switches:
        mgmt:
            - label:
              hostname:
              userid:
              password:
              ssh_key:
              class:
              rack_id:
              rack_eia:
              interfaces:
                  - type:
                    ipaddr:
                    vlan:
                    port:
              links:
                  - target:
                    ipaddr:
                    vip:
                    netmask:
                    prefix:
                    ports:
        data:
            - label:
              hostname:
              userid:
              password:
              ssh_key:
              class:
              rack_id:
              rack_eia:
              interfaces:
                  - type:
                    ipaddr:
                    vlan:
                    port:
              links:
                  - target:
                    ipaddr:
                    vip:
                    netmask:
                    prefix:
                    ports:

+---------------------------------+---------------------------------------+---------------------------------------------------------------------------------------------+----------+
| Element                         | Example(s)                            | Description                                                                                 | Required |
+=================================+=======================================+=============================================================================================+==========+
| .. _switches_mgmt:              |                                       |                                                                                             |          |
|                                 |                                       |                                                                                             |          |
| ::                              | ::                                    | Management switch configuration. Each physical switch is defined as an                      | **yes**  |
|                                 |                                       | item in the *mgmt:* list.                                                                   |          |
|   switches:                     |   mgmt:                               |                                                                                             |          |
|       mgmt:                     |       - label: mgmt_switch            | | Required keys:                                                                            |          |
|           - label:              |         hostname: switch23423         | |   *label*  - Unique label used to reference this switch elsewhere in the config file.     |          |
|             hostname:           |         userid: admin                 |                                                                                             |          |
|             userid:             |         password: abc123              | | Required keys in "active" switch mode:                                                    |          |
|             password:           |         class: lenovo                 | |   *userid*        - Userid for switch management account.                                 |          |
|             class:              |         rack_id: rack1                | |   *password* [1]_ - Plain text password associated with *userid*.                         |          |
|             rack_id:            |         rack_eia: 20                  | |   *ssh_key*  [1]_ - Path to SSH private key file associated with *userid*.                |          |
|             rack_eia:           |         interfaces:                   |                                                                                             |          |
|             interfaces:         |             - type: outband           | | Required keys in "passive" switch mode:                                                   |          |
|                 - type:         |               ipaddr: 192.168.1.10    | |   *class*  - Switch class (lenovo/mellanox/cisco/cumulus).                                |          |
|                   ipaddr:       |               port: mgmt0             |                                                                                             |          |
|                   vlan:         |             - type: inband            | | Optional keys:                                                                            |          |
|                   port:         |               ipaddr: 192.168.5.20    | |   *hostname* - Hostname associated with switch management network interface.              |          |
|             links:              |               port: 15                | |   *rack_id*  - Reference to rack *label* defined in the                                   |          |
|                 - target:       |         links:                        |                  `locations: racks:= <location_racks_>`_ element.                           |          |
|                   ports:        |             - target: deployer        | |   *rack_eia* - Switch position within rack.                                               |          |
|       ...                       |               ports: 1                | |   *interfaces* - See interfaces_.                                                         |          |
|                                 |             - target: data_switch     | |   *links*    - See links_.                                                                |          |
|                                 |               ports: 2                |                                                                                             |          |
|                                 |                                       | .. [1] Either *password* or *ssh_key* shall be specified, but not both.                     |          |
|                                 |                                       |                                                                                             |          |
+---------------------------------+---------------------------------------+---------------------------------------------------------------------------------------------+----------+
| .. _switches_data:              |                                       |                                                                                             |          |
|                                 |                                       |                                                                                             |          |
| ::                              | example #1::                          | Data switch configuration. Each physical switch is defined as an item in the                | **yes**  |
|                                 |                                       | *data:* list.                                                                               |          |
|   switches:                     |   data:                               | Key/value specs are identical to `mgmt switches <switches_mgmt_>`_.                         |          |
|       data:                     |       - label: data_switch_1          |                                                                                             |          |
|           - label:              |         hostname: switch84579         |                                                                                             |          |
|             hostname:           |         userid: admin                 |                                                                                             |          |
|             userid:             |         password: abc123              |                                                                                             |          |
|             password:           |         class: mellanox               |                                                                                             |          |
|             class:              |         rack_id: rack1                |                                                                                             |          |
|             rack_id:            |         rack_eia: 21                  |                                                                                             |          |
|             rack_eia:           |         interfaces:                   |                                                                                             |          |
|             interfaces:         |             - type: inband            |                                                                                             |          |
|                 - type:         |               ipaddr: 192.168.1.21    |                                                                                             |          |
|                   ipaddr:       |               port: 15                |                                                                                             |          |
|                   vlan:         |         links:                        |                                                                                             |          |
|                   port:         |             - target: mgmt_switch     |                                                                                             |          |
|             links:              |               ports: 1                |                                                                                             |          |
|                 - target:       |             - target: data_switch_2   |                                                                                             |          |
|                   ports:        |               ports: 2                |                                                                                             |          |
|       ...                       |                                       |                                                                                             |          |
|                                 | example #2::                          |                                                                                             |          |
|                                 |                                       |                                                                                             |          |
|                                 |   data:                               |                                                                                             |          |
|                                 |       - label: data_switch            |                                                                                             |          |
|                                 |         hostname: switch84579         |                                                                                             |          |
|                                 |         userid: admin                 |                                                                                             |          |
|                                 |         password: abc123              |                                                                                             |          |
|                                 |         rack_id: rack1                |                                                                                             |          |
|                                 |         rack_eia: 21                  |                                                                                             |          |
|                                 |         interfaces:                   |                                                                                             |          |
|                                 |             - type: outband           |                                                                                             |          |
|                                 |               ipaddr: 192.168.1.21    |                                                                                             |          |
|                                 |               port: mgmt0             |                                                                                             |          |
|                                 |         links:                        |                                                                                             |          |
|                                 |             - target: mgmt_switch     |                                                                                             |          |
|                                 |               ports: mgmt0            |                                                                                             |          |
|                                 |                                       |                                                                                             |          |
+---------------------------------+---------------------------------------+---------------------------------------------------------------------------------------------+----------+
| .. _interfaces:                 |                                       |                                                                                             |          |
|                                 |                                       |                                                                                             |          |
| ::                              | example #1::                          | Switch interface configuration.                                                             | no       |
|                                 |                                       |                                                                                             |          |
|   switches:                     |   interfaces:                         | | Required keys:                                                                            |          |
|       mgmt:                     |       - type: outband                 | |   *type*   - In-Band or Out-of-Band (inband/outband).                                     |          |
|           - ...                 |         ipaddr: 192.168.1.20          | |   *ipaddr* - IP address.                                                                  |          |
|             interfaces:         |         port: mgmt0                   |                                                                                             |          |
|                 - type:         |                                       | | Optional keys:                                                                            |          |
|                   ipaddr:       | example #2::                          | |   *vlan*   - VLAN.                                                                        |          |
|                   port:         |                                       | |   *port*   - Port.                                                                        |          |
|       data:                     |   interfaces:                         |                                                                                             |          |
|           - ...                 |       - type: inband                  | | Subnet mask may be defined with:                                                          |          |
|             interfaces:         |         ipaddr: 192.168.5.20          | |   *netmask* - Management network bitmask.                                                 |          |
|                 - type:         |         netmask: 255.255.255.0        | |   --- or ---                                                                              |          |
|                   ipaddr:       |         port: 15                      | |   *prefix*  - Management network bit-length.                                              |          |
|                   port:         |                                       |                                                                                             |          |
|                                 |                                       |                                                                                             |          |
+---------------------------------+---------------------------------------+---------------------------------------------------------------------------------------------+----------+
| .. _links:                      |                                       |                                                                                             |          |
|                                 |                                       |                                                                                             |          |
| ::                              | example #1::                          | Switch link configuration. Links can be configured between any switches and/or              | no       |
|                                 |                                       | the deployer.                                                                               |          |
|   switches:                     |   mgmt:                               |                                                                                             |          |
|       mgmt:                     |       - label: mgmt_switch            | | Required keys:                                                                            |          |
|           - ...                 |         ...                           | |   *target* - Reference to destination target. This value must be set to 'deployer'        |          |
|             links:              |         interfaces:                   |                or correspond to another switch's *label* (switches_mgmt_, switches_data_).  |          |
|                 - target:       |             - type: inband            | |   *ports*   - Source port numbers (not target ports!). This can either be a single        |          |
|                   ports:        |               ipaddr: 192.168.5.10    |                 port or a list of ports. If a list is given then the links will be          |          |
|       data:                     |               port: 15                |                 aggregated.                                                                 |          |
|           - ...                 |         links:                        | | Optional keys:                                                                            |          |
|             links:              |             - target: deployer        | |   *ipaddr* - Management interface IP address.                                             |          |
|                 - target:       |               ports: 10               | |   *vlan*   - Management interface vlan.                                                   |          |
|                   port:         |             - target: data_switch     | |   *vip*    - Virtual IP used for redundant switch configurations.                         |          |
|           - ...                 |               ports: 11               |                                                                                             |          |
|             links:              |   data:                               | | Subnet mask must be defined with:                                                         |          |
|                 - target:       |       - label: data_switch            | |   *netmask* - Management network bitmask.                                                 |          |
|                   ipaddr:       |         ...                           | |   --- or ---                                                                              |          |
|                   vip:          |         interfaces:                   | |   *prefix*  - Management network bit-length.                                              |          |
|                   netmask:      |             - type: outband           |                                                                                             |          |
|                   vlan:         |               ipaddr: 192.168.5.10    | In example #1 port 10 of "mgmt_switch" is cabled directly to the deployer and port 11       |          |
|                   ports:        |               vlan: 5                 | of "mgmt_switch" is cabled to the mangement port 0 of "data_switch". An inband              |          |
|                                 |               port: mgmt0             | management interface is configured with an IP address of '192.168.5.10' for                 |          |
|                                 |         links:                        | "mgmt_switch", and the dedicated management port 0 of "data_switch" is configured           |          |
|                                 |             - target: mgmt_switch     | with an IP address of "192.168.5.11" on vlan "5".                                           |          |
|                                 |               ports: mgmt0            |                                                                                             |          |
|                                 |                                       | In example #2 a redundant data switch configuration is shown. Ports 7 and 8 (on both        |          |
|                                 | example #2::                          | switches) are configured as an aggrated peer link on vlan "4000" with IP address of         |          |
|                                 |                                       | "10.0.0.1/24" and "10.0.0.2/24".                                                            |          |
|                                 |   data:                               |                                                                                             |          |
|                                 |       - label: data_1                 |                                                                                             |          |
|                                 |         ...                           |                                                                                             |          |
|                                 |         links:                        |                                                                                             |          |
|                                 |             - target: mgmt            |                                                                                             |          |
|                                 |               ipaddr: 192.168.5.31    |                                                                                             |          |
|                                 |               vip: 192.168.5.254      |                                                                                             |          |
|                                 |               ports: mgmt0            |                                                                                             |          |
|                                 |             - target: data_2          |                                                                                             |          |
|                                 |               ipaddr: 10.0.0.1        |                                                                                             |          |
|                                 |               netmask: 255.255.255.0  |                                                                                             |          |
|                                 |               vlan: 4000              |                                                                                             |          |
|                                 |               ports:                  |                                                                                             |          |
|                                 |                   - 7                 |                                                                                             |          |
|                                 |                   - 8                 |                                                                                             |          |
|                                 |       - label: data_2                 |                                                                                             |          |
|                                 |         links:                        |                                                                                             |          |
|                                 |             - target: mgmt            |                                                                                             |          |
|                                 |               ipaddr: 192.168.5.32    |                                                                                             |          |
|                                 |               vip: 192.168.5.254      |                                                                                             |          |
|                                 |               ports: mgmt0            |                                                                                             |          |
|                                 |             - target: data_2          |                                                                                             |          |
|                                 |               ipaddr: 10.0.0.2        |                                                                                             |          |
|                                 |               network: 255.255.255.0  |                                                                                             |          |
|                                 |               vlan: 4000              |                                                                                             |          |
|                                 |               ports:                  |                                                                                             |          |
|                                 |                   - 7                 |                                                                                             |          |
|                                 |                   - 8                 |                                                                                             |          |
|                                 |                                       |                                                                                             |          |
+---------------------------------+---------------------------------------+---------------------------------------------------------------------------------------------+----------+


interfaces:
------------

::

    interfaces:
        - label:
          description:
          iface:
          method:
          address_list:
          netmask:
          broadcast:
          gateway:
          dns_search:
          dns_nameservers:
          mtu:
          pre_up:
          vlan_raw_device:
        - label:
          description:
          DEVICE:
          BOOTPROTO:
          ONBOOT
          ONPARENT
          MASTER
          SLAVE
          BONDING_MASTER
          IPADDR_list:
          NETMASK:
          BROADCAST:
          GATEWAY:
          SEARCH:
          DNS1:
          DNS2:
          MTU:
          VLAN:

+---------------------------+---------------------------------------------------+--------------------------------------------------------------------------------------------+----------+
| Element                   | Example(s)                                        | Description                                                                                | Required |
+===========================+===================================================+============================================================================================+==========+
|                           |                                                   |                                                                                            |          |
| ::                        |                                                   | List of OS interface configuration definitions. Each definition can be formatted           | no       |
|                           |                                                   | for either `Ubuntu <interfaces_ubuntu_>`_ or `RHEL <interfaces_rhel_>`_.                   |          |
|   interfaces:             |                                                   |                                                                                            |          |
|       - ...               |                                                   |                                                                                            |          |
|       - ...               |                                                   |                                                                                            |          |
|                           |                                                   |                                                                                            |          |
+---------------------------+---------------------------------------------------+--------------------------------------------------------------------------------------------+----------+
| .. _interfaces_ubuntu:    |                                                   |                                                                                            |          |
|                           |                                                   |                                                                                            |          |
| ::                        | ::                                                | Ubuntu formatted OS interface configuration.                                               | no       |
|                           |                                                   |                                                                                            |          |
|   interfaces:             |   - label: manual1                                | | Required keys:                                                                           |          |
|       - label:            |     description: manual network 1                 | |   *label* - Unique label of interface configuration to be referenced within              |          |
|         description:      |     iface: eth0                                   |               `networks:`_ `node_templates: interfaces: <node_templates_interfaces_>`_.    |          |
|         iface:            |     method: manual                                |                                                                                            |          |
|         method:           |                                                   | | Optional keys:                                                                           |          |
|         address_list:     |   - label: dhcp1                                  | |   *description*   - Short description of interface configuration to be included          |          |
|         netmask:          |     description: dhcp interface 1                 |                       as a comment in OS config files.                                     |          |
|         broadcast:        |     iface: eth0                                   | |   *address_list*  - List of IP address to assign client interfaces referencing this      |          |
|         gateway:          |     method: dhcp                                  |                       configuration. Each list element may either be a single IP           |          |
|         dns_search:       |                                                   |                       address or a range (formatted as *<start_address>*-<*end_address*>). |          |
|         dns_nameservers:  |   - label: static1                                | |   *address_start* - Starting IP address to assign client interfaces referencing          |          |
|         mtu:              |     description: static interface 1               |                       this configuration. Addresses will be assigned to each client        |          |
|         pre_up:           |     iface: eth0                                   |                       interface incrementally.                                             |          |
|         vlan_raw_device:  |     method: static                                |                                                                                            |          |
|                           |     address_list:                                 | | Optional "drop-in" keys:                                                                 |          |
|                           |         - 9.3.89.14                               | |   The following key names are derived directly from the Ubuntu *interfaces*              |          |
|                           |         - 9.3.89.18-9.3.89.22                     |     configuration file (note that all "-" charactes are replaced with "_"). Values         |          |
|                           |         - 9.3.89.111-9.3.89.112                   |     will be copied directly into the *interfaces* file. Refer to the `interfaces`          |          |
|                           |         - 9.3.89.120                              |     `manpage <http://manpages.ubuntu.com/manpages/xenial/man5/interfaces.5.html>`_         |          |
|                           |     netmask: 255.255.255.0                        | |                                                                                          |          |
|                           |     broadcast: 9.3.89.255                         | |   *iface*                                                                                |          |
|                           |     gateway: 9.3.89.1                             | |   *method*                                                                               |          |
|                           |     dns_search: your.dns.com                      | |   *netmask*                                                                              |          |
|                           |     dns_nameservers: 9.3.1.200 9.3.1.201          | |   *broadcast*                                                                            |          |
|                           |     mtu: 9000                                     | |   *gateway*                                                                              |          |
|                           |     pre_up: command                               | |   *dns_search*                                                                           |          |
|                           |                                                   | |   *dns_nameservers*                                                                      |          |
|                           |   - label: vlan1                                  | |   *mtu*                                                                                  |          |
|                           |     description: vlan interface 1                 | |   *pre_up*                                                                               |          |
|                           |     iface: eth0.10                                | |   *vlan_raw_device*                                                                      |          |
|                           |     method: manual                                |                                                                                            |          |
|                           |                                                   | .. _interfaces_ubuntu_rename_notes:                                                        |          |
|                           |   - label: vlan2                                  |                                                                                            |          |
|                           |     description: vlan interface 2                 |                                                                                            |          |
|                           |     iface: myvlan.20                              |                                                                                            |          |
|                           |     method: manual                                | | Notes:                                                                                   |          |
|                           |     vlan_raw_device: eth0                         | |   If 'rename: true' in                                                                   |          |
|                           |                                                   |     `node_templates: physical_interfaces: pxe/data <physical_ints_os_>`_ then the          |          |
|                           |   - label: bridge1                                |     *iface* value will be used to rename the interface.                                    |          |
|                           |     description: bridge interface 1               | |                                                                                          |          |
|                           |     iface: br1                                    | |   If 'rename: false' in                                                                  |          |
|                           |     method: static                                |     `node_templates: physical_interfaces: pxe/data <physical_ints_os_>`_ then the          |          |
|                           |     address_start: 10.0.0.100                     |     *iface* value will be ignored and the interface name assigned by the OS will be        |          |
|                           |     netmask: 255.255.255.0                        |     used. If the iface value is referenced in any other interface definition it will       |          |
|                           |     bridge_ports: eth0                            |     also be replaced.                                                                      |          |
|                           |     bridge_fd: 9                                  |                                                                                            |          |
|                           |     bridge_hello: 2                               |                                                                                            |          |
|                           |     bridge_maxage: 12                             |                                                                                            |          |
|                           |     bridge_stp: off                               |                                                                                            |          |
|                           |                                                   |                                                                                            |          |
|                           |   - label: bond1_interface0                       |                                                                                            |          |
|                           |     description: primary interface for bond 1     |                                                                                            |          |
|                           |     iface: eth0                                   |                                                                                            |          |
|                           |     method: manual                                |                                                                                            |          |
|                           |     bond_master: bond1                            |                                                                                            |          |
|                           |     bond_primary: eth0                            |                                                                                            |          |
|                           |                                                   |                                                                                            |          |
|                           |   - label: bond1_interface1                       |                                                                                            |          |
|                           |     description: secondary interface for bond 1   |                                                                                            |          |
|                           |     iface: eth1                                   |                                                                                            |          |
|                           |     method: manual                                |                                                                                            |          |
|                           |     bond_master: bond1                            |                                                                                            |          |
|                           |                                                   |                                                                                            |          |
|                           |   - label: bond1                                  |                                                                                            |          |
|                           |     description: bond interface 1                 |                                                                                            |          |
|                           |     iface: bond1                                  |                                                                                            |          |
|                           |     address_start: 192.168.1.10                   |                                                                                            |          |
|                           |     netmask: 255.255.255.0                        |                                                                                            |          |
|                           |     bond_mode: active-backup                      |                                                                                            |          |
|                           |     bond_miimon: 100                              |                                                                                            |          |
|                           |     bond_slaves: none                             |                                                                                            |          |
|                           |                                                   |                                                                                            |          |
|                           |   - label: osbond0_interface0                     |                                                                                            |          |
|                           |     description: primary interface for osbond0    |                                                                                            |          |
|                           |     iface: eth0                                   |                                                                                            |          |
|                           |     method: manual                                |                                                                                            |          |
|                           |     bond_master: osbond0                          |                                                                                            |          |
|                           |     bond_primary: eth0                            |                                                                                            |          |
|                           |                                                   |                                                                                            |          |
|                           |   - label: osbond0_interface1                     |                                                                                            |          |
|                           |     description: secondary interface for osbond0  |                                                                                            |          |
|                           |     iface: eth1                                   |                                                                                            |          |
|                           |     method: manual                                |                                                                                            |          |
|                           |     bond_master: osbond0                          |                                                                                            |          |
|                           |                                                   |                                                                                            |          |
|                           |   - label: osbond0                                |                                                                                            |          |
|                           |     description: bond interface                   |                                                                                            |          |
|                           |     iface: osbond0                                |                                                                                            |          |
|                           |     address_start: 192.168.1.10                   |                                                                                            |          |
|                           |     netmask: 255.255.255.0                        |                                                                                            |          |
|                           |     bond_mode: active-backup                      |                                                                                            |          |
|                           |     bond_miimon: 100                              |                                                                                            |          |
|                           |     bond_slaves: none                             |                                                                                            |          |
|                           |                                                   |                                                                                            |          |
|                           |   - label: osbond0_vlan10                         |                                                                                            |          |
|                           |     description: vlan interface 1                 |                                                                                            |          |
|                           |     iface: osbond0.10                             |                                                                                            |          |
|                           |     method: manual                                |                                                                                            |          |
|                           |                                                   |                                                                                            |          |
|                           |   - label: bridge10                               |                                                                                            |          |
|                           |     description: bridge interface for vlan10      |                                                                                            |          |
|                           |     iface: br10                                   |                                                                                            |          |
|                           |     method: static                                |                                                                                            |          |
|                           |     address_start: 10.0.10.100                    |                                                                                            |          |
|                           |     netmask: 255.255.255.0                        |                                                                                            |          |
|                           |     bridge_ports: osbond0.10                      |                                                                                            |          |
|                           |     bridge_stp: off                               |                                                                                            |          |
|                           |                                                   |                                                                                            |          |
|                           |   - label: osbond0_vlan20                         |                                                                                            |          |
|                           |     description: vlan interface 2                 |                                                                                            |          |
|                           |     iface: osbond0.20                             |                                                                                            |          |
|                           |     method: manual                                |                                                                                            |          |
|                           |                                                   |                                                                                            |          |
|                           |   - label: bridge20                               |                                                                                            |          |
|                           |     description: bridge interface for vlan20      |                                                                                            |          |
|                           |     iface: br20                                   |                                                                                            |          |
|                           |     method: static                                |                                                                                            |          |
|                           |     address_start: 10.0.20.100                    |                                                                                            |          |
|                           |     netmask: 255.255.255.0                        |                                                                                            |          |
|                           |     bridge_ports: osbond0.20                      |                                                                                            |          |
|                           |     bridge_stp: off                               |                                                                                            |          |
|                           |                                                   |                                                                                            |          |
+---------------------------+---------------------------------------------------+--------------------------------------------------------------------------------------------+----------+
| .. _interfaces_rhel:      |                                                   |                                                                                            |          |
|                           |                                                   |                                                                                            |          |
| ::                        | ::                                                | Red Hat formatted OS interface configuration.                                              | no       |
|                           |                                                   |                                                                                            |          |
|   interfaces:             |   - label: manual2                                | | Required keys:                                                                           |          |
|       - label:            |     description: manual network 2                 | |   *label* - Unique label of interface configuration to be referenced within              |          |
|         description:      |     DEVICE: eth0                                  |               `networks:`_ `node_templates: interfaces: <node_templates_interfaces_>`_.    |          |
|         DEVICE:           |     TYPE: Ethernet                                |                                                                                            |          |
|         TYPE:             |     BOOTPROTO: none                               | | Optional keys:                                                                           |          |
|         BOOTPROTO:        |     ONBOOT: yes                                   | |   *description*  - Short description of interface configuration to be included as        |          |
|         ONBOOT            |     NM_CONTROLLED: no                             |                      a comment in OS config files.                                         |          |
|         ONPARENT:         |                                                   | |   *IPADDR_list*  - List of IP address to assign client interfaces referencing this       |          |
|         MASTER:           |   - label: dhcp2                                  |                      configuration. Each list element may either be a single IP            |          |
|         SLAVE:            |     description: dhcp interface 2                 |                      address or a range (formatted as *<start_address>*-<*end_address*>).  |          |
|         BONDING_MASTER:   |     DEVICE: eth0                                  | |   *IPADDR_start* - Starting IP address to assign client interfaces referencing this      |          |
|         IPADDR_list:      |     TYPE: Ethernet                                |                      configuration. Addresses will be assigned to each client              |          |
|         NETMASK:          |     BOOTPROTO: dhcp                               |                      interface incrementally.                                              |          |
|         BROADCAST:        |     ONBOOT: yes                                   |                                                                                            |          |
|         GATEWAY:          |     NM_CONTROLLED: no                             | | Optional "drop-in" keys:                                                                 |          |
|         SEARCH:           |                                                   | |   The following key names are derived directly from RHEL's *ifcfg* configuration         |          |
|         DNS1:             |   - label: static2                                |     files. Values will be copied directly into the *ifcfg-<name>* files.  Refer to         |          |
|         DNS2:             |     description: static interface 2               |     the `RHEL IP NETWORKING <rhel_ifcfg_doc_>`_ for usage.                                 |          |
|         MTU:              |     DEVICE: eth0                                  | |                                                                                          |          |
|         VLAN:             |     TYPE: Ethernet                                | |   *DEVICE*                                                                               |          |
|         NM_CONTROLLED:    |     BOOTPROTO: none                               | |   *TYPE*                                                                                 |          |
|                           |     ONBOOT: yes                                   | |   *BOOTPROTO*                                                                            |          |
|                           |     IPADDR_list:                                  | |   *ONBOOT*                                                                               |          |
|                           |         - 9.3.89.14                               | |   *ONPARENT*                                                                             |          |
|                           |         - 9.3.89.18-9.3.89.22                     | |   *MASTER*                                                                               |          |
|                           |         - 9.3.89.111-9.3.89.112                   | |   *SLAVE*                                                                                |          |
|                           |         - 9.3.89.120                              | |   *BONDING_MASTER*                                                                       |          |
|                           |     NETMASK: 255.255.255.0                        | |   *NETMASK*                                                                              |          |
|                           |     BROADCAST: 9.3.89.255                         | |   *BROADCAST*                                                                            |          |
|                           |     GATEWAY: 9.3.89.1                             | |   *GATEWAY*                                                                              |          |
|                           |     SEARCH: your.dns.com                          | |   *SEARCH*                                                                               |          |
|                           |     DNS1: 9.3.1.200                               | |   *DNS1*                                                                                 |          |
|                           |     DNS2: 9.3.1.201                               | |   *DNS2*                                                                                 |          |
|                           |     MTU: 9000                                     | |   *MTU*                                                                                  |          |
|                           |     NM_CONTROLLED: no                             | |   *VLAN*                                                                                 |          |
|                           |                                                   | |   *NM_CONTROLLED*                                                                        |          |
|                           |   - label: vlan3                                  |                                                                                            |          |
|                           |     description: vlan interface 3                 | .. _interfaces_rhel_rename_notes:                                                          |          |
|                           |     DEVICE: eth0.10                               |                                                                                            |          |
|                           |     BOOTPROTO: none                               | | Notes:                                                                                   |          |
|                           |     ONBOOT: yes                                   | |   If 'rename: true' in                                                                   |          |
|                           |     ONPARENT: yes                                 |     `node_templates: physical_interfaces: pxe/data <physical_ints_os_>`_ then the          |          |
|                           |     VLAN: yes                                     |     *DEVICE* value will be used to rename the interface.                                   |          |
|                           |     NM_CONTROLLED: no                             | |                                                                                          |          |
|                           |                                                   | |   If 'rename: false' in                                                                  |          |
|                           |   - label: bridge2                                |     `node_templates: physical_interfaces: pxe/data <physical_ints_os_>`_ then the          |          |
|                           |     description: bridge interface 2               |     *DEVICE* value will be replaced by the interface name assigned by the OS. If the       |          |
|                           |     DEVICE: br2                                   |     *DEVICE* value is referenced in **any** other interface definition it will also        |          |
|                           |     TYPE: Bridge                                  |     be replaced.                                                                           |          |
|                           |     BOOTPROTO: static                             |                                                                                            |          |
|                           |     ONBOOT: yes                                   |                                                                                            |          |
|                           |     IPADDR_start: 10.0.0.100                      |                                                                                            |          |
|                           |     NETMASK: 255.255.255.0                        |                                                                                            |          |
|                           |     STP: off                                      |                                                                                            |          |
|                           |     NM_CONTROLLED: no                             |                                                                                            |          |
|                           |                                                   |                                                                                            |          |
|                           |   - label: bridge2_port                           |                                                                                            |          |
|                           |     description: port for bridge if 2             |                                                                                            |          |
|                           |     DEVICE: tap_br2                               |                                                                                            |          |
|                           |     TYPE: Ethernet                                |                                                                                            |          |
|                           |     BOOTPROTO: none                               |                                                                                            |          |
|                           |     ONBOOT: yes                                   |                                                                                            |          |
|                           |     BRIDGE: br2                                   |                                                                                            |          |
|                           |     NM_CONTROLLED: no                             |                                                                                            |          |
|                           |                                                   |                                                                                            |          |
|                           |   - label: bond2_interface0                       |                                                                                            |          |
|                           |     description: primary interface for bond 2     |                                                                                            |          |
|                           |     DEVICE: eth0                                  |                                                                                            |          |
|                           |     TYPE: Ethernet                                |                                                                                            |          |
|                           |     BOOTPROTO: manual                             |                                                                                            |          |
|                           |     ONBOOT: yes                                   |                                                                                            |          |
|                           |     MASTER: bond2                                 |                                                                                            |          |
|                           |     SLAVE: yes                                    |                                                                                            |          |
|                           |     NM_CONTROLLED: no                             |                                                                                            |          |
|                           |                                                   |                                                                                            |          |
|                           |   - label: bond2_interface1                       |                                                                                            |          |
|                           |     description: secondary interface for bond 2   |                                                                                            |          |
|                           |     DEVICE: eth1                                  |                                                                                            |          |
|                           |     TYPE: Ethernet                                |                                                                                            |          |
|                           |     BOOTPROTO: manual                             |                                                                                            |          |
|                           |     ONBOOT: yes                                   |                                                                                            |          |
|                           |     MASTER: bond2                                 |                                                                                            |          |
|                           |     SLAVE: yes                                    |                                                                                            |          |
|                           |     NM_CONTROLLED: no                             |                                                                                            |          |
|                           |                                                   |                                                                                            |          |
|                           |   - label: bond2                                  |                                                                                            |          |
|                           |     description: bond interface 2                 |                                                                                            |          |
|                           |     DEVICE: bond2                                 |                                                                                            |          |
|                           |     TYPE: Bond                                    |                                                                                            |          |
|                           |     BONDING_MASTER: yes                           |                                                                                            |          |
|                           |     IPADDR_start: 192.168.1.10                    |                                                                                            |          |
|                           |     NETMASK: 255.255.255.0                        |                                                                                            |          |
|                           |     ONBOOT: yes                                   |                                                                                            |          |
|                           |     BOOTPROTO: none                               |                                                                                            |          |
|                           |     BONDING_OPTS: "mode=active-backup miimon=100" |                                                                                            |          |
|                           |     NM_CONTROLLED: no                             |                                                                                            |          |
|                           |                                                   |                                                                                            |          |
+---------------------------+---------------------------------------------------+--------------------------------------------------------------------------------------------+----------+

.. _rhel_ifcfg_doc: https://access.redhat.com/documentation/en-US/Red_Hat_Enterprise_Linux/7/html/Networking_Guide/sec-Editing_Network_Configuration_Files.html#sec-Configuring_a_Network_Interface_Using_ifcg_Files

networks:
----------

::

    networks:
        - label:
          interfaces:

+----------------------+--------------------------+---------------------------------------------------------------------------------------------------------------------+----------+
| Element              | Example(s)               | Description                                                                                                         | Required |
+======================+==========================+=====================================================================================================================+==========+
|                      |                          |                                                                                                                     |          |
| ::                   | ::                       | The 'networks' list defines groups of interfaces. These groups can be assigned to items in the `node_templates:`_   | no       |
|                      |                          | list.                                                                                                               |          |
|   networks:          |   interfaces:            |                                                                                                                     |          |
|       - label:       |       - label: example1  | | Required keys:                                                                                                    |          |
|         interfaces:  |         ...              | |   *label*      - Unique label of network group to be referenced within a `node_templates:`_ item's 'networks:'    |          |
|                      |       - label: example2  |                    value.                                                                                           |          |
|                      |         ...              | |   *interfaces* - List of interfaces assigned to the group.                                                        |          |
|                      |       - label: example3  |                                                                                                                     |          |
|                      |         ...              |                                                                                                                     |          |
|                      |   networks:              |                                                                                                                     |          |
|                      |       - label: all_nets  |                                                                                                                     |          |
|                      |         interfaces:      |                                                                                                                     |          |
|                      |             - example1   |                                                                                                                     |          |
|                      |             - example2   |                                                                                                                     |          |
|                      |             - example3   |                                                                                                                     |          |
|                      |       - label: group1    |                                                                                                                     |          |
|                      |         interfaces:      |                                                                                                                     |          |
|                      |             - example1   |                                                                                                                     |          |
|                      |             - example2   |                                                                                                                     |          |
|                      |       - label: group2    |                                                                                                                     |          |
|                      |         interfaces:      |                                                                                                                     |          |
|                      |             - example1   |                                                                                                                     |          |
|                      |             - example3   |                                                                                                                     |          |
|                      |                          |                                                                                                                     |          |
+----------------------+--------------------------+---------------------------------------------------------------------------------------------------------------------+----------+


node_templates:
----------------

::

    node_templates:
        - label:
          ipmi:
              userid:
              password:
          os:
              hostname_prefix:
              domain:
              profile:
              install_device:
              users:
                  - name:
                    password:
              groups:
                  - name:
              kernel_options:
          physical_interfaces:
              ipmi:
                  - switch:
                    ports:
              pxe:
                  - switch:
                    interface:
                    rename:
                    ports:
              data:
                  - switch:
                    interface:
                    rename:
                    ports:
          interfaces:
          networks:
          roles:

+------------------------------------+-----------------------------------------------+----------------------------------------------------------------------------------+----------+
| Element                            | Example(s)                                    | Description                                                                      | Required |
+====================================+===============================================+==================================================================================+==========+
|                                    |                                               |                                                                                  |          |
| ::                                 | ::                                            | Node templates define client node configurations. Existing IPMI credentials      | **yes**  |
|                                    |                                               | and network interface physical connection information must be given to           |          |
|   node_templates:                  |   - label: controllers                        | allow Cluster POWER-Up to connect to nodes. OS installation characteristics      |          |
|       - label:                     |     ipmi:                                     | and post install network configurations are also defined.                        |          |
|         ipmi:                      |         userid: admin                         |                                                                                  |          |
|         os:                        |         password: pass                        | | Required keys:                                                                 |          |
|         physical_interfaces:       |     os:                                       | |   *label*   - Unique label used to reference this template.                    |          |
|         interfaces:                |         hostname_prefix: ctrl                 | |   *ipmi*    - IPMI credentials. See `node_templates: ipmi                      |          |
|         networks:                  |         domain: ibm.com                       |                 <node_templates_ipmi_>`_.                                        |          |
|         roles:                     |         profile: ubuntu-14.04-server-ppc64el  | |   *os*      - Operating system configuration. See `node_templates: os          |          |
|                                    |         install_device: /dev/sda              |                 <node_templates_os_>`_.                                          |          |
|                                    |         kernel_options: quiet                 | |   *physical_interfaces* - Physical network interface port mappings. See        |          |
|                                    |     physical_interfaces:                      |                             `node_templates: physical_interfaces                 |          |
|                                    |         ipmi:                                 |                             <node_templates_physical_ints_>`_.                   |          |
|                                    |             - switch: mgmt_switch_1           |                                                                                  |          |
|                                    |               ports:                          | | Optional keys:                                                                 |          |
|                                    |                   - 1                         | |   *interfaces* - Post-deploy interface assignments. See `node_templates:       |          |
|                                    |                   - 3                         |                    interfaces <node_templates_interfaces_>`_.                    |          |
|                                    |                   - 5                         | |   *networks*   - Post-deploy network (interface group) assignments. See        |          |
|                                    |         pxe:                                  |                    `node_templates: networks <node_templates_networks_>`_.       |          |
|                                    |             - switch: mgmt_switch_1           | |   *roles*      - Ansible group assignment. See `node_templates: roles          |          |
|                                    |               ports:                          |                    <node_templates_roles_>`_.                                    |          |
|                                    |                   - 2                         |                                                                                  |          |
|                                    |                   - 4                         |                                                                                  |          |
|                                    |                   - 6                         |                                                                                  |          |
|                                    |                                               |                                                                                  |          |
+------------------------------------+-----------------------------------------------+----------------------------------------------------------------------------------+----------+
| .. _node_templates_ipmi:           |                                               |                                                                                  |          |
|                                    |                                               |                                                                                  |          |
| ::                                 | ::                                            | Client node IPMI credentials. Note that IPMI credentials must be consistent      | **yes**  |
|                                    |                                               | for all members of a node template.                                              |          |
|   node_templates:                  |   - label: ppc64el                            |                                                                                  |          |
|       - ...                        |     ipmi:                                     | | Required keys:                                                                 |          |
|         ipmi:                      |         userid: ADMIN                         | |   *userid*   - IPMI userid.                                                    |          |
|             userid:                |         password: admin                       | |   *password* - IPMI password.                                                  |          |
|             password:              |     ...                                       |                                                                                  |          |
|                                    |   - lable: x86_64                             |                                                                                  |          |
|                                    |     ipmi:                                     |                                                                                  |          |
|                                    |         userid: ADMIN                         |                                                                                  |          |
|                                    |         password: ADMIN                       |                                                                                  |          |
|                                    |     ...                                       |                                                                                  |          |
|                                    |                                               |                                                                                  |          |
+------------------------------------+-----------------------------------------------+----------------------------------------------------------------------------------+----------+
| .. _node_templates_os:             |                                               |                                                                                  |          |
|                                    |                                               |                                                                                  |          |
| ::                                 | ::                                            | Client node operating system configuration.                                      | **yes**  |
|                                    |                                               |                                                                                  |          |
|   node_templates:                  |   - ...                                       | | Required keys:                                                                 |          |
|       - ...                        |     os:                                       | |   *profile*         - Cobbler profile to use for OS installation. This         |          |
|         os:                        |         hostname_prefix: controller           |                         name usually should match the name of the                |          |
|             hostname_prefix:       |         domain: ibm.com                       |                         installation image (with or without the'.iso' extension).|          |
|             domain:                |         profile: ubuntu-14.04-server-ppc64el  | |   *install_device*  - Path to installation disk device.                        |          |
|             profile:               |         install_device: /dev/sda              |                                                                                  |          |
|             install_device:        |         users:                                | | Optional keys:                                                                 |          |
|             users:                 |             - name: root                      | |   *hostname_prefix* - Prefix used to assign hostnames to client nodes          |          |
|                 - name:            |               password: <crypted password>    |                         belonging to this node template. A "-" and               |          |
|                   password:        |             - name: user1                     |                         enumeration is added to the end of the prefix to         |          |
|             groups:                |               password: <crypted password>    |                         make a unique hostname for each client node              |          |
|                 - name:            |               groups: sudo,testgroup1         |                         (e.g. "controller-1" and "controoler-2").                |          |
|             kernel_options:        |         groups:                               | |   *domain*          - Domain name used to set client FQDN.                     |          |
|                                    |             - name: testgroup1                |                         (e.g. with 'domain: ibm.com': controller-1.ibm.com)      |          |
|                                    |             - name: testgroup2                |                         (e.g. without 'domain' value: controller-1.localdomain)  |          |
|                                    |         kernel_options: quiet                 | |   *users*           - OS user accounts to create. All parameters in the        |          |
|                                    |                                               |                         `Ansible user module <ansible_user_module_>`_ are        |          |
|                                    |                                               |                         supported. **note:** Plaintext user passwords are not    |          |
|                                    |                                               |                         supported. For help see                                  |          |
|                                    |                                               |                         `Ansible's guide for generating passwords <gen_pass_>`_. |          |
|                                    |                                               | |   *groups*          - OS groups to create. All parameters in the `Ansible      |          |
|                                    |                                               |                         group module <ansible_group_module_>`_ are               |          |
|                                    |                                               |                         supported.                                               |          |
|                                    |                                               | |   *kernel_options*  - Kernel options                                           |          |
|                                    |                                               |                                                                                  |          |
+------------------------------------+-----------------------------------------------+----------------------------------------------------------------------------------+----------+
| .. _node_templates_physical_ints:  |                                               |                                                                                  |          |
|                                    |                                               |                                                                                  |          |
| ::                                 | ::                                            | Client node interface port mappings.                                             | **yes**  |
|                                    |                                               |                                                                                  |          |
|   node_templates:                  |   - ...                                       | | Required keys:                                                                 |          |
|       - ...                        |     physical_interfaces:                      | |   *ipmi* - IPMI (BMC) interface port mappings. See `physical_interfaces: ipmi  |          |
|         physical_interfaces:       |         ipmi:                                 |              <physical_ints_ipmi_>`_.                                            |          |
|             ipmi:                  |             - switch: mgmt_1                  | |   *pxe*  - PXE (OS) interface port mappings. See `physical_interfaces:         |          |
|                 - switch:          |               ports:                          |              pxe/data <physical_ints_os_>`_.                                     |          |
|                   ports:           |                   - 7                         |                                                                                  |          |
|             pxe:                   |                   - 8                         | | Optional keys:                                                                 |          |
|                 - switch:          |                   - 9                         | |   *data* - Data (OS) interface port mappings. See `physical_interfaces:        |          |
|                   interface:       |         pxe:                                  |              pxe/data <physical_ints_os_>`_.                                     |          |
|                   rename:          |             - switch: mgmt_1                  |                                                                                  |          |
|                   ports:           |               interface: eth15                |                                                                                  |          |
|             data:                  |               rename: true                    |                                                                                  |          |
|                 - switch:          |               ports:                          |                                                                                  |          |
|                   interface        |                   - 10                        |                                                                                  |          |
|                   rename:          |                   - 11                        |                                                                                  |          |
|                   ports:           |                   - 12                        |                                                                                  |          |
|                                    |         data:                                 |                                                                                  |          |
|                                    |             - switch: data_1                  |                                                                                  |          |
|                                    |               interface: eth10                |                                                                                  |          |
|                                    |               rename: true                    |                                                                                  |          |
|                                    |               ports:                          |                                                                                  |          |
|                                    |                   - 7                         |                                                                                  |          |
|                                    |                   - 8                         |                                                                                  |          |
|                                    |                   - 9                         |                                                                                  |          |
|                                    |             - switch: data_1                  |                                                                                  |          |
|                                    |               interface: eth11                |                                                                                  |          |
|                                    |               rename: false                   |                                                                                  |          |
|                                    |               ports:                          |                                                                                  |          |
|                                    |                   - 10                        |                                                                                  |          |
|                                    |                   - 11                        |                                                                                  |          |
|                                    |                   - 12                        |                                                                                  |          |
|                                    |                                               |                                                                                  |          |
+------------------------------------+-----------------------------------------------+----------------------------------------------------------------------------------+----------+
| .. _physical_ints_ipmi:            |                                               |                                                                                  |          |
|                                    |                                               |                                                                                  |          |
| ::                                 | ::                                            | IPMI (BMC) interface port mappings.                                              | **yes**  |
|                                    |                                               |                                                                                  |          |
|   node_templates:                  |   - ...                                       | | Required keys:                                                                 |          |
|       - ...                        |     physical_interfaces:                      | |   *switch* - Reference to mgmt switch *label* defined in the `switches: mgmt:  |          |
|         physical_interfaces:       |         ipmi:                                 |                <switches_mgmt_>`_ element.                                       |          |
|             ipmi:                  |             - switch: mgmt_1                  | |   *ports*  - List of port number/identifiers mapping to client node IPMI       |          |
|                 - switch:          |               ports:                          |                interfaces.                                                       |          |
|                   ports:           |                   - 7                         |                                                                                  |          |
|             ...                    |                   - 8                         | In the example three client nodes are defined and mapped to ports 7,8,9 of       |          |
|                                    |                   - 9                         | a management switch labeled "mgmt_1".                                            |          |
|                                    |                                               |                                                                                  |          |
+------------------------------------+-----------------------------------------------+----------------------------------------------------------------------------------+----------+
| .. _physical_ints_os:              |                                               |                                                                                  |          |
|                                    |                                               |                                                                                  |          |
| ::                                 | ::                                            | OS (PXE & data) interface port mappings.                                         | **yes**  |
|                                    |                                               |                                                                                  |          |
|   node_templates:                  |   - ...                                       | | Required keys:                                                                 |          |
|       - ...                        |     physical_interfaces:                      | |   *switch* - Reference to switch *label* defined in the `switches: mgmt:       |          |
|         physical_interfaces:       |         pxe:                                  |                <switches_mgmt_>`_ or `switches: data: <switches_data_>`_         |          |
|             ...                    |             - switch: mgmt_1                  |                elements.                                                         |          |
|             pxe:                   |               interface: dhcp1                | |   *interface* - Reference to interface label defined in the `interfaces:`_     |          |
|                 - switch:          |               rename: true                    |                elements.                                                         |          |
|                   interface:       |               ports:                          | |   *rename* - Value (true/false) to control whether client node interfaces      |          |
|                   rename:          |                   - 10                        |                will be renamed to match the interface iface (Ubuntu) or          |          |
|                   ports:           |                   - 11                        |                DEVICE (RHEL) value.                                              |          |
|             data:                  |                   - 12                        | |   *ports*  - List of port number/identifiers mapping to client node OS         |          |
|                 - switch:          |         data:                                 |                interfaces.                                                       |          |
|                   interface:       |             - switch: data_1                  |                                                                                  |          |
|                   rename:          |               interface: manual1              | | Note: For additional information on using *rename* see notes in                |          |
|                   ports            |               rename: true                    |   `interfaces: (Ubuntu) <interfaces_ubuntu_rename_notes_>`_ and                  |          |
|                                    |               ports:                          |   `interfaces: (RHEL) <interfaces_rhel_rename_notes_>`_.                         |          |
|                                    |                   - 7                         |                                                                                  |          |
|                                    |                   - 8                         |                                                                                  |          |
|                                    |                   - 9                         |                                                                                  |          |
|                                    |             - switch: data_1                  |                                                                                  |          |
|                                    |               interface: manual2              |                                                                                  |          |
|                                    |               rename: false                   |                                                                                  |          |
|                                    |               ports:                          |                                                                                  |          |
|                                    |                   - 10                        |                                                                                  |          |
|                                    |                   - 11                        |                                                                                  |          |
|                                    |                   - 12                        |                                                                                  |          |
|                                    |                                               |                                                                                  |          |
|                                    |                                               |                                                                                  |          |
|                                    |                                               |                                                                                  |          |
+------------------------------------+-----------------------------------------------+----------------------------------------------------------------------------------+----------+
| .. _node_templates_interfaces:     |                                               |                                                                                  |          |
|                                    |                                               |                                                                                  |          |
| ::                                 | ::                                            | OS network interface configuration assignment.                                   | no       |
|                                    |                                               |                                                                                  |          |
|   node_templates:                  |   interfaces:                                 | | Required keys:                                                                 |          |
|       - ...                        |       - label: data_int1                      | |   *interfaces* - List of references to interface *labels* from the             |          |
|         interfaces:                |       ...                                     |                    top-level `interfaces:`_ dictionary.                          |          |
|                                    |       - label: data_int2                      |                                                                                  |          |
|                                    |       ...                                     |                                                                                  |          |
|                                    |       - label: data_int3                      |                                                                                  |          |
|                                    |       ...                                     |                                                                                  |          |
|                                    |   node_templates:                             |                                                                                  |          |
|                                    |       - ...                                   |                                                                                  |          |
|                                    |         interfaces:                           |                                                                                  |          |
|                                    |             - data_int1                       |                                                                                  |          |
|                                    |             - data_int2                       |                                                                                  |          |
|                                    |             - data_int3                       |                                                                                  |          |
|                                    |                                               |                                                                                  |          |
+------------------------------------+-----------------------------------------------+----------------------------------------------------------------------------------+----------+
| .. _node_templates_networks:       |                                               |                                                                                  |          |
|                                    |                                               |                                                                                  |          |
| ::                                 | ::                                            | OS network interface configuration assignment by group.                          | no       |
|                                    |                                               |                                                                                  |          |
|   node_templates:                  |   interfaces:                                 | | Required keys:                                                                 |          |
|       - ...                        |       - label: data_int1                      | |   *networks* - List of references to network *labels* from the                 |          |
|         networks:                  |       ...                                     |                  top-level `networks:`_ dictionary.                              |          |
|                                    |       - label: data_int2                      |                                                                                  |          |
|                                    |       ...                                     |                                                                                  |          |
|                                    |       - label: data_int3                      |                                                                                  |          |
|                                    |       ...                                     |                                                                                  |          |
|                                    |   networks:                                   |                                                                                  |          |
|                                    |       - label: data_group1                    |                                                                                  |          |
|                                    |         interfaces:                           |                                                                                  |          |
|                                    |             - data_int1                       |                                                                                  |          |
|                                    |             - data_int2                       |                                                                                  |          |
|                                    |             - data_int3                       |                                                                                  |          |
|                                    |   node_templates:                             |                                                                                  |          |
|                                    |       - ...                                   |                                                                                  |          |
|                                    |         networks:                             |                                                                                  |          |
|                                    |             - data_group1                     |                                                                                  |          |
|                                    |                                               |                                                                                  |          |
+------------------------------------+-----------------------------------------------+----------------------------------------------------------------------------------+----------+
| .. _node_templates_roles:          |                                               |                                                                                  |          |
|                                    |                                               |                                                                                  |          |
| ::                                 | ::                                            | Ansible role/group assignment.                                                   | no       |
|                                    |                                               |                                                                                  |          |
|   node_templates:                  |   roles:                                      | | Required keys:                                                                 |          |
|       - ...                        |       - controllers                           | |   *roles* - List of roles (Ansible groups) to assign to client nodes           |          |
|         roles:                     |       - power_servers                         |               associated with this node template. Names can be any string.       |          |
|                                    |                                               |                                                                                  |          |
+------------------------------------+-----------------------------------------------+----------------------------------------------------------------------------------+----------+

.. _ansible_user_module: http://docs.ansible.com/ansible/latest/user_module.html
.. _gen_pass: http://docs.ansible.com/ansible/latest/reference_appendices/faq.html#how-do-i-generate-crypted-passwords-for-the-user-module
.. _ansible_group_module: http://docs.ansible.com/ansible/latest/group_module.html


software_bootstrap:
--------------------

::

    software_bootstrap:
        - hosts:
          executable:
          command:

+-------------------------+----------------------------------+----------------------------------------------------------------------------------------------------------+----------+
| Element                 | Example(s)                       | Description                                                                                              | Required |
+=========================+==================================+==========================================================================================================+==========+
|                         |                                  |                                                                                                          |          |
| ::                      | ::                               | Software bootstrap defines commands to be run on client nodes after Cluster Genesis completes.           | no       |
|                         |                                  | This is useful for various additional configuration activities, such as bootstrapping additional         |          |
|   software_bootstrap:   |   software_bootstrap:            | software package installations.                                                                          |          |
|       - hosts:          |       - hosts: all               |                                                                                                          |          |
|         executable:     |         command: apt-get update  | | Required keys:                                                                                         |          |
|         command:        |       - hosts: openstackservers  | |   *hosts*   - Hosts to run commands on. The value can be set to 'all' to run on all hosts,             |          |
|                         |         executable: /bin/bash    |                 node_template labels, or role/group names.                                               |          |
|                         |         command: |               | |   *command* - Command to run.                                                                          |          |
|                         |           set -e                 |                                                                                                          |          |
|                         |           apt update             | | Optional keys:                                                                                         |          |
|                         |           apt upgrade -y         | |   *executable* - Path to shell used to execute the command.                                            |          |
|                         |                                  |                                                                                                          |          |
+-------------------------+----------------------------------+----------------------------------------------------------------------------------------------------------+----------+
