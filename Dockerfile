FROM ubuntu:18.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y \
    apache2 \
    iproute2 \
    iputils-ping \
    dhcpdump \
    git \
    ipmitool \
    libapache2-mod-wsgi \
    libffi-dev \
    libssl-dev \
    mkisofs \
    openssh-server \
    python2.7 \
    python2.7-dev \
    python-cheetah \
    python-netaddr \
    python-pysnmp4 \
    python-pycurl \
    python-simplejson \
    python-yaml \
    python3.6 \
    python3.6-dev \
    python3-pip \
    python3.6-venv \
    ssh \
    wget \
    vim \
    python-django \
    xorriso \
    yum-utils \
    dnsmasq \
    fence-agents \
    lsb-release \
    createrepo \
    debmirror \
    ntp

RUN if [ $(uname -m) = "x86_64" ]; then \
    apt-get update && \
    apt-get install -y \
    syslinux; \
    fi

RUN if [ $(uname -m) = "ppc64le" ]; then \
    apt-get update && \
    apt-get install -y \
    syslinux-common; \
    fi

COPY . /opt/power-up/

RUN bash -e /opt/power-up/scripts/venv_install.sh /opt/power-up/

EXPOSE 67/udp
EXPOSE 68/udp

CMD /bin/bash
