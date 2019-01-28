# Kickstart for RHEL7

install
url --url=http://$http_server/$distro/

text

keyboard --vckeymap=us --xlayouts='us'
lang en_US.UTF-8
timezone America/Chicago --utc

auth --enableshadow --enablemd5
user $SNIPPET('defaultuser') --groups=wheel $SNIPPET('password')
network --hostname=$getVar('hostname').$getVar('domain', 'localdomain')

clearpart --all --initlabel
ignoredisk --only-use=$getVar('install_disk', '/dev/sda')
bootloader --location=mbr --boot-drive=$getVar('install_disk', '/dev/sda')
autopart

reboot

%packages
@core
bridge-utils
vim
wget
ntp
%end

%pre
$SNIPPET('kickstart_start')
%end

%post
# Add yum sources
# Add ssh keys to root
mkdir /root/.ssh
chmod 700 /root/.ssh
wget http://$http_server/authorized_keys -O /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys
echo -e "[$distro]" > /etc/yum.repos.d/$(distro).repo
echo -e "name=$distro" >> /etc/yum.repos.d/$(distro).repo
echo -e "baseurl=http://$http_server/$distro/" >> /etc/yum.repos.d/$(distro).repo
echo -e "enabled=1" >> /etc/yum.repos.d/$(distro).repo
echo -e "gpgcheck=0" >> /etc/yum.repos.d/$(distro).repo
$SNIPPET('kickstart_done')
%end
