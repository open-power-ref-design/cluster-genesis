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
import subprocess
import code
import getpass

import lib.logger as logger
from lib.genesis import GEN_PATH, GEN_SOFTWARE_PATH, get_ansible_playbook_path, get_playbooks_path, get_dependencies_path
from lib.utilities import sub_proc_display, sub_proc_exec, heading1, Color, \
    get_selection, get_yesno, rlinput, bold, ansible_pprint, replace_regex
from pathlib import Path

def dependency_folder_collector():
   #sub_proc_display("ansible-fetch copy_text_files_from_client.yml",
   #                 shell=True)
   dependencies_path = get_dependencies_path()
   if not os.path.exists('{}'.format(dependencies_path)):
          os.makedirs('{}'.format(dependencies_path))

										   #client
def pre_post_file_collect(task):

   access = ' --become --ask-become-pas'

   def file_collecter(file_name,process):

      #current_user    = input("Enter current user: ")
      #client_user     = input("Enter client user: ")
      #client_hostname = input("Enter client hostname or IP: ")

      current_user    = 'pupbyobu'
      client_user     = 'rhel75'
      client_hostname = 'server-1'

      print (f"\n*ENGINEERING MODE* INFO - Current user: {current_user}\n")

      remote_access   = f"{client_user}@{client_hostname}"
      remote_location = f"/home/{client_user}/"
      dbfile          = f"{file_name}"
      local_dir       = dependencies_path

      data_copy_cmd  = f'scp -r {remote_access}:{remote_location}{dbfile} {local_dir}'

      ansible_prefix = f'ansible all -i {host_path} -m shell -a '
      yum_file_format    = " | sed 1,2d | xargs -n3 | column -t > "
      conda_file_format = " | sed 1,3d >"
      function = dbfile.split('_',4)[1]

      if (function == 'yum'):
         ansible_cmd = f"{ansible_prefix}'{process}{yum_file_format}{file_name}'"
      elif (function == 'conda'):
          ansible_cmd = (f"{ansible_prefix}'{process}{conda_file_format}{file_name}'"
                         f"{access}")
      else:
         ansible_cmd = f"{ansible_prefix}'{process} > {file_name}'{access}"

      print (f"\n*ENGINEERING MODE* INFO - Checking for {file_name} Data on Client Node\n")
      cmd = f"ssh {remote_access} ls | grep {file_name}"
      find_file, err, rc = sub_proc_exec(cmd, shell=True)
      find_file_formatted = find_file.rstrip("\n\r")

      #code.interact(banner='Debug', local=dict(globals(), **locals()))

      if find_file_formatted == f'{file_name}':
         print (f"\n*ENGINEERING MODE* INFO - {file_name} data exists on client node!\n")
         pass
      else:
         print (f"\n*ENGINEERING MODE* INFO - Creating {file_name} data on client node\n")
         sub_proc_display(ansible_cmd, shell=True)
      menu = True
      while menu == True:
         my_file = Path(f'{local_dir}{dbfile}')
         if my_file.is_file():
            print("\n*ENGINEERING MODE* INFO - A copy of the data exists locally!")
            override = input("\nAction Required: "
                             "\n1) Override Data"
                             "\n2) Make local file as backup version"
                             "\n3) Continue with Installer"
                             "\n4) Exit software installer\n")
            if override == "1":
               print (f"\n*ENGINEERING MODE* INFO - Copying {file_name} to deployer\n")
               sub_proc_display(f'{data_copy_cmd}', shell=True)
               menu = False
            elif override == "2":
               print ("*ENGINEERING MODE* INFO - Backing up local data copy\n")
               create_backup = (f"mv {local_dir}{file_name} "
                                f"{local_dir}backup_{file_name}")
               sub_proc_display(f'{create_backup}',shell=True)
               print (f"\n*ENGINEERING MODE* INFO - Copying {file_name} to deployer\n")
               sub_proc_display(f'{data_copy_cmd}', shell=True)
               menu = False
            elif override == "3":
               print (f"\n*ENGINEERING MODE* INFO - Proceeding..\n")
               menu = False
            elif override == "4":
               print ("Exiting installer.")
               sub_proc_display('sys.exit()', shell=True)
               menu = False

            else:
               print ("Please make a valid choice")
         else:
            print (f"\n*ENGINEERING MODE* INFO - Copying {file_name} to deployer\n")
            sub_proc_display(f'{data_copy_cmd}', shell=True)
            menu = False

                                        #Clean cache

   def conda_clean_cache():
      conda_cache = "/opt/anaconda3/conda-bld/"
      conda_cache_dir = ['src_cache','git_cache','hg_cache','svn_cache']
      ansible_prefix = f'ansible all -i {host_path} -m shell -a '
      print("\n*ENGINEERING MODE* INFO - Checking for conda cache")
      try:
         for cache_dir in conda_cache_dir:
            sub_proc_display(f"{ansible_prefix} 'ls {conda_cache}{cache_dir}'",
                             shell=True)
         sub_proc_display(f"{ansible_prefix} 'conda clean --all'{access}", shell=True)
      except FolderNotFoundError as exc:
            print ("\nINFO Cache directories do not exist\n")

   def yum_clean_cache():
      yum_cache_dir = '/var/cache/yum'
      print("\n*ENGINEERING MODE* INFO - Checking for yum cache")
      try:
         sub_proc_display(f"{ansible_prefix} 'ls {yum_cache_dir}'",
                          shell=True)
         yum_clean = sub_proc_display(f"ansible all -i {host_path} -m shell -a '"
                                   f"yum clean'{access}", shell=True)
      except FolderNotFoundError as exc:
         print ("\nINFO Cache directories do not exist\n")


                                        #Start


   host_path = get_playbooks_path() +'/software_hosts'
   tasks_list = [
                 'yum_update_cache.yml'
                 ]

   if (task in tasks_list):

      yum_clean_cache()

      file_collecter(file_name="client_yum_pre_install.txt",
                     process="yum list installed")

      file_collecter(file_name="client_pip_pre_install.txt",  #N/A x86 Andaconda/7.6
                     process="touch client_pip_pre_install.txt")

   elif (task == 'install_frameworks.yml'):

                                        # Clean Cache

      conda_clean_cache()

										#dlipy3_env
      # Create dlipy3 test environment

      print (f"\n*ENGINEERING MODE* INFO - Creating dlipy3_test environment\n")
      sub_proc_display(f"ansible all -i {host_path} -m shell -a "
                       "'/opt/anaconda3/bin/conda "
                       "create --name dlipy3_test --yes pip python=3.6'"
                       f"{access}",
                       shell=True)

      # Activate dlipy3_test and gather pre pip_list
      file_collecter(file_name='dlipy3_pip_pre_install.txt',
                     process='source /opt/anaconda3/bin/activate dlipy3_test && '
                             '/opt/anaconda3/envs/dlipy3_test/bin/pip list')

      # Activate dlipy3_test env and gather pre conda_list
      file_collecter(file_name='dlipy3_conda_pre_install.txt',
                     process='source /opt/anaconda3/bin/activate dlipy3_test && '
                             'conda list')

										#dlipy2_env
      # Create dlipy2_test environment
      print (f"\n*ENGINEERING MODE* INFO - Creating dlipy2_test environment\n")
      sub_proc_display(f"ansible all -i {host_path} -m shell -a "
                       "'/opt/anaconda3/bin/conda "
                       "create --name dlipy2_test --yes pip python=2.7'"
                       f"{access}",
                       shell=True)

      # Activate dlipy2_test env and gather pre pip_list
      file_collecter(file_name='dlipy2_pip_pre_install.txt',
                     process='source /opt/anaconda3/bin/activate dlipy2_test && '
                             '/opt/anaconda3/envs/dlipy2_test/bin/pip list')

      # Activate dlipy2_test env and gather pre conda_list
      file_collecter(file_name='dlipy2_conda_pre_install.txt',
                     process='source /opt/anaconda3/bin/activate dlipy2_test && '
                             'conda list')

                                        #dlinsights_env

      # Activate dlinsights and gather pre pip_list  (Note:python 2.7 env to use as refrence)
      file_collecter(file_name='dlinsights_pip_pre_install.txt',
                     process='source /opt/anaconda3/bin/activate dlipy2_test && '
                             '/opt/anaconda3/envs/dlipy3_test/bin/pip list')

      # Activate dlinsights env and gather pre conda_list
      file_collecter(file_name='dlinsights_conda_pre_install.txt',
                     process='source /opt/anaconda3/bin/activate dlipy2_test && '
                             'conda list')

   elif (task == 'configure_spectrum_conductor.yml'):

										#post_dlipy3
      # Activate dlipy3 and gather post pip_list
      file_collecter(file_name='dlipy3_pip_post_install.txt',
                     process='source /opt/anaconda3/bin/activate dlipy3 && '
                             '/opt/anaconda3/envs/dlipy3/bin/pip list')

      # Activate dlipy3 env and gather post conda_list
      file_collecter(file_name='dlipy3_conda_post_install.txt',
                     process='source /opt/anaconda3/bin/activate dlipy3 && '
                             'conda list')

										#post_dlipy2
      # Activate dlipy2 and gather post pip_list
      file_collecter(file_name='dlipy2_pip_post_install.txt',
                     process='source /opt/anaconda3/bin/activate dlipy2 && '
                             '/opt/anaconda3/envs/dlipy2/bin/pip list')

      # Activate dlipy2 and gather post conda_list
      file_collecter(file_name='dlipy2_conda_post_install.txt',
                     process='source /opt/anaconda3/bin/activate dlipy2 && '
                             'conda list')

                                       #post_dlinsights
      # Activate dlinsights and gather post pip_list
      file_collecter(file_name='dlinsights_pip_post_install.txt',
                     process='source /opt/anaconda3/bin/activate dlinsights && '
                             '/opt/anaconda3/envs/dlinsights/bin/pip list')

      # Activate dlinsights env and gather post conda_list
      file_collecter(file_name='dlinsights_conda_post_install.txt',
                     process='source /opt/anaconda3/bin/activate dlinsights && '
                             'conda list')

   elif (task=='powerai_tuning.yml'):

      # Gather post yum list from client
      file_collecter(file_name='client_yum_post_install.txt',
                     process='yum list installed')

      # Gather post pip_list from client
      file_collecter(file_name='client_pip_post_install.txt',
                     process='/opt/anaconda3/bin/pip list')

