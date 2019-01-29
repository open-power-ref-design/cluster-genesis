#!/usr/bin/python

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

import os
import sys
import fileinput
import re

import code

user = raw_input("Enter current user: ")
print '\n'
os.chdir("/home/{}/power-up/logs/dependencies/".format(user))
cwd = os.getcwd()
print("*ENGINEERING MODE* INFO - Current working directory is: ", cwd)

class engr_delta_collect():

      def __init__(self,pre_list_file,post_list_file):

          self.pre_list_file = pre_list_file
          self.post_list_file = post_list_file
          self.final_file = final_file = (pre_list_file.split('_',3)[0] + "_" + pre_list_file.split('_',3)[1] + '_pkglist_final.txt')

          self.post_list_file = post_list_file
          self.pre_pkg_list = pre_pkg_list = []
          self.post_pkg_list = final_pkg_list = []
          self.delta_pkg_list = delta_pkg_list = []
   
      def pre_package_lister(self): 

        pre_dbfile  = open("{}".format(self.pre_list_file),'r')
        for line_a in pre_dbfile.readlines():
           value_a = line_a.split()
           final_value_a = value_a[0]
           self.pre_pkg_list.append(final_value_a)

        print "\n*ENGINEERING MODE* INFO - Pre Data loaded\n"
        return self.pre_pkg_list
         
      def post_package_lister(self):  

        pre_dbfile  = open("{}".format(self.post_list_file),'r')
        for line_a in pre_dbfile.readlines():
           value_a = line_a.split()
           final_value_a = value_a[0]
           self.post_pkg_list.append(final_value_a)

        print "\n*ENGINEERING MODE* INFO - Post Data Loaded\n"
        return self.post_pkg_list

      def delta_logic(self): 

         for i in self.pre_pkg_list:
            for x in self.post_pkg_list:
               if x == i:
                  self.delta_pkg_list.append(x)
                  self.post_pkg_list.remove(x)
                  os.system('touch {}; chmod 777 {}'.format(self.final_file, self.final_file))

         with open('{}'.format(self.post_list_file)) as oldfile, open('{}'.format(self.final_file), 'wt+') as newfile:
            for line in oldfile:
               if any(pkg in line for pkg in self.post_pkg_list):
                  newfile.write(line)

         print "\n*ENGINEERING MODE* INFO - Delta Results:\n"
         print self.post_pkg_list
         print '\n'

         return self.post_pkg_list

      def yum_formatter(self):

         dep_search = [
                       'anaconda',
                       'cuda-powerup',
                       'powerai-powerup',
                       'dependencies-powerup',
                       'epel-ppc64le-powerup',
                       'installed',
                      ]
         dep_files = [
                      'anaconda_{}'.format(self.final_file),
                      'cuda-powerup_{}'.format(self.final_file),
                      'powerai-powerup_{}'.format(self.final_file),
                      'dependencies-powerup_{}'.format(self.final_file),
                      'epel-ppc64le-powerup_{}'.format(self.final_file),
                      'installed_{}'.format(self.final_file),
                      ]

         tmp_dep_files = [
                          'tmp_anaconda_{}'.format(self.final_file),
                          'tmp_cuda-powerup_{}'.format(self.final_file),
                          'tmp_powerai-powerup_{}'.format(self.final_file),
                          'tmp_dependencies-powerup_{}'.format(self.final_file),
                          'tmp_epel-ppc64le-powerup_{}'.format(self.final_file),
                          'tmp_installed_{}'.format(self.final_file),
                         ]

         yum_conda_dbfile = open('anaconda_{}'
                                .format(self.final_file),'w+')
         yum_cuda_dbfile = open('cuda-powerup_{}'
                               .format(self.final_file),'w+')
         yum_powerai_dbfile = open('powerai-powerup_{}'
                                  .format(self.final_file),'w+')
         yum_dependencies_dbfile = open('dependencies-powerup_{}'
                                       .format(self.final_file),'w+')
         yum_epel_dbfile = open('epel-ppc64le-powerup_{}'
                               .format(self.final_file),'w+')
         yum_installed_dbfile = open('installed_{}'
                                    .format(self.final_file),'w+')

         anaconda_list = []
         cuda_powerup_list = []
         powerai_powerup_list = []
         dependencies_powerup_list = []
         epel_ppc64le_powerup_list = []
         installed_list = []

         for dep in dep_files:
            os.system("touch {}; chmod 777 {}".format(dep,dep))

         for search in dep_search:
            dep_grep = os.popen("cat {} | xargs -n3 | column -t > tmp_{}_{}"
                               .format(self.final_file,search,self.final_file))

         for line_a in open("{}".format(tmp_dep_files[0]),'r').readlines():
            value_a = line_a.split()
            value_b = value_a[0]
            prefix = value_b.split('.',1)[0]
            suffix = value_b.split('.',1)[1]
            version = value_a[1]
            new_value = "{}-{}.{}".format(prefix,version,suffix)
            yum_conda_dbfile.write('{}\n'.format(new_value))

         for line_a in open("{}".format(tmp_dep_files[1]),'r').readlines():
            value_a = line_a.split()
            value_b = value_a[0]
            prefix = value_b.split('.',1)[0]
            suffix = value_b.split('.',1)[1]
            version = value_a[1]
            new_value = "{}-{}.{}".format(prefix,version,suffix)
            yum_cuda_dbfile.write('{}\n'.format(value_a[0]))

         for line_a in open("{}".format(tmp_dep_files[2]),'r').readlines():
            value_a = line_a.split()
            value_b = value_a[0]
            prefix = value_b.split('.',1)[0]
            suffix = value_b.split('.',1)[1]
            version = value_a[1]
            new_value = "{}-{}.{}".format(prefix,version,suffix)
            yum_powerai_dbfile.write('{}\n'.format(new_value))

         for line_a in open("{}".format(tmp_dep_files[3]),'r').readlines():
            value_a = line_a.split()
            value_b = value_a[0]
            prefix = value_b.split('.',1)[0]
            suffix = value_b.split('.',1)[1]
            version = value_a[1]
            new_value = "{}-{}.{}".format(prefix,version,suffix)
            yum_dependencies_dbfile.write('{}\n'.format(new_value))

         for line_a in open("{}".format(tmp_dep_files[4]),'r').readlines():
            value_a = line_a.split()
            value_b = value_a[0]
            prefix = value_b.split('.',1)[0]
            suffix = value_b.split('.',1)[1]
            version = value_a[1]
            new_value = "{}-{}.{}".format(prefix,version,suffix)
            yum_epel_dbfile.write('{}\n'.format(new_value))

         for line_b in open("{}".format(tmp_dep_files[5]),'r').readlines():
            value_a = line_a.split()
            value_b = value_a[0]
            prefix = value_b.split('.',1)[0]
            suffix = value_b.split('.',1)[1]
            version = value_a[1]
            new_value = "{}-{}.{}".format(prefix,version,suffix)
            yum_installed_dbfile.write('{}\n'.format(new_value))

         os.system("sudo rm -rf tmp* {} ".format(self.final_file)) 

         print ("\n*ENGINEERING MODE* INFO - Yum format completed\n") 

      def pip_formatter(self): 

         pip_dbfile = open('{}'.format(self.final_file),'rb+')
         for line_c in pip_dbfile.readlines():
            value_c = line_c.split()
            prefix = value_c[0]
            suffix = value_c[1]
            new_value = "{}=={}".format(prefix,suffix)
            pip_dbfile.write('{}\n'.format(new_value))
        
         print ("\n*ENGINEERING MODE* INFO - Pip format Completed\n")

      def conda_formatter(self):

         conda_dbfile = open('{}'.format(self.final_file),'rb+')
         for line_d in conda_dbfile.readlines():
            value_d = line_d.split()
            prefix = value_d[0]
            suffix = value_d[2]
            version = value_d[1]
            new_value = ("{}-{}-{}.tar.bz2"
                        .format(prefix,version,suffix))

         print ("\n*ENGINEERING MODE* INFO - Conda format completed\n")

##START##

pre_list_file = [
                 'client_yum_pre_list.txt',
                 'client_pip_pre_install.txt',
                 'dlipy3_pip_pre_install.txt',
                 'dlipy2_pip_pre_install.txt',
                 'client_conda_pre_install.txt',
                 'dlipy3_conda_pre_install.txt',
                 'dlipy2_conda_pre_install.txt',
                ]

post_list_file = [
                  'client_yum_post_list.txt',
                  'client_pip_post_install.txt',
                  'dlipy3_pip_post_install.txt',
                  'dlipy2_pip_post_install.txt',
                  'client_conda_post_install.txt',
                  'dlipy3_conda_post_install.txt',
                  'dlipy2_conda_post_install.txt',
                 ]


print("\n*ENGINEERING MODE* INFO - Composing yum package delta list from client\n")
client_yum = engr_delta_collect(pre_list_file[0],post_list_file[0])
engr_delta_collect.pre_package_lister(client_yum)
engr_delta_collect.post_package_lister(client_yum)
engr_delta_collect.delta_logic(client_yum)
engr_delta_collect.yum_formatter(client_yum)

print("\n*ENGINEERING MODE* INFO - Composing pip package delta list from client\n")
client_pip = engr_delta_collect(pre_list_file[1],post_list_file[1])
engr_delta_collect.pre_package_lister(client_pip)
engr_delta_collect.post_package_lister(client_pip)
engr_delta_collect.delta_logic(client_pip)
engr_delta_collect.pip_formatter(client_pip)

print("\n*ENGINEERING MODE* INFO - Composing pip package delta list from dlipy3 environment\n")
dlipy3_pip = engr_delta_collect(pre_list_file[2],post_list_file[2])
engr_delta_collect.pre_package_lister(dlipy3_pip)
engr_delta_collect.post_package_lister(dlipy3_pip)
engr_delta_collect.delta_logic(dlipy3_pip)
engr_delta_collect.pip_formatter(dlipy3_pip)

print("\n*ENGINEERING MODE* INFO - Composing pip package delta list from dlipy2 environment\n")
dlipy2_pip = engr_delta_collect(pre_list_file[3],post_list_file[3])
engr_delta_collect.pre_package_lister(dlipy2_pip)
engr_delta_collect.post_package_lister(dlipy2_pip)
engr_delta_collect.delta_logic(dlipy2_pip)
engr_delta_collect.pip_formatter(dlipy2_pip)

#print("\n*ENGINEERING MODE* INFO - Composing conda package delta list from client\n")
#client_conda = engr_delta_collect(pre_list_file[4],post_list_file[4])
#engr_delta_collect.pre_package_lister(client_conda)
#engr_delta_collect.post_package_lister(client_conda)
#engr_delta_collect.delta_logic(client_conda)
#engr_delta_collect.conda_formatter(client_conda)

print("\n*ENGINEERING MODE* INFO - Composing conda package delta list from dlipy3 environment\n")
dlipy3_conda = engr_delta_collect(pre_list_file[5],post_list_file[5])
engr_delta_collect.pre_package_lister(dlipy3_conda)
engr_delta_collect.post_package_lister(dlipy3_conda)
engr_delta_collect.delta_logic(dlipy3_conda)
engr_delta_collect.conda_formatter(dlipy3_conda)

print("\n*ENGINEERING MODE* INFO - Composing conda package delta list from dlipy2 environment\n")
dlipy2_conda = engr_delta_collect(pre_list_file[6],post_list_file[6])
engr_delta_collect.pre_package_lister(dlipy2_conda)
engr_delta_collect.post_package_lister(dlipy2_conda)
engr_delta_collect.delta_logic(dlipy2_conda)
engr_delta_collect.conda_formatter(dlipy2_conda)

#data = [client_yum,client_pip,dlipy3_pip,dlipy2_pip,client_conda,dlipy3_conda,dlipy2_conda]

#def automator():
# 
#   pre_list_file = [
#                    'client_yum_pre_list.txt',
#                    'client_pip_pre_install.txt',
#                    'dlipy3_pip_pre_install.txt',
#                    'dlipy2_pip_pre_install.txt',
#                    'client_conda_pre_install.txt',
#                    'dlipy3_conda_pre_install.txt',
#                    'dlipy2_conda_pre_install.txt',
#                   ]
#   
#   post_list_file = [
#                     'client_yum_post_list.txt',
#                     'client_pip_post_install.txt',
#                     'dlipy3_pip_post_install.txt',
#                     'dlipy2_pip_post_install.txt',
#                     'client_conda_post_install.txt',
#                     'dlipy3_conda_post_install.txt',
#                     'dlipy2_conda_post_install.txt',
#                    ]
#   
#   client_yum   = [pre_list_file[0],post_list_file[0]]
#   client_pip   = [pre_list_file[1],post_list_file[1]]
#   dlipy3_pip   = [pre_list_file[2],post_list_file[2]]
#   dlipy2_pip   = [pre_list_file[3],post_list_file[3]]
#   client_conda = [pre_list_file[4],post_list_file[4]]
#   dlipy3_conda = [pre_list_file[5],post_list_file[5]]
#   dlipy2_conda = [pre_list_file[6],post_list_file[6]]
#    
#   data = [
#           client_yum,
#           client_pip,dlipy3_pip,dlipy2_pip,
#           client_conda,dlipy3_conda,dlipy2_conda
#          ]
#
#   for d in data:
#
#      current_task = engr_delta_collect(d[0],d[1])
#
#      function = d[0].split('_',4)[1]
#      env      = d[0].split('_',4)[0]
#      phase    = d[0].split('_',4)[2]
#      stage    = d[0].split('_',4)[0] +'_' + d[0].split('_',4)[1]
#      
#      print("\n*ENGINEERING MODE* INFO - Composing '{}' package delta "
#           "list from '{}' environment".format(function, env))
#
#      #code.interact(banner='function status', local=dict(globals(), **locals()))  
#      
#      print ("\n*ENGINEERING MODE* INFO - Loading Data\n")
#      pre  = engr_delta_collect.pre_package_lister() 
#      post = engr_delta_collect.post_package_lister(stage)
#      print ("\n*ENGINEERING MODE* INFO - Composing Delta Data\n")
#      delta = engr_delta_collect.delta_logic(d)
#
#      code.interact(banner='function status', local=dict(globals(), **locals()))
#
#      if (function == 'yum'):
#         print("\n*ENGINEERING MODE* INFO - Structuring 'yum' Delta Data\n")
#         yum_formatter(d)
#      elif (function == 'pip'):
#         print("\n*ENGINEERING MODE* INFO - Structuring 'pip' Delta Data\n")
#         pip_formatter(d)
#      elif (function == 'conda'):
#         print("\n*ENGINEERING MODE* INFO - Structuring 'conda' Delta Data\n")
#         conda_formatter(d)
#      else:
#         print ("ERROR: Invalid Match - Exiting")
#         sys.exit()
#
#
#automator()

print("Done.")
#
#
