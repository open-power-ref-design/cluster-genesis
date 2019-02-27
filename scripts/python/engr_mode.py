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
import tempfile
import argparse
import os
import sys
import re
import subprocess
import code
import getpass
STANDALONE = False
import lib.logger as logger
from lib.genesis import GEN_PATH, GEN_SOFTWARE_PATH, get_ansible_playbook_path, get_playbooks_path, get_dependencies_path
from lib.utilities import sub_proc_display, sub_proc_exec, heading1, Color, \
    get_selection, get_yesno, rlinput, bold, ansible_pprint, replace_regex, bash_cmd
from pathlib import Path

DEPENDENCIES_PATH = get_dependencies_path()
RC_SUCCESS = 0
RC_ERROR = 99  # generic failure
RC_ARGS = 2  # failed to parse args given
RC_SRV = 20  # srv directory does not exist
RC_USER_EXIT = 40  # keyboard exit
RC_PERMISSION = 41  # Permission denied
YUM_CACHE_DIR = '/var/cache/yum'
CONDA_CACHE = "/opt/anaconda3/conda-bld/"
CONDA_CACHE_DIR = ['src_cache','git_cache','hg_cache','svn_cache']
HOST_PATH = get_playbooks_path() +'/software_hosts'
ANSIBLE_PREFIX = f'ansible all -i {HOST_PATH} -m shell -a '
YUM_CLEAN_ALL = 'yum clean all '
LOG = ""
ACCESS = ' --become --ask-become-pas'

try:
    LOG = logger.getlogger()
    STANDALONE = False
except:
    LOG = logging.getLogger(__name__)
    setup_logging()
    STANDALONE = True

def exit(rc, *extra):
    message = "\n".join(extra)
    if rc == RC_SUCCESS:
        LOG.info(message)
    else:
        LOG.error(message)
        if STANDALONE is True:
            sys.exit(rc)
        else:
            err = "RC: {0}\n{1}".format(rc, message)
            if rc == RC_SRV:
                raise OSError(err)
            elif rc == RC_ARGS:
                raise OSError(err)
            elif rc == RC_USER_EXIT:
                raise KeyboardInterrupt(err)
            elif rc == RC_PERMISSION:
                raise PermissionError(err)
            else:  # rc == RC_ERROR:
                raise Exception(err)

def get_string(string):
    tempstring = " "
    tempstring +=string
    tempstring += " }}"
    return tempstring

#
def dependency_folder_collector():
   #sub_proc_display("ansible-fetch copy_text_files_from_client.yml",
   #                 shell=True)
   if not os.path.exists('{}'.format(DEPENDENCIES_PATH)):
          os.makedirs('{}'.format(DEPENDENCIES_PATH))

def conda_clean_cache():
  LOG.debug("\n*ENGINEERING MODE* INFO - Checking for conda cache")
  try:
     for cache_dir in CONDA_CACHE_DIR:
         LOG.debug("\n*ENGINEERING MODE* INFO - Checking for conda cache")
         sub_proc_display(f"{ANSIBLE_PREFIX} 'ls {CONDA_CACHE}{cache_dir}'",
                         shell=True)
  except Exception  as e:
    LOG.debug("\nINFO ls failed\n{0}".format(e))
  try:
    sub_proc_display(f"{ANSIBLE_PREFIX} 'conda clean --all'{ACCESS}", shell=True)
  except Exception as e:
    LOG.debug("\nINFO Conda clean --all failed\n{0}".format(e))


def yum_clean_cache():
  LOG.debug("\n*ENGINEERING MODE* INFO - Checking for yum cache")
  try:
     sub_proc_display(f"{ANSIBLE_PREFIX} 'ls {YUM_CACHE_DIR}'",
                      shell=True)
  except:
     LOG.warn("\nINFO Cache directories do not exist\n")

  try:
     yum_clean = sub_proc_display(f"ansible all -i {HOST_PATH} -m shell -a '"
                               f"{YUM_CLEAN_ALL}'{ACCESS}", shell=True)										   #client
  except:
     LOG.warn("\nINFO Cache directories do not exist\n")

def yum_remove_dvd():
  LOG.debug("\n*ENGINEERING MODE* INFO - Remove dvd")
  remove_dvd = "rm -rf /etc/yum.repos.d/*dvd*"
  try:
     yum_clean = sub_proc_display(f"ansible all -i {HOST_PATH} -m shell -a '"
                               f"{remove_dvd}'{ACCESS}", shell=True)										   #client
  except:
     LOG.warn("\nINFO failed to remove dvd\n")

def do_yum_remove_dvd_packages():
  LOG.debug("\n*ENGINEERING MODE* INFO - Remove dvd")
  remove_dvd = 'yum remove -y $(yum list installed | grep "@*-dvd" | awk "{ print $1 }") '
  try:
     yum_clean = sub_proc_display(f"ansible all -i {HOST_PATH} -m shell -a '"
                               f"{remove_dvd}'{ACCESS}", shell=True)										   #client
  except:
     LOG.warn("\nINFO failed to remove dvd packages\n")

def parse_ansible_output(output):
    pass

def do_run_ansible_cmd(cmd):
    output = ""
    cmd = f"{ANSIBLE_PREFIX} '{cmd}' {ACCESS}" 
    print("\nRunning: {0}".format(cmd))
    try:
        output = bash_cmd(cmd)										   #client
        LOG.info("\nOutput:\n{0}".format(output))
    except Exception as e :
         LOG.error("\nINFO failed to run {0}\n{1}".format(cmd,e))
    return output

def do_rpm_list_packages(hosts):
    LOG.debug("\n*ENGINEERING MODE* INFO - Remove dvd")
    cmd = 'list_date=$(date "+%Y.%m.%d-%H.%M.%S");rpm -qa --last > list"_"$list_date; cat list"_"$list_date'
    do_run_ansible_cmd(cmd)

def do_base_system_install(hosts):
    LOG.debug("\n*ENGINEERING MODE* INFO - Remove dvd")
    cmd = 'sudo rpm -qi basesystem | grep Install'
    output  = do_run_ansible_cmd(cmd)
    print(output)

def do_remove_yum_dvd_repo():
    yum_remove_dvd()

redhat_subscription =  '''- name: Create Red Hat Registration 
  hosts: "{{ variable_host | default('') }}" 
  tasks:
    - name: Get RedHat Subscription Manager on Node rhsm.sh script
      shell:  "wget --no-check-certificate --user='{0}' --password='{1}' -O /tmp/ibm-rhsm.sh https://ftp3.linux.ibm.com/dl.php?file=/redhat/ibm-rhsm.sh"
    - name: Run  rhsm.sh  script
      shell: "bash /tmp/ibm-rhsm.sh"
      become: True
      environment:
        FTP3USER: '{2}'
        FTP3PASS: '{3}'
        FTP3FORCE: y'''

def do_public_setup(hosts):
    # ip route add default via  192.168.65.3
    # setup network script to static
    #    DEVICE=eth15
     #  TYPE=Ethernet
     #  BOOTPROTO=none
     #  ONBOOT=yes
     #  IPADDR=192.168.65.21
     #  PREFIX=24
     #  GATEWAY=192.168.65.3
     #  NM_CONTROLLED=no
     #  DEFROUTE=yes
     #  ZONE=public
    # setup redhat license
    # add to /etc/hosts 
    #   192.168.65.21 server-1
    #change hostname to server-1 
    #   hostnamectl set-hostname server-1
    # install nfs-utils
    # remove dvd iso repo
    #   sudo rm -rf /etc/yum.repos.d/*dvd*
    # add conda defaults to .condarc
    # pypi repo set to output repo by removing  --index-url http://{{ host_ip.stdout }}/repos/pypi/simple
    # and --trusted-host {{ host_ip.stdout }} 
     # make direcoroy
     #  sudo mkdir -p /nfs/pwrai
     # 
     # setup fstab to persist
     # (make sure the owner matches the current user (not root)
     # The owner of /nfs/pwrai  and it's subdirectories should now be nfsnobody, 
     # the owner of directories under pwrai  (ie rh) should be the local user)
     # 
     #   echo "9.3.89.51:/media/shnfs_sdo/nfs/pwrai  /nfs/pwrai  nfs nolock,acl,rsize=8192,wsize=8192,timeo=14,intr,nfsvers=3 0 0" | sudo tee --append /etc/fstab
    pass

def do_private_setup(hosts):
    # remove ip route add default via  192.168.65.3
    # setup network script to static
    #    DEVICE=eth15
     #  TYPE=Ethernet
     #  BOOTPROTO=none
     #  ONBOOT=yes
     #  IPADDR=192.168.65.21
     #  PREFIX=24
     #  GATEWAY=192.168.65.3
     #  NM_CONTROLLED=no
     #  DEFROUTE=yes
     #  ZONE=public
    # setup redhat license
    # add to /etc/hosts 
    #   192.168.65.21 server-1
    #change hostname to server-1 
    #   hostnamectl set-hostname server-1
    # install nfs-utils
    # add  dvd iso repo
    #   sudo rm -rf /etc/yum.repos.d/*dvd*
    # add conda defaults to .condarc
    # pypi repo set to output repo by removing  --index-url http://{{ host_ip.stdout }}/repos/pypi/simple
    # and --trusted-host {{ host_ip.stdout }} 
     # make direcoroy
     #  sudo mkdir -p /nfs/pwrai
     # 
     # setup fstab to persist
     # (make sure the owner matches the current user (not root)
     # The owner of /nfs/pwrai  and it's subdirectories should now be nfsnobody, 
     # the owner of directories under pwrai  (ie rh) should be the local user)
     # 
     #   echo "9.3.89.51:/media/shnfs_sdo/nfs/pwrai  /nfs/pwrai  nfs nolock,acl,rsize=8192,wsize=8192,timeo=14,intr,nfsvers=3 0 0" | sudo tee --append /etc/fstab
    pass

def do_run_redhat_sub(hosts):
    # todo get input from user
    runfile = tempfile.NamedTemporaryFile() 
    subscribe = redhat_subscription.format('',
                                           '', 
                                           '',
                                           '')
    print(f"{runfile.name}")
    with open(runfile.name,'w') as f:
        f.write(subscribe)
    output = bash_cmd(f"ansible-playbook {runfile.name} --extra-vars=\"variable_host={0}\" '{ACCESS}'".format(hosts))
    print(output)
def get_cmd_install_rhel_repos():
    name =  "Install Rhell Rhepos"
    cmd = 'sudo yum install https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm && sudo subscription-manager repos --enable "rhel-*-optional-rpms"\
        --enable "rhel-*-extras-rpms"  --enable "rhel-ha-for-rhel-*-server-rpms"'
    return cmd,name
def do_install_rhel_repos(hosts):
    LOG.debug("Install Rhel Public Repos")
    cmd,name = get_cmd_install_rhel_repos()
    output  = do_run_ansible_cmd(cmd)
    print(output)

def file_collecter(file_name,process):

  #current_user    = input("Enter current user: ")
  #client_user     = input("Enter client user: ")
  #client_hostname = input("Enter client hostname or IP: ")

  current_user    = 'jja'
  client_user     = 'rhel76'
  client_hostname = 'server-1'

  print (f"\n*ENGINEERING MODE* INFO - Current user: {current_user}\n")

  remote_access   = f"{client_user}@{client_hostname}"
  remote_location = f"/home/{client_user}/"
  dbfile          = f"{file_name}"
  local_dir       = DEPENDENCIES_PATH

  data_copy_cmd  = f'scp -r {remote_access}:{remote_location}{dbfile} {local_dir}'

  yum_file_format    = " | sed 1,2d | xargs -n3 | column -t > "
  conda_file_format = " | sed 1,3d >"
  function = dbfile.split('_',4)[1]

  if (function == 'yum'):
     ansible_cmd = f"{ANSIBLE_PREFIX}'{process}{yum_file_format}{file_name}'"
  elif (function == 'conda'):
      ansible_cmd = (f"{ANSIBLE_PREFIX}'{process}{conda_file_format}{file_name}'"
                     f"{ACCESS}")
  else:
     ansible_cmd = f"{ANSIBLE_PREFIX}'{process} > {file_name}'{ACCESS}"

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

def yum_list_installed():
    LOG.info("Running yum list installed")
    yum_clean_cache()

    file_collecter(file_name="client_yum_pre_install.txt",
             process="yum list installed")

    file_collecter(file_name="client_pip_pre_install.txt",  #N/A x86 Andaconda/7.6
             process="touch client_pip_pre_install.txt")

def complete_system_setup():
                                # Clean Cache
    conda_clean_cache()
                                                                        #dlipy3_env
    # Create dlipy3 test environment

    print (f"\n*ENGINEERING MODE* INFO - Creating dlipy3_test environment\n")
    sub_proc_display(f"ansible all -i {HOST_PATH} -m shell -a "
               "'/opt/anaconda3/bin/conda "
               "create --name dlipy3_test --yes pip python=3.6'"
               f"{ACCESS}",
               shell=True)

    # Activate dlipy3_test and gather pre pip_list
    file_collecter(file_name='dlipy3_pip_pre_install.txt',
             process='source /opt/anaconda3/bin/activate dlipy3_test && '
                     '/opt/anaconda3/envs/dlipy3_test/bin/pip list')

    # Activate dlipy3_test env and gather pre conda_list
    file_collecter(file_name='dlipy3_conda_pre_install.txt',
             process='source /opt/anaconda3/bin/activate dlipy3_test && '
                     'conda list --explicit')

                                                                        #dlipy2_env
    # Create dlipy2_test environment
    print (f"\n*ENGINEERING MODE* INFO - Creating dlipy2_test environment\n")
    sub_proc_display(f"ansible all -i {HOST_PATH} -m shell -a "
               "'/opt/anaconda3/bin/conda "
               "create --name dlipy2_test --yes pip python=2.7'"
               f"{ACCESS}",
               shell=True)

    # Activate dlipy2_test env and gather pre pip_list
    file_collecter(file_name='dlipy2_pip_pre_install.txt',
             process='source /opt/anaconda3/bin/activate dlipy2_test && '
                     '/opt/anaconda3/envs/dlipy2_test/bin/pip list')

    # Activate dlipy2_test env and gather pre conda_list
    file_collecter(file_name='dlipy2_conda_pre_install.txt',
             process='source /opt/anaconda3/bin/activate dlipy2_test && '
                     'conda list --explicit')

                                #dlinsights_env

    # Activate dlinsights and gather pre pip_list  (Note:python 2.7 env to use as refrence)
    file_collecter(file_name='dlinsights_pip_pre_install.txt',
             process='source /opt/anaconda3/bin/activate dlipy2_test && '
                     '/opt/anaconda3/envs/dlipy3_test/bin/pip list')

    # Activate dlinsights env and gather pre conda_list
    file_collecter(file_name='dlinsights_conda_pre_install.txt',
             process='source /opt/anaconda3/bin/activate dlipy2_test && '
                     'conda list --explicit')


def configure_spectrum_conductor():
										#post_dlipy3
    # Activate dlipy3 and gather post pip_list
    file_collecter(file_name='dlipy3_pip_post_install.txt',
             process='source /opt/anaconda3/bin/activate dlipy3 && '
                     '/opt/anaconda3/envs/dlipy3/bin/pip list')

    # Activate dlipy3 env and gather post conda_list
    file_collecter(file_name='dlipy3_conda_post_install.txt',
             process='source /opt/anaconda3/bin/activate dlipy3 && '
                     'conda list --explicit')

                                                                        #post_dlipy2
    # Activate dlipy2 and gather post pip_list
    file_collecter(file_name='dlipy2_pip_post_install.txt',
             process='source /opt/anaconda3/bin/activate dlipy2 && '
                     '/opt/anaconda3/envs/dlipy2/bin/pip list')

    # Activate dlipy2 and gather post conda_list
    file_collecter(file_name='dlipy2_conda_post_install.txt',
             process='source /opt/anaconda3/bin/activate dlipy2 && '
                     'conda list --explicit')

                               #post_dlinsights
    # Activate dlinsights and gather post pip_list
    file_collecter(file_name='dlinsights_pip_post_install.txt',
             process='source /opt/anaconda3/bin/activate dlinsights && '
                     '/opt/anaconda3/envs/dlinsights/bin/pip list')

    # Activate dlinsights env and gather post conda_list
    file_collecter(file_name='dlinsights_conda_post_install.txt',
             process='source /opt/anaconda3/bin/activate dlinsights && '
                     'conda list --explicit')
def do_call_file_collector(args):
    soft_type = args.soft_type 
    environment = args.environment 
    at_time = args.at_time 
    command = f"{environment} list"
    if environment == "conda":
        command = command + " --explicit"
    else:
        pippath = "/opt/anaconda3/envs/{soft_type}/bin/"
        comand = pippath + command

    file_collecter(file_name=f'{soft_type}_{environment}_{at_time}_install.txt',
             process=f'source /opt/anaconda3/bin/activate {soft_type} && '
                     f'{command}')

def powerai_tunning():
    # Gather post yum list from client
    file_collecter(file_name='client_yum_post_install.txt',
             process='yum list installed')

    # Gather post pip_list from client
    file_collecter(file_name='client_pip_post_install.txt',
             process='/opt/anaconda3/bin/pip list')

def do_yum_list_installed(hosts):
    yum_list_installed()

def do_complete_system_setup(hosts):
    complete_system_setup()

def do_configure_spectrum_conductor(hosts):
    configure_spectrum_conductor()

def do_powerai_tunning(hosts):
    powerai_tunning()

def pre_post_file_collect(task):

   tasks_list = [
                 'yum_update_cache.yml'
                 ]
   if (task in tasks_list):
       yum_list_installed()
   elif (task == 'complete_system_setup.yml'):
       complete_system_setup()
   elif (task == 'configure_spectrum_conductor.yml'):
       configure_spectrum_conductor()
   elif (task=='powerai_tuning.yml'):
       powerai_tunning()

def parse_input(args):
    parser = argparse.ArgumentParser(description="Utility for retreiving\
                                     PowerAIE Packages for air gapped environment")
    subparsers = parser.add_subparsers()

    def add_subparser(cmd, cmd_help, args=None):
        sub_parser = subparsers.add_parser(cmd, help=cmd_help)
        if args is None:
            sub_parser.set_defaults(func=globals()[cmd])
        else:
            for arg, arg_help, required, in args:
                sub_parser.add_argument("--" + arg,
                                        help=arg_help, required=required,
                                        type=globals()["validate_" + arg])
            sub_parser.set_defaults(func=globals()["do_"+cmd])

        sub_parser.add_argument('-ll', '--loglevel', type=str,
                                choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                                default="INFO",
                                help='Set the logging level')

    add_subparser('yum_clean', "run yum clean on all the hosts",
                  [('hosts', 'hosts file path', False)])

    add_subparser('conda_clean', "run conda clean on all the hosts",
                  [('hosts', 'hosts file path', False)])
    add_subparser('yum_list_installed', "run yum list insalled on all the hosts",
                  [('hosts', 'hosts file path', False)])
    add_subparser('remove_yum_dvd_repo', "run yum list insalled on all the hosts",
                  [('hosts', 'hosts file path', False)])
    add_subparser('rpm_list_packages', "run yum list insalled on all the hosts",
                  [('hosts', 'hosts file path', False)])
    add_subparser('base_system_install', "run yum list insalled on all the hosts",
                  [('hosts', 'hosts file path', False)])

    add_subparser('complete_system_setup', "run yum list insalled on all the hosts",
                  [('hosts', 'hosts file path', False)])
    add_subparser('configure_spectrum_conductor', "run yum list insalled on all the hosts",
                  [('hosts', 'hosts file path', False)])
    add_subparser('powerai_tunning', "run yum list insalled on all the hosts",
                  [('hosts', 'hosts file path', False)])

    add_subparser('run_redhat_sub', "run redhat subscription",
                  [('hosts', 'hosts file path', False)])
    add_subparser('install_rhel_repos', "run install rhel repos on hosts",
                  [('hosts', 'hosts file path', False)])
    add_subparser('call_file_collector', "call file collector",
                  [('soft_type', 'dlipy2, dlipy3, dlinsights', True),
                    ('environment', 'pip or conda', True),
                    ('at_time', 'pre or post', True)
                   ])

    #  add_subparser('bundle', "Bundle Paie software, assume bundle from /srv directory",
                  #  [('to', 'bundle paie software to?', True)])
#
    #  subparsers.choices['bundle'].add_argument('--compress', dest="compress",
                                              #  required=False, action="store_true",
                                              #  help='compress using gzip')
#
    #  add_subparser('extract_bundle', "Extract bundle Paie software assume to /srv",
                  #  [('from_archive', 'from which archive to extract paie software?', True)])

    if not args:
        parser.print_help()
        sys.exit(RC_ARGS)
    args = parser.parse_args(args)

    if STANDALONE is True:
        LOG.setLevel(args.loglevel)
    return args

def validate_exists(name, path):
    if not os.path.exists(path):
        exit(RC_ARGS, "{1} does not exist ({0})".format(path, name))
    LOG.debug("{1} = {0}".format(path, name))
    return path

def validate_values(envs, environment):
    if environment not in envs:
        LOG.debug("{1} != {0}".format(environment, " ".join(envs)))
        exit(RC_ARGS, "Only options are: ".format(" ".join(envs)))
    return environment

def validate_environment(environment):
    envs = ["pip", "conda"]
    return validate_values(envs, environment)

def validate_at_time(at_time):
    return validate_values(["post", "pre"],at_time) 

def validate_soft_type(soft_type):
    return validate_values(['dlinsights',"dlipy2", "dlipy3"],soft_type) 

def validate_hosts(hosts):
    if not hosts:
        LOG.info( "{1} does not exist ({0})".format(hosts, 'hosts'))
        hosts = HOST_PATH 
    LOG.debug("{1} = {0}".format(hosts, name))
    return validate_exits("hosts", hosts)

def do_yum_clean(hosts):
    HOST_PATH = hosts
    yum_clean_cache()
def do_conda_clean(hosts):
    conda_clean_cache()

def setup_logging(debug="INFO"):
    '''
    Method to setup logging based on debug flag
    '''
    LOG.setLevel(debug)
    formatString = '%(asctime)s - %(levelname)s - %(message)s'
    ch = logging.StreamHandler()
    formatter = logging.Formatter(formatString)
    ch.setFormatter(formatter)
    LOG.addHandler(ch)
    #  setup file handler
    rfh = logging.FileHandler(filename=LOGFILE)
    rfh.setFormatter(logging.Formatter(formatString))
    LOG.addHandler(rfh)

def main(args):
    """Wmla run ansible package retriever environment"""
    try:
        parsed_args = parse_input(args)
        LOG.info("Running operation '%s'", ' '.join(args))
        parsed_args.func(parsed_args)
        exit(RC_SUCCESS, "Operation %s completed successfully" % args[0])
    except KeyboardInterrupt as k:
        exit(RC_USER_EXIT, "Exiting at user request ... {0}".format(k))


if __name__ == "__main__":
    STANDALONE = True 
    main(sys.argv[1:])
