#!/usr/bin/python

import os
import sys


#path to dependent packages
dependent_pkgs_path = '/srv/repos/dependencies/rhel7/dependencies'
file = 'dependent_packages'

os.mkdir(file)
os.chdir(file)

#Create list of dependent packages and store to dependent_pkg_list.txt
os.system('ls {} | grep .rpm > dependent_pkg_list.txt' .format(dependent_pkgs_path))

