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
|   version:  |   version: v2.0  |  +----------------+----------------------------------+                                                                               |          |
|             |                  |  | Release Branch | Supported Inventory File Version |                                                                               |          |
|             |                  |  +================+==================================+                                                                               |          |
|             |                  |  | release-2.x    | version: v2.0                    |                                                                               |          |
|             |                  |  +----------------+----------------------------------+                                                                               |          |
|             |                  |  | release-1.x    | version: 1.0                     |                                                                               |          |
|             |                  |  +----------------+----------------------------------+                                                                               |          |
|             |                  |  | release-0.9    | version: 1.0                     |                                                                               |          |
|             |                  |  +----------------+----------------------------------+                                                                               |          |
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
        data:
            switches:
            ports:
            devices:
            macs:
        os:

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
|       ...            |           ports:              | |   *macs*      - Interface MAC addresses.                                                                     |          |
|                      |           - 2                 |                                                                                                                |          |
|                      |           - 12                | List items are correlated by index.                                                                            |          |
|                      |           devices:            |                                                                                                                |          |
|                      |           - eth16             |                                                                                                                |          |
|                      |           - eth17             |                                                                                                                |          |
|                      |           ipaddrs:            |                                                                                                                |          |
|                      |           - 10.0.1.1          |                                                                                                                |          |
|                      |           - 10.0.1.2          |                                                                                                                |          |
|                      |           macs:               |                                                                                                                |          |
|                      |           - 01:23:45:67:89:AD |                                                                                                                |          |
|                      |           - 01:23:45:67:89:AE |                                                                                                                |          |
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
|           macs:      |           ports:              |                                                                                                                |          |
|       ...            |           - 1                 | List items are correlated by index.                                                                            |          |
|                      |           - 2                 |                                                                                                                |          |
|                      |           devices:            |                                                                                                                |          |
|                      |           - eth26             |                                                                                                                |          |
|                      |           - eth27             |                                                                                                                |          |
|                      |           macs:               |                                                                                                                |          |
|                      |           - 01:23:45:67:89:AF |                                                                                                                |          |
|                      |           - 01:23:45:67:89:BA |                                                                                                                |          |
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
