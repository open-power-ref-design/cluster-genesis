.. _appendix_d:

Appendix - D Example system 1 Simple Flat Cluster
=================================================

.. figure:: _images/simple_flat_cluster.png
     :height: 350
     :align: center

     A simple flat cluster with two node types

**A Sample config.yml file**

The config file below defines two compute node templates with multiple network
interfaces. The deployer node needs to have access to the internet which shown
via one of the dotted line paths in the figure above or alternately via a
wireless or dedicated interface.

.. literalinclude:: ../sample-configs/basic.config.ubuntu.yml
    :language: yaml
