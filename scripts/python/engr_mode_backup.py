#!/usr/bin/env python3

# Copyright 2018 IBM Corp.
#
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import os
import sys
import re

import lib.logger as logger
from lib.genesis import GEN_PATH, GEN_SOFTWARE_PATH, get_ansible_playbook_path, get_playbooks_path, get_logs_path
from lib.utilities import sub_proc_display, sub_proc_exec, heading1, Color, \
    get_selection, get_yesno, rlinput, bold, ansible_pprint, replace_regex

#Global_Prameters
#
#ENGR_MODE_STATUS=False
#user='jonesdt'
#client='rhel75'

def dependency_folder_collector():
   dependencies_path = get_logs_path() +'/dependencies'
   if not os.path.exists('{}'.format(dependencies_path)):
          os.makedirs('{}'.format(dependencies_path))
   user='jonest'
   client='rhel75'   
   sub_proc_display("scp -r {}@192.168.47.21:/home/{}/"
                   "*.txt /home/{}/power-up/logs/dependencies"
                   .format(client, client, user) ,shell=True)

def pre_post_file_collect(task):

   host_path = get_playbooks_path() +'/software_hosts'
   tasks_list = [
                  'yum_update_cache.yml',
#                 'yum_install_additional_software.yml',
#                 'update_kernel.yml',
#                 'disable_udev_mem_auto_onlining.yml',
#                 'disable_udev_mem_auto_onlining.yml',
#                 'install_cuda.yml',
#                 'install_cudnn.yml',
#                 'install_nccl.yml',
#                 'anaconda_prep.yml',
#                 'anaconda_install.yml',
#                 'complete_system_setup.yml',
#                 'powerai_license_install.yml',
#                 'powerai_license_check.yml',
#                 'install_frameworks.yml',
                 ] 
  
   if (task in tasks_list):

      sub_proc_display(f"ansible all -i {host_path} -m shell -a "
                       "'yum list installed | sed 1,2d | xargs -n3 | column -t > yum_pre_list.txt'",
                       shell=True)

   elif (task == 'configure_spectrum_conductor.yml'):

#usr_space
      # Gather pre pip_list from user
      sub_proc_display(f"ansible all -i {host_path} -m shell -a "
                       "'/opt/anaconda3/bin/pip list > "
                       "client_pip_pre_install.txt'",
                       shell=True)
      # Gather pre conda_list from user
      sub_proc_display(f"ansible all -i {host_path} -m shell -a "
                       "'conda list > client_conda_pre_install.txt'",
                       shell=True)
#dlipy3_env
      # Create dlipy3 test environment
      sub_proc_display(f"ansible all -i {host_path} -m shell -a "
                       "'/opt/anaconda3/bin/conda "
                       "create --name dlipy3_test --yes pip python=3.6'",
                       shell=True)
      # Activate dlipy3_test and gather pre pip_list
      sub_proc_display(f"ansible all -i {host_path} -m shell -a "
                       "'source /opt/anaconda3/bin/activate dlipy3_test; "
                       "/opt/anaconda3/envs/dlipy3_test/bin/pip list > "
                       "dlipy3_pip_pre_install.txt'",
                       shell=True)
      # Activate dlipy3_test env and gather pre conda_list
      sub_proc_display(f"ansible all -i {host_path} -m shell -a "
                       "'source /opt/anaconda3/bin/activate dlipy3_test; "
                       "conda list > dlipy3_conda_pre_install.txt'",
                       shell=True)
      #Deactivate dlipy3_test env
#      sub_proc_display(f"ansible all -i {host_path} -m shell -a "
#                       "'source /opt/anaconda3/bin/deactivate dlipy3_test ",
#                       shell=True)
      
#dlipy2_env
      # Create dlipy2_test environment
      sub_proc_display(f"ansible all -i {host_path} -m shell -a "
                       "'/opt/anaconda3/bin/conda "
                       "create --name dlipy2_test --yes pip python=2.7'",
                       shell=True)
      # Activate dlipy2_test env and gather pre pip_list #check (not outputting) 
      sub_proc_display(f"ansible all -i {host_path} -m shell -a "
                       "'source /opt/anaconda3/bin/activate dlipy2_test; "
                       "~/.conda/envs/dlipy2_test/bin/pip list > "
                       "dlipy2_pip_pre_install.txt'",
                       shell=True)
      # Activate dlipy2_test env and gather pre conda_list
      sub_proc_display(f"ansible all -i {host_path} -m shell -a "
                       "'source /opt/anaconda3/bin/activate dlipy2_test; "
                       "conda list > dlipy2_conda_pre_install.txt'",
                       shell=True)
      #Deactivate dlipy2_test env
#      sub_proc_display(f"ansible all -i {host_path} -m shell -a "
#                       "'source /opt/anaconda3/bin/deactivate dlipy2_test ",
#                       shell=True)

   elif (task == 'entitle_spectrum_conductor_dli.yml'):

#post_client
      # Gather post pip_list from user
      sub_proc_display(f"ansible all -i {host_path} -m shell -a "
                       "'/opt/anaconda3/bin/pip list > "
                       "client_pip_post_install.txt'",
                       shell=True)
      # Gather post conda_list from user
      sub_proc_display(f"ansible all -i {host_path} -m shell -a "
                       "'conda list > client_conda_post_install.txt'",
                       shell=True)
#post_dlipy3
      # Activate dlipy3 and gather post pip_list
      sub_proc_display(f"ansible all -i {host_path} -m shell -a "
                       "'source /opt/anaconda3/bin/activate dlipy3; "
                       "/opt/anaconda3/envs/dlipy3/bin/pip list > "
                       "dlipy3_pip_post_install.txt'",
                       shell=True)
      # Activate dlipy3 env and gather post conda_list
      sub_proc_display(f"ansible all -i {host_path} -m shell -a "
                       "'source /opt/anaconda3/bin/activate dlipy3; "
                       "conda list > dlipy3_conda_post_install.txt'",
                       shell=True)
#post_dlipy2
      # Activate dlipy2 and gather post pip_list 
      sub_proc_display(f"ansible all -i {host_path} -m shell -a "
                       "'source /opt/anaconda3/bin/activate dlipy2; "
                       "~/.conda/envs/dlipy2_test/bin/pip list > "
                       "dlipy2_pip_post_install.txt'",
                       shell=True)
      # Activate dlipy2 and gather post conda_list
      sub_proc_display(f"ansible all -i {host_path} -m shell -a "
                       "'source /opt/anaconda3/bin/activate dlipy2; "
                       "conda list > dlipy2_conda_post_install.txt'",
                       shell=True)

   elif (task == 'powerai_tuning.yml'):
      sub_proc_display(f"ansible all -i {host_path} -m shell -a "
                       "'yum list installed | sed 1,2d | xargs -n3 | column -t > yum_post_list.txt'",
                       shell=True)      

def ENGR_MODE(task):
   ENGR_MODE_STATUS = True  
   if ENGR_MODE_STATUS == False:
      pass
   else:
      pre_post_file_collector(task)

#to find Delts, RUN "dependencies_delta_compare.py" located in /power-up/scripts/python


       
