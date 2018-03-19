
Appendix - F Detailed Genesis Flow (needs update)
=================================================

Phase 1:

1.  Apply power to the management and data switches.
2.  All ports on the management switch will be enabled and added to a
    single LAN through genesis routines.
3.  Power on the compute, storage and controller nodes.

    1. Each BMC will automatically be assigned an arbitrary IP from the
       DHCP pool.

4.  Genesis code accesses management switch to read MAC address table
    information. (MAC to port number mapping). This will include both
    BMC MAC addresses as well as PXE port MAC addresses.
5.  Read BMC port list from the config file.
6.  Read ip address assignement for BMC ports from the DHCP server
7.  IPMI call will be issued to determine whether the BMC represents an
    x86\_64 or PPC64 system.
8.  Each BMC will be instructed to initiate a PXE install of a minimal
    OS, such as CoreOS or similar.
9.  Genesis function will access CoreOS and correlate IPMI and PXE MAC
    addresses using internal IPMI call.
10. Each data network port on the client will be issues an 'UP' and
    checked for physical connectivity.
11. 
12. Cobbler database will be updated. Need more detail.
13. Data switch will be configured.

    1. VLANS.

14. verification
15. Inventory file will be updated with IPMI, PXE and data port details.
16. IPMI will be used to configure for OS reload and reboot.
17. OS and packages will be installed on the various systems
18. 10 Gb Network ports are renamed
19. Networks are configured on system nodes. There will be a unique
    config per role. Network configuration consists of modifying the
    interfaces file template for that role and copying it to the
    servers.

-  IP addresses
-  VLANS
-  Bridges created

1. Other post OS configuration (NTP)
2. reboot for network config to take effect
3. Deployer container is copied to the first controller node.
4. The inventory file is copied to the first controller node.

Phase 2:

1. Software installation orchestrator is installed on first controller
   node and given control. Genesis activity continues on first
   controller node.
