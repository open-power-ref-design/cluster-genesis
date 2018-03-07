.. _inventory_file_spec:

Cluster Inventory File Specification
=====================================

**Specification Version: v2.0**

TODO: Short description of *inventory.yml* and how it should be used.

Each section represents a top level dictionary key:

| `version:`_
| `location:`_
| `switches:`_
| `nodes:`_

version:
--------

+-------------+------------------+--------------------------------------------------------------------------------------------------------------------------------------+----------+
| Element     | Example(s)       | Description                                                                                                                          | Required |
+=============+==================+======================================================================================================================================+==========+
|             |                  |                                                                                                                                      |          |
| ::          | ::               | Inventory file version.                                                                                                              | **yes**  |
|             |                  |                                                                                                                                      |          |
|   version:  |   version: v2.0  |  -----------------------------------------------------                                                                               |          |
|             |                  |  | Release Branch | Supported Inventory File Version |                                                                               |          |
|             |                  |  =====================================================                                                                               |          |
|             |                  |  | release-2.x    | version: v2.0                    |                                                                               |          |
|             |                  |  -----------------------------------------------------                                                                               |          |
|             |                  |  | release-1.x    | version: 1.0                     |                                                                               |          |
|             |                  |  -----------------------------------------------------                                                                               |          |
|             |                  |  | release-0.9    | version: 1.0                     |                                                                               |          |
|             |                  |  -----------------------------------------------------                                                                               |          |
|             |                  |                                                                                                                                      |          |
+-------------+------------------+--------------------------------------------------------------------------------------------------------------------------------------+----------+

location:
---------

See :ref:`Config Specification - Location Section <Config-Specification:location:>`.

switches:
---------

See :ref:`Config Specification - Switches Section <Config-Specification:switches:>`.

nodes:
------

::

  nodes:
      - label:
        hostname:
        rack_id:
        rack_eia:
        ipmi:
            switches:
            ports:
            userid:
            password:
            ipaddrs:
            macs:
        pxe:
            switches:
            ports:
            devices:
            ipaddrs:
            macs:
            rename:
        data:
            switches:
            ports:
            devices:
            macs:
            rename:
        os:
        interfaces:

+----------------------+-------------------------------+----------------------------------------------------------------------------------------------------------------+----------+
| Element              | Example(s)                    | Description                                                                                                    | Required |
+======================+===============================+================================================================================================================+==========+
|                      |                               |                                                                                                                |          |
| ::                   | ::                            | Type.                                                                                                          | **yes**  |
|                      |                               |                                                                                                                |          |
|   nodes:             |   label: ubuntu-servers       |                                                                                                                |          |
|       label:         |                               |                                                                                                                |          |
|       ...            |                               |                                                                                                                |          |
|                      |                               |                                                                                                                |          |
+----------------------+-------------------------------+----------------------------------------------------------------------------------------------------------------+----------+
|                      |                               |                                                                                                                |          |
| ::                   | ::                            | Hostname.                                                                                                      | **yes**  |
|                      |                               |                                                                                                                |          |
|   nodes:             |   hostname: server-1          |                                                                                                                |          |
|       hostname:      |                               |                                                                                                                |          |
|       ...            |                               |                                                                                                                |          |
|                      |                               |                                                                                                                |          |
+----------------------+-------------------------------+----------------------------------------------------------------------------------------------------------------+----------+
|                      |                               |                                                                                                                |          |
| ::                   | ::                            | Rack ID.                                                                                                       | no       |
|                      |                               |                                                                                                                |          |
|   nodes:             |   rack_id: rack_1             |                                                                                                                |          |
|       rack_id:       |                               |                                                                                                                |          |
|       ...            |                               |                                                                                                                |          |
|                      |                               |                                                                                                                |          |
+----------------------+-------------------------------+----------------------------------------------------------------------------------------------------------------+----------+
|                      |                               |                                                                                                                |          |
| ::                   | ::                            | Rack EIA.                                                                                                      | no       |
|                      |                               |                                                                                                                |          |
|   nodes:             |   rack_eia: U10               |                                                                                                                |          |
|       rack_eia:      |                               |                                                                                                                |          |
|       ...            |                               |                                                                                                                |          |
|                      |                               |                                                                                                                |          |
+----------------------+-------------------------------+----------------------------------------------------------------------------------------------------------------+----------+
|                      |                               |                                                                                                                |          |
| ::                   | ::                            | IPMI related parameters.                                                                                       | **yes**  |
|                      |                               |                                                                                                                |          |
|   nodes:             |   nodes:                      | | Required keys:                                                                                               |          |
|       ipmi:          |       ipmi:                   | |   *switches*  - Management switches.                                                                         |          |
|           switches:  |           switches:           | |   *ports*     - Management ports.                                                                            |          |
|           ports:     |           - mgmt_1            | |   *ipaddrs*   - IPMI interface ipaddrs.                                                                      |          |
|           ipaddr:    |           - mgmt_2            | |   *macs*      - IPMI interface MAC addresses.                                                                |          |
|           mac:       |           ports:              | |   *userid*    - IPMI userid.                                                                                 |          |
|           userid:    |           - 1                 | |   *password*  - IPMI password.                                                                               |          |
|           password:  |           - 11                |                                                                                                                |          |
|       ...            |           ipaddrs:            | List items are correlated by index.                                                                            |          |
|                      |           - 10.0.0.1          |                                                                                                                |          |
|                      |           - 10.0.0.2          |                                                                                                                |          |
|                      |           macs:               |                                                                                                                |          |
|                      |           - 01:23:45:67:89:AB |                                                                                                                |          |
|                      |           - 01:23:45:67:89:AC |                                                                                                                |          |
|                      |           userid: user        |                                                                                                                |          |
|                      |           password: passw0rd  |                                                                                                                |          |
|                      |                               |                                                                                                                |          |
+----------------------+-------------------------------+----------------------------------------------------------------------------------------------------------------+----------+
|                      |                               |                                                                                                                |          |
| ::                   | ::                            | PXE related parameters.                                                                                        | **yes**  |
|                      |                               |                                                                                                                |          |
|   nodes:             |   nodes:                      | | Required keys:                                                                                               |          |
|       pxe:           |       pxe:                    | |   *switches*  - Management switches.                                                                         |          |
|           switches:  |           switches:           | |   *ports*     - Management ports.                                                                            |          |
|           ports:     |           - mgmt_1            | |   *devices*   - Network devices.                                                                             |          |
|           devices:   |           - mgmt_2            | |   *ipaddrs*   - Interface ipaddrs.                                                                           |          |
|           ipaddrs:   |           ports:              | |   *macs*      - Interface MAC addresses.                                                                     |          |
|           macs:      |           - 2                 | |   *rename*    - Interface rename flags.                                                                      |          |
|           rename:    |           - 12                |                                                                                                                |          |
|       ...            |           devices:            | List items are correlated by index.                                                                            |          |
|                      |           - eth16             |                                                                                                                |          |
|                      |           - eth17             |                                                                                                                |          |
|                      |           ipaddrs:            |                                                                                                                |          |
|                      |           - 10.0.1.1          |                                                                                                                |          |
|                      |           - 10.0.1.2          |                                                                                                                |          |
|                      |           macs:               |                                                                                                                |          |
|                      |           - 01:23:45:67:89:AD |                                                                                                                |          |
|                      |           - 01:23:45:67:89:AE |                                                                                                                |          |
|                      |           rename:             |                                                                                                                |          |
|                      |           - true              |                                                                                                                |          |
|                      |           - true              |                                                                                                                |          |
|                      |                               |                                                                                                                |          |
+----------------------+-------------------------------+----------------------------------------------------------------------------------------------------------------+----------+
|                      |                               |                                                                                                                |          |
| ::                   | ::                            | Data related parameters.                                                                                       | **yes**  |
|                      |                               |                                                                                                                |          |
|   nodes:             |   nodes:                      | | Required keys:                                                                                               |          |
|       data:          |       data:                   | |   *switches*  - Data switches.                                                                               |          |
|           switches:  |           switches:           | |   *ports*     - Data ports.                                                                                  |          |
|           ports:     |           - data_1            | |   *devices*   - Network devices.                                                                             |          |
|           devices:   |           - data_2            | |   *macs*      - Interface MAC addresses.                                                                     |          |
|           macs:      |           ports:              | |   *rename*    - Interface rename flags.                                                                      |          |
|           rename:    |           - 1                 |                                                                                                                |          |
|       ...            |           - 2                 | List items are correlated by index.                                                                            |          |
|                      |           devices:            |                                                                                                                |          |
|                      |           - eth26             |                                                                                                                |          |
|                      |           - eth27             |                                                                                                                |          |
|                      |           macs:               |                                                                                                                |          |
|                      |           - 01:23:45:67:89:AF |                                                                                                                |          |
|                      |           - 01:23:45:67:89:BA |                                                                                                                |          |
|                      |           rename:             |                                                                                                                |          |
|                      |           - true              |                                                                                                                |          |
|                      |           - true              |                                                                                                                |          |
|                      |                               |                                                                                                                |          |
+----------------------+-------------------------------+----------------------------------------------------------------------------------------------------------------+----------+
|                      |                               |                                                                                                                |          |
| ::                   |                               | Operating system configuration.                                                                                | **yes**  |
|                      |                               |                                                                                                                |          |
|   nodes:             |                               | See :ref:`Config Specification - Node Templates OS Section <Config-Specification:_node_templates_os:>`.        |          |
|       os:            |                               |                                                                                                                |          |
|       ...            |                               |                                                                                                                |          |
|                      |                               |                                                                                                                |          |
+----------------------+-------------------------------+----------------------------------------------------------------------------------------------------------------+----------+
|                      |                               |                                                                                                                |          |
| ::                   |                               | Interface definitions.                                                                                         | **yes**  |
|                      |                               |                                                                                                                |          |
|   nodes:             |                               | | Interfaces assigned to a node in                                                                             |          |
|       interfaces:    |                               |   :ref:`Config Specification - Node Templates interfaces <Config-Specification:_node_templates_interfaces:>`   |          |
|       ...            |                               |   or                                                                                                           |          |
|                      |                               |   :ref:`Config Specification - Node Templates networks <Config-Specification:_node_templates_networks:>` are   |          |
|                      |                               |   included in this list. Interfaces are copied from                                                            |          |
|                      |                               |   :ref:`Config Specification - Interfaces section <Config-Specification:interfaces:>` and modified in the      |          |
|                      |                               |   following ways:                                                                                              |          |
|                      |                               | |                                                                                                              |          |
|                      |                               | |   * *address_list* and *address_start* keys are replaced with *address* and each value is replaced with a    |          |
|                      |                               | |   single unique IP address.                                                                                  |          |
|                      |                               | |                                                                                                              |          |
|                      |                               | |   * *IPADDR_list* and *IPADDR_start* keys are replaced with *IPADDR* and each value is replaced with a       |          |
|                      |                               | |   single unique IP address.                                                                                  |          |
|                      |                               | |                                                                                                              |          |
|                      |                               | |   * If 'rename: false' in                                                                                    |          |
|                      |                               |     :ref:`Config Specification - Node Templates <Config-Specification:_physical_ints_os:>` then *iface*,       |          |
|                      |                               |     *DEVICE*, and any interface value referencing them will be modified to match the OS given interface name.  |          |
|                      |                               |     See                                                                                                        |          |
|                      |                               |     :ref:`Config Specification - interfaces: (Ubuntu) <Config-Specification:_interfaces_ubuntu_rename_notes:>` |          |
|                      |                               |     and :ref:`Config Specification - interfaces: (RHEL) <Config-Specification:_interfaces_rhel_rename_notes:>` |          |
|                      |                               |     for details.                                                                                               |          |
|                      |                               |                                                                                                                |          |
+----------------------+-------------------------------+----------------------------------------------------------------------------------------------------------------+----------+
