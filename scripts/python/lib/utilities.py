# Copyright 2019 IBM Corp.
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

from glob import glob
import os
import re
import sys
import datetime
import subprocess
import fileinput
import readline
from shutil import copy2, copyfile
from subprocess import Popen, PIPE
from netaddr import IPNetwork, IPAddress, IPSet
from tabulate import tabulate
from textwrap import dedent
import hashlib
from distro import linux_distribution

from lib.config import Config
import lib.logger as logger
from lib.exception import UserException

PATTERN_DHCP = r"^\|_*\s+(.+):(.+)"
PATTERN_MAC = r'([\da-fA-F]{2}:){5}[\da-fA-F]{2}'
PATTERN_IP = (r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
              r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$')
PATTERN_EMBEDDED_IP = (r'(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
                       r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)')

CalledProcessError = subprocess.CalledProcessError

LOG = logger.getlogger()
DHCP_SERVER_CMD = "sudo nmap --script broadcast-dhcp-discover -e {0}"


def parse_dhcp_servers(nmap_response):
    """ parse nmap output response

    Args:
        nmap_response (str): Output of nmap --script broadcast-dhcp-discover -e

    Returns:
        data (dict): dictionary parsed from data

        {'Broadcast Address': '192.168.12.255',
        'DHCP Message Type': 'DHCPOFFER',
        'Domain Name Server': '192.168.12.2',
        'IP Address Lease Time: 0 days, 0:02': '00',
        'IP Offered': '192.168.12.249',
        'Rebinding Time Value: 0 days, 0:01': '45',
        'Renewal Time Value: 0 days, 0:01': '00',
        'Router': '192.168.12.3',
        'Server Identifier': '192.168.12.2',
        'Subnet Mask': '255.255.255.0',
        'broadcast-dhcp-discover': ''}
    """
    matches = re.findall(PATTERN_DHCP, nmap_response, re.MULTILINE)
    data = {a: b.strip() for a, b in matches}
    return data


def get_dhcp_servers(interface):
    """ get dhcp servers by running nmap

    Args:
        interface (str): interface to query for dhcp servers

    Returns:
        output (str): string output of command
    """
    cmd = DHCP_SERVER_CMD.format(interface)
    output = ""
    data = None
    try:
        output = bash_cmd(cmd)
    except Exception as e:
        LOG.error("{0}".format(e))
        raise e
    else:
        data = parse_dhcp_servers(output)
    return data


def has_dhcp_servers(interface):
    """ does interface have dhcp servers

    Args:
        interface (str): interface to query for dhcp servers

    Returns:
         isTrue (int): true or false
    """
    try:
        dct = get_dhcp_servers(interface)
        return 'DHCPOFFER' in dct['DHCP Message Type']
    except:
        pass
    return False


def scan_subnet(cidr):
    """Scans a subnet for responding devices.
    Args:
        cidr (str): subnet in cidr format or can be list of ips separated by
                    spaces
    """
    cmd = f'sudo nmap -sn {cidr}'
    res, err, rc = sub_proc_exec(cmd)
    items = []
    if rc != 0:
        LOG.error(f'Error while scanning subnet {cidr}, rc: {rc}')
    for line in res.split('Nmap scan report'):
        match = re.search(PATTERN_EMBEDDED_IP, line)
        if match:
            ip = match.group(0)
            match2 = re.search(PATTERN_MAC, line)
            if match2:
                mac = match2.group(0)
            else:
                mac = ''
            items += [(ip, mac)]
    return items


def scan_subnet_for_port_open(cidr, port):
    """Scans a subnet for responding devices.
    Args:
        cidr (str or list): subnet in cidr format or can be list of ips
                            separated by spaces.
        port (str or int) : tcp port to check
    """
    if isinstance(cidr, list):
        cidr = ' '.join(cidr)
    cmd = f'sudo nmap -p {port} {cidr}'
    res, err, rc = sub_proc_exec(cmd)
    items = []
    if rc != 0:
        LOG.error(f'Error while scanning subnet {cidr}, rc: {rc}')
    for line in res.split('Nmap scan report'):
        match = re.search(PATTERN_EMBEDDED_IP, line)
        if match:
            ip = match.group(0)
            match2 = re.search(r'\d+/tcp\s+open.+' + rf'({PATTERN_MAC})', line,
                               re.DOTALL)
            if match2:
                mac = match2.group(1)
                if match2:
                    items += [(ip, mac)]
    return items


def is_ipaddr(ip):
    if re.search(PATTERN_IP, ip):
        return True


def is_netmask(mask):
    from netaddr import AddrFormatError
    try:
        if IPAddress(mask).is_netmask():
            res = True
        else:
            res = False
    except AddrFormatError:
        res = False

    return res


def get_network_addr(ipaddr, prefix):
    """ Return the base address of the subnet in which the ipaddr / prefix
        reside.
    """
    return str(IPNetwork(f'{ipaddr}/{prefix}').network)


def get_netmask(prefix):
    return str(IPNetwork(f'0.0.0.0/{prefix}').netmask)


def get_prefix(netmask):
    return IPAddress(netmask).netmask_bits()


def get_network_size(cidr):
    """ return the decimal size of the cidr address
    """
    return IPNetwork(cidr).size


def add_offset_to_address(addr, offset):
    """calculates an address with an offset added. offset can be negative.
    Args:
        addr (str): ipv4 or cidr representation of address
        offset (int): integer offset
    Returns:
        addr_.ip (str) address in ipv4 representation
    """
    addr_ = IPNetwork(addr)
    addr_.value += offset
    return str(addr_.ip)


def is_overlapping_addr(subnet1, subnet2):
    """ Checks if two ipv4 subnets are overlapping
    Inputs:
        subnet1,subnet2 (str) ipv4 subnet in cidr format
    Returns:
        True if the two subnets overlap, False if they do not.
    """
    if IPSet([subnet1]).intersection(IPSet([subnet2])):
        return True
    else:
        return False


def bash_cmd(cmd):
    """Run command in Bash subprocess

    Args:
        cmd (str): Command to run

    Returns:
        output (str): stdout from command
    """
    log = logger.getlogger()
    _cmd = ['bash', '-c', cmd]
    log.debug('Run subprocess: %s' % ' '.join(_cmd))
    output = subprocess.check_output(_cmd, universal_newlines=True,
                                     stderr=subprocess.STDOUT)
    try:
        output = output.decode('utf-8')
    except AttributeError:
        pass
    log.debug(output)

    return output


def backup_file(path, suffix='.orig', multi=True):
    """Save backup copy of file

    Backup copy is saved as the name of the original with the value of suffix
    appended. If multi is True, and a backup already exists, an additional
    backup is made with a numeric index value appended to the name. The backup
    copy filemode is set to read-only.

    Args:
        path (str): Path of file to backup
        suffix (str): String to append to the filename of the backup
        multi (bin): Set False to only make a backup if one does not exist
            already.
    """
    log = logger.getlogger()
    backup_path = path + suffix
    version = 0
    while os.path.exists(backup_path) and multi:
        version += 1
        backup_path += "." + str(version)
    log.debug('Make backup copy of orignal file: \'%s\'' % backup_path)
    copy2(path, backup_path)
    os.chmod(backup_path, 0o444)


def append_line(path, line, check_exists=True):
    """Append line to end of text file

    Args:
        path (str): Path of file
        line (str): String to append
        check_exists(bool): Check if line exists before appending
    """
    log = logger.getlogger()
    log.debug('Add line \'%s\' to file \'%s\'' % (line, path))

    if not line.endswith('\n'):
        line += '\n'

    exists = False
    if check_exists:
        with open(path, 'r') as file_in:
            for read_line in file_in:
                if read_line == line:
                    exists = True

    if not exists:
        with open(path, 'a') as file_out:
            file_out.write(line)


def remove_line(path, regex):
    """Remove line(s) from file containing a regex pattern

    Any lines matching the regex pattern will be removed.

    Args:
        path (str): Path of file
        regex (str): Regex pattern
    """
    log = logger.getlogger()
    log.debug('Remove lines containing regex \'%s\' from file \'%s\'' %
              (regex, path))
    for line in fileinput.input(path, inplace=1):
        if not re.match(regex, line):
            print(line, end='')


def line_in_file(path, regex, replace, backup=None):
    """If 'regex' exists in the file specified by path, then replace it with
    the value in 'replace'. Else append 'replace' to the end of the file. This
    facilitates simplified changing of a parameter to a desired value if it
    already exists in the file or adding the paramater if it does not exist.
    Inputs:
        path (str): path to the file
        regex (str): Python regular expression
        replace (str): Replacement string
        backup (str): If specified, a backup of the orginal file will be made
            if a backup does not already exist. The backup is made in the same
            directory as the original file by appending the value of backup to
            the filename.
    """
    if os.path.isfile(path):
        if backup:
            backup_file(path, multi=False)
        try:
            with open(path, 'r') as f:
                data = f.read()
        except FileNotFoundError as exc:
            print(f'File not found: {path}. Err: {exc}')
        else:
            data = data.splitlines()
            in_file = False
            # open 'r+' to maintain owner
            with open(path, 'r+') as f:
                for line in data:
                    in_line = re.search(regex, line)
                    if in_line:
                        line = re.sub(regex, replace, line)
                        in_file = True
                    f.write(line + '\n')
                if not in_file:
                    f.write(replace + '\n')


def replace_regex(path, regex, replace):
    """Replace line(s) from file containing a regex pattern

    Any lines matching the regex pattern will be removed and replaced
    with the 'replace' string.

    Args:
        path (str): Path of file
        regex (str): Regex pattern
        replace (str): String to replace matching line
    """
    log = logger.getlogger()
    log.debug('Replace regex \'%s\' with \'%s\' in file \'%s\'' %
              (regex, replace, path))
    for line in fileinput.input(path, inplace=1):
        print(re.sub(regex, replace, line), end='')


def copy_file(source, dest, metadata=True):
    """Copy a file to a given destination

    Args:
        source (str): Path of source file
        dest (str): Destination path to copy file to
        metadata (bool, optional): Attempt to preserve file metadata
    """
    log = logger.getlogger()
    log.debug(f'Copy file, source:{source} dest:{dest} metadata:{metadata}')
    if metadata:
        copy2(source, dest)
    else:
        if os.path.isdir(dest):
            basename = os.path.basename(source)
            dest = os.path.join(dest, basename)
        copyfile(source, dest)


def sub_proc_launch(cmd, stdout=PIPE, stderr=PIPE):
    """Launch a subprocess and return the Popen process object.
    This is non blocking. This is useful for long running processes.
    """
    proc = Popen(cmd.split(), stdout=stdout, stderr=stderr)
    return proc


def sub_proc_exec(cmd, stdout=PIPE, stderr=PIPE, shell=False, env=None):
    """Launch a subprocess wait for the process to finish.
    Returns stdout from the process
    This is blocking
    """
    if not shell:
        cmd = cmd.split()
    proc = Popen(cmd, stdout=stdout, stderr=stderr, shell=shell, env=env)
    stdout, stderr = proc.communicate()
    try:
        stdout = stdout.decode('utf-8')
    except AttributeError:
        pass
    try:
        stderr = stderr.decode('utf-8')
    except AttributeError:
        pass
    return stdout, stderr, proc.returncode


def sub_proc_display(cmd, stdout=None, stderr=None, shell=False, env=None):
    """Popen subprocess created without PIPES to allow subprocess printing
    to the parent screen. This is a blocking function.
    """
    if not shell:
        cmd = cmd.split()
    proc = Popen(cmd, stdout=stdout, stderr=stderr, shell=shell, env=env)
    proc.wait()
    rc = proc.returncode
    return rc


def sub_proc_wait(proc):
    """Launch a subprocess and display a simple time counter while waiting.
    This is a blocking wait. NOTE: sleeping (time.sleep()) in the wait loop
    dramatically reduces performace of the subprocess. It would appear the
    subprocess does not get it's own thread.
    """
    cnt = 0
    rc = None
    while rc is None:
        rc = proc.poll()
        print('\rwaiting for process to finish. Time elapsed: {:2}:{:2}:{:2}'.
              format(cnt // 3600, cnt % 3600 // 60, cnt % 60), end="")
        sys.stdout.flush()
        cnt += 1
    print('\n')
    resp, err = proc.communicate()
    print(resp)
    return rc


class Color:
    black = '\033[90m'
    red = '\033[91m'
    green = '\033[92m'
    yellow = '\033[33m'
    brt_yellow = '\033[93m'
    blue = '\033[94m'
    purple = '\033[95m'
    cyan = '\033[96m'
    white = '\033[37m'
    brt_white = '\033[97m'
    bold = '\033[1m'
    underline = '\033[4m'
    sol = '\033[1G'
    clr_to_eol = '\033[K'
    clr_to_bot = '\033[J'
    scroll_five = '\n\n\n\n\n'
    scroll_ten = '\n\n\n\n\n\n\n\n\n\n'
    up_one = '\033[1A'
    up_five = '\033[5A'
    up_ten = '\033[10A'
    header1 = '          ' + bold + underline
    endc = '\033[0m'


def heading1(text='-', width=79, indent=10):
    ind = ''.join([' ' for i in range(indent)])
    text1 = f'{ind}{Color.bold}{Color.underline}{text}{Color.endc}'
    print(f'\n{text1: <{width + 8}}')


def bold(text):
    return Color.bold + text + Color.endc


def rlinput(prompt, prefill=''):
    readline.set_startup_hook(lambda: readline.insert_text(prefill))
    try:
        return input(prompt)
    finally:
        readline.set_startup_hook()


def files_present(url, fileglobs, _all=True):
    """Return true if any/all of the fileglobs are present in the url.
    """
    any_present = False
    all_present = True
    fileglobsstr = ','.join(fileglobs)
    if fileglobs:
        cmd = (f'wget -r -l 10 -nd -np --spider --accept={fileglobsstr} {url}')
        reply, err, rc = sub_proc_exec(cmd)
        err = err.replace('%2B', '+')
        if rc == 0:
            for fileglob in fileglobs:
                regx = fileglob_to_regx(fileglob)
                res = re.findall(regx, err)
                any_present = any_present or res != []
                all_present = all_present and res != []
    if not fileglobs:
        return True
    if _all:
        return all_present
    else:
        return any_present


def fileglob_to_regx(fileglob):
    regx = fileglob.replace('.', r'\.')
    regx = regx.replace('+', r'\+')
    regx = regx.replace(']*', '][0-9]{0,3}')
    regx = regx.replace('*', '.*')
    regx = 'http.+' + regx
    return regx


def get_url(url='http://', fileglob='', prompt_name='', repo_chk='',
            contains=[], excludes=[], filelist=[]):
    """Input a URL from user. The URL is checked for validity using curl and
    wget and the user can continue modifying it indefinitely until a response
    is obtained or he can enter 'sss' to skip (stop) entry.

    If a fileglob is specified, the specified url is searched
    recursively (crawled) up to 10 levels deep looking for matches.

    If repo_chk is specified, the url is searched recursively looking for a
    marker specific to that repo type. If multiple URL's are found, the
    list of found url's is filtered using 'contains', 'excludes' and
    'files_present'. The user is again prompted to make a selection.

    fileglob and repo_chk are mutually exclusive.

    If neither fileglob nor repo_chk are specified, and the url does not end
    in '/' then the url is assumed to be looking for a file.

    Inputs:
        url (str). Valid URLs are http:, https:, and file:
        fileglob (str) standard linux fileglobs with *, ? or []
        repo_chk (str) 'yum', 'ana' or 'pypi'
        contains (list of strings) Filter criteria to be used in combination
            with repo_chk. After finding repos of the type in 'repo_chk', the
            list is restricted to those urls that contain elements from
            'contains' and no elements of 'excludes'.
        excludes (list of strings)
        filelist (list of strings) Can be globs. Used to validate a repo. The
            specified files must be present
        prompt_name (str) Used for prompting only.
    Output:
        url (str) URL for one file or repository directory
    """
    from lib.genesis import GEN_SOFTWARE_PATH
    print(f'Enter {prompt_name} URL. ("sss" at end of URL to skip)')
    if fileglob:
        print('Do not include filenames in the URL. A search of the URL')
        print('will be made up to 10 levels deep')
    while True:
        url = rlinput(f'Enter URL: ', url)
        if url.endswith('sss'):
            url = None
            break

        if 'artifactory.swg' in url:
            fnd_creds = False
            while not fnd_creds:
                path = os.path.join(GEN_SOFTWARE_PATH, 'artifactory.credentials')
                if os.path.isfile(path):
                    with open(path, 'r') as f:
                        creds = f.read().rstrip('\n')
                        fnd_creds = True
                else:
                    print('No artifactory credentials file found')
                    r = get_selection('Retry\nTerminate Sofware install',
                                      ('R', 'T'))
                    if r == 'T':
                        sys.exit('PowerUp software install terminated by user')
            url = f'https://{creds}{url}'
            break

        if repo_chk:
            url = url if url.endswith('/') else url + '/'
        try:
            # Basic response test
            cmd = f'curl --max-time 2 -I {url}'
            url_info, err, rc = sub_proc_exec(cmd)
        except:
            pass
        else:
            if 'http:' in url or 'https:' in url:
                response = re.search(r'HTTP\/\d+.\d+\s+200\s+ok', url_info,
                                     re.IGNORECASE)
                if response:
                    repo_mrkr = {'yum': '/repodata/', 'ana': 'repodata.json',
                                 'pypi': '/simple/'}
                    print(response.group(0))
                    if repo_chk:
                        ss = repo_mrkr[repo_chk]
                    elif fileglob:
                        ss = fileglob
                    elif url[-1] != '/':
                        ss = os.path.basename(url)
                        url = os.path.dirname(url)
                    cmd = ('wget -r -l 10 -nd -np --spider '
                           f'--accept={ss} {url}')
                    reply, err, rc = sub_proc_exec(cmd)
                    err = err.replace('%2B', '+')
                    if rc == 0:
                        if repo_chk:
                            regx = 'http.+' + repo_mrkr[repo_chk]
                        elif fileglob:
                            regx = fileglob_to_regx(fileglob)
                        _found = re.findall(regx, err)
                        # remove dups
                        _found = list(set(_found))

                        found = []
                        # Include items containing any element of 'contains'
                        # and exclude items containing any element of
                        # 'excludes' If no item meets criteria, then use
                        # any / all items but include a warning.
                        if repo_chk:
                            for _url in _found:
                                if (any([item for item in contains if item in
                                         _url]) and not any([item for item in
                                                             excludes if item
                                                             in _url])):
                                    found.append(_url)

                        if found:
                            _list = found
                        elif _found:
                            _list = _found
                            if repo_chk:
                                print(bold('\nWarning. The following url(s) '
                                           'were found but do not match the '
                                           'search criteria'))
                        else:
                            _list = []
                        if _list:
                            ch, sel = get_selection(_list, allow_none=True)
                            if ch != 'N':
                                if repo_chk:
                                    sel = sel.rstrip('/')
                                    url = os.path.dirname(sel)
                                    if files_present(url, filelist):
                                        break
                                    else:
                                        print('\nChosen URL does not appear '
                                              'to be valid. File check '
                                              'failed.')
                                        if get_yesno('Use selection anyway'):
                                            break
                                else:
                                    url = sel
                                    break

                        else:
                            print('No match found.')
                    else:
                        print(f'Error reading url.  {reply}')

                else:
                    print('Invalid url')
                    err = re.search('curl: .+', err)
                    if err:
                        print(err.group(0))
                    tmp = re.search(r'HTTP\/\d+.\d+\s+.+', url_info)
                    if tmp:
                        print(tmp.group(0))

            elif 'file:///' in url:
                response = re.search(r'Content-Length:\s+\d+', url_info)
                if response:
                    if repo_chk == 'yum':
                        ss = '/repodata'
                    elif repo_chk == 'ana':
                        ss = '/repodata.json'
                    elif repo_chk == 'pypi':
                        ss = '/simple'
                    if repo_chk:
                        ss = url + ss
                    elif fileglob:
                        ss = url + fileglob
                    ss = '/' + ss.lstrip('file:/')
                    files = glob(ss, recursive=True)

                    if files:
                        ch, sel = get_selection(files, allow_none=True)
                        if ch != 'N':
                            url = 'file://' + os.path.dirname(sel) + '/'
                            break
                    else:
                        print('No match found.')

            elif 'file:' in url:
                print('Proper file url format: "file:///path/to/file')
                response = ''
            else:
                response = ''
    return url


def get_yesno(prompt='', yesno='y/n', default=''):
    r = ' '
    yn = yesno.split('/')
    while r not in yn:
        r = rlinput(f'{prompt}({yesno})? ', default)
    if r == yn[0]:
        return True
    return False


def get_dir(src_dir):
    """Interactive selection of a source dir. Searching starts in the cwd.
    Returns:
        path (str or None) : Selected path
    """
    rows = 10
    if not src_dir:
        path = os.path.abspath('.')
    else:
        path = src_dir
    # path = os.getcwd()
    while True:
        path = rlinput(f'Enter an absolute directory location (S to skip): ',
                       path)
        if path == 'S':
            return None
        if os.path.exists(path):
            rpm_filelist = []
            non_rpm_filelist = []
            print()
            top, dirs, files = next(os.walk(path))
            files.sort()
            rpm_cnt = 0
            non_rpm_cnt = 0
            for f in files:
                if f.endswith('.rpm'):
                    rpm_filelist.append(f)
                    rpm_cnt += 1
                else:
                    non_rpm_filelist.append(f)
                    non_rpm_cnt += 1
            cnt = min(10, max(rpm_cnt, non_rpm_cnt))
            rpm_filelist += rows * ['']
            list1 = rpm_filelist[:cnt]
            non_rpm_filelist += rows * ['']
            list2 = non_rpm_filelist[:cnt]
            print('\n' + bold(path))
            print(tabulate(list(zip(list1, list2)),
                           headers=[bold('RPM Files'),
                                    bold('Other files')], tablefmt='psql'))

            if rpm_cnt > 0:
                print(bold(f'{rpm_cnt} rpm files found'))
                print(f'including the {min(10, rpm_cnt)} files above.\n')
            else:
                print(bold('No rpm files found\n'))
            if non_rpm_cnt > 0:
                print(bold(f'{non_rpm_cnt} other files found'))
                print(f'including the {min(10, non_rpm_cnt)} files above.')
            else:
                print(bold('No non rpm files found'))

            print('\nSub directories of the entered directory: ')
            dirs.sort()
            print(dirs)

            print(f'\nThe entered path was: {top}')
            if get_yesno('Use the entered path '):
                return path


def scan_ping_network(network_type='all', config_path=None):
    cfg = Config(config_path)
    type_ = cfg.get_depl_netw_client_type()
    if network_type == 'pxe' or network_type == 'all':
        net_type = 'pxe'
        idx = type_.index(net_type)
        cip = cfg.get_depl_netw_client_cont_ip()[idx]
        netprefix = cfg.get_depl_netw_client_prefix()[idx]
        cidr_cip = IPNetwork(cip + '/' + str(netprefix))
        net_c = str(IPNetwork(cidr_cip).network)
        cmd = 'fping -a -r0 -g ' + net_c + '/' + str(netprefix)
        result, err, rc = sub_proc_exec(cmd)
        print(result)

    if network_type == 'ipmi' or network_type == 'all':
        net_type = 'ipmi'
        idx = type_.index(net_type)
        cip = cfg.get_depl_netw_client_cont_ip()[idx]
        netprefix = cfg.get_depl_netw_client_prefix()[idx]
        cidr_cip = IPNetwork(cip + '/' + str(netprefix))
        net_c = str(IPNetwork(cidr_cip).network)
        cmd = 'fping -a -r0 -g ' + net_c + '/' + str(netprefix)
        result, err, rc = sub_proc_exec(cmd)
        print(result)


def get_selection(items, choices=None, prompt='Enter a selection: ', sep='\n',
                  allow_none=False, allow_retry=False):
    """Prompt user to select a choice. Entered choice can be a member of
    choices or items, but a member of choices is always returned as choice. If
    choices is not specified a numeric list is generated. Note that if choices
    or items is a string it will be 'split' using sep. If you wish to include
    sep in the displayed choices or items, an alternate seperator can be
    specified.
    ex: ch, item = get_selection('Apple pie\nChocolate cake')
    ex: ch, item = get_selection('Apple pie.Chocolate cake', 'Item 1.Item 2',
                                 sep='.')
    Inputs:
        choices (str or list or tuple): Choices. If not specified, a numeric
                                        list is generated.
        items (str or list or tuple): Description of choices or items to select
    returns:
       ch (str): One of the elements in choices
       item (str): mathing item from items
    """
    if not items:
        return None, None
    if not isinstance(items, (list, tuple)):
        items = items.rstrip(sep)
        items = items.split(sep)
    if not choices:
        choices = [str(i) for i in range(1, 1 + len(items))]
    if not isinstance(choices, (list, tuple)):
        choices = choices.rstrip(sep)
        choices = choices.split(sep)
    if allow_none:
        choices.append('N')
        items.append('Return without making a selection.')
    if allow_retry:
        choices.append('R')
        items.append('Retry the search.')
    if len(choices) == 1:
        return choices[0], items[0]
    maxw = 1
    for ch in choices:
        maxw = max(maxw, len(ch))
    print()
    for i in range(min(len(choices), len(items))):
        print(bold(f'{choices[i]: <{maxw}}') + ' - ' + items[i])
    print()
    ch = ' '
    while not (ch in choices or ch in items):
        ch = input(f'{Color.bold}{prompt}{Color.endc}')
        if not (ch in choices or ch in items):
            print('Not a valid selection')
            print(f'Choose from {choices}')
            ch = ' '
    if ch not in choices:
        # not in choices so it must be in items
        ch = choices[items.index(ch)]
    item = items[choices.index(ch)]
    if item == 'Return without making a selection.':
        item = None
    print()
    return ch, item


def get_src_path(src_name):
    """Search local disk for src_name and allow interactive selection if more
    than one match. Note that the user is not given the option to change the
    search criteria. Searching starts recursively in the /home directory and
    expands to entire file system if no match in /home.
    """
    log = logger.getlogger()
    while True:
        cmd = (f'find /home -name {src_name}')
        resp1, err, rc1 = sub_proc_exec(cmd)
        if rc1 != 0:
            log.error(f'Error searching for {src_name}')

        cmd = (f'find /root -name {src_name}')
        resp2, err, rc2 = sub_proc_exec(cmd)
        if rc2 != 0:
            log.error(f'Error searching for {src_name}')
        if rc1 != 0 and rc2 != 0:
            return None

        resp = resp1 + resp2
        if not resp:
            cmd = (f'find / -name {src_name}')
            resp, err, rc = sub_proc_exec(cmd)
            if rc != 0:
                log.error(f'Error searching for {src_name}')
                return None
            if not resp:
                print(f'Source file {src_name} not found')
                if not get_yesno('Search again', 'y/no', default='y'):
                    log.error(f'Source file {src_name} not found.\n '
                              f'{src_name} is not setup in the POWER-Up '
                              'software server.')
                    return None
            else:
                ch, src_path = get_selection(resp,
                                             prompt='Select a source file: ',
                                             allow_none=True, allow_retry=True)
                if ch != 'R':
                    return src_path
        else:
            ch, src_path = get_selection(resp, prompt='Select a source file: ',
                                         allow_none=True, allow_retry=True)
            if ch != 'R':
                return src_path


def get_file_path(filename='/home'):
    """Interactive search and selection of a file path.
    Returns:
        path to file or None
    """
    print(bold('\nFile search hints:'))
    print('/home/user1/abc.*         Search for abc.* under home/user1/')
    print('/home/user1/**/abc.*      Search recursively for abc.* under '
          '/home/user1/')
    print('/home/user1/myfile[56].2  Search for myfile5.2 or myfile6.2 under '
          '/home/user1/')
    print('/home/user1/*/            List directories under /home/user1')
    print()
    maxl = 10
    while True:
        print("Enter a file name to search for ('L' to leave without making a "
              "selction): ")
        filename = rlinput(bold("File: "), filename)
        print()
        if filename == 'L' or filename == "'L'":
            return None
        files = glob(filename, recursive=True)
        if files:
            print(bold(f'Found {len(files)} matching'))
            if len(files) > maxl:
                print(f'\nSearch returned more than {maxl} items. Showing '
                      f'first {maxl}')
                files = files[:40]
            choices = [str(i + 1) for i in range(len(files))]
            choices.append('S')
            choices.append('L')
            files.append('Search again')
            files.append('Leave without selecting')
            ch, item = get_selection(files, choices)
            print()
            if item is not None and os.path.isfile(item):
                print(f'\n{item}')
                if get_yesno("Confirm selection: ", default='y'):
                    return item
                else:
                    item = 'Search again'
            elif item == 'Leave without selecting':
                return None
            if item != 'Search again':
                filename = item


def ansible_pprint(ansible_output):
    """Ansible pretty print

    Args:
        ansible_output (str): Raw ansible output

    Returns:
        str: Ansible output formatted for visual parsing
    """
    pretty_out = ""
    indent_str = "    "
    indentation = ""
    for item in ['{', '}']:
        ansible_output = ansible_output.replace(f'{item}', f'\n{item}')
    ansible_output = ansible_output.replace(': ["', ':\n["')
    ansible_output = ansible_output.replace('\\r\\n"', '"')
    ansible_output = ansible_output.replace('\\r\\n', '\n')
    ansible_output = ansible_output.replace('\\n', '\n')
    ansible_output = ansible_output.replace('\\r', '\n')
    index_indent = False
    for line in ansible_output.splitlines():
        for element in line.split(','):

            element = element.lstrip()

            if element.startswith('{'):
                pretty_out += indentation + "{\n"
                indentation += indent_str
                element = element[1:]
            elif element.startswith('['):
                indentation += indent_str
            elif element.endswith('}'):
                indentation = indentation[len(indent_str):]

            if element != '':
                pretty_out += indentation + element + "\n"

            if element.count("\"") == 3:
                index_indent = True
                index = element.find("\"")
                index = element.find("\"", index + 1)
                index = element.find("\"", index + 1)
                indentation += index * ' '

            if element.endswith(']'):
                indentation = indentation[len(indent_str):]
            elif index_indent and element.endswith('"'):
                indentation = indentation[index:]
                index_indent = False

    return pretty_out


def get_col_pos(tbl, hdrs, row_char='-'):
    """Gets the indices for the column positions in a text table
    Inputs:
        tbl (str): Text table with rows terminated with '\n'
        hdrs (tuple of str): Each element of the tuple is a column header. Note
             that hdrs are treated at regular expressions. Characters such as
             '([{)}]' need to be escaped with a '\'.
        row_char (scalar str): Character used in the table row which separates
            the headers from the table rows

    For example, for the table below, the following call;
    get_col_pos(tbl, ('col 1', 'col 2', 'last col'), '-' 'this data')

    will return;
    {'col 2': (10, 18), 'col 1': (0, 8), 'last col': (20, 30)}

    tbl:
    'Data from somewhere with a table\n'
    'this data has a table with a my col 1, a my col 2, and a last col\n'
    '\n'
    '          my col 2
    'my col 1   wraps     last col\n'
    '--------  --------  ----------\n'
    'abcdef     ijklm    pqrstuvwxy'
    """
    log = logger.getlogger()
    tbl = tbl.splitlines()
    hdr_span = {}
    col_idx = {}

    for row in tbl:
        dashes_span = re.search(fr'{row_char}+\s+{row_char}+', row)
        if dashes_span:
            dashes_span = list(re.finditer(r'-+', row))
            col_span = [x.span() for x in dashes_span]
            break

        for hdr in hdrs:
            idx = re.search(hdr, row, re.IGNORECASE)
            if idx:
                hdr_span[hdr] = idx.span()

    log.debug(f'Seperator row: {row}')
    for hdr in hdr_span:
        for col in col_span:
            col_idx[hdr] = (0, 0)
            if hdr_span[hdr][0] >= col[0] and hdr_span[hdr][1] <= col[1]:
                col_idx[hdr] = col
                break

    return col_idx


def nginx_modify_conf(conf_path, directives={}, locations={}, reload=True,
                      clear=False):
    """Create/modify nginx configuration file

    Directives are defined in a dictionary, e.g.:

        directives={'listen': 80', 'server_name': 'powerup'}

    Locations are defined in a dictionary with values as strings or
    lists, e.g.:

        locations={'/': ['root /srv', 'autoindex on'],
                   '/cobbler': 'alias /var/www/cobbler'}

    *note: Semicolons (;) are auto added if not present

    Args:
        conf_path (str): Path to nginx configuration file
        directives (dict, optional): Server directives
        locations (dict, optional): Location definitions
        reload (bool, optional): Reload nginx after writing config
        clear (bool, optional): Remove any existing configuration data

    Returns:
        int: Return code from nginx syntax check ('nginx -t')
             If syntax check rc=0 and reload=True the return code
             from 'systemctl restart nginx.service'
    """

    collecting_directive_data = False
    collecting_location_data = False
    current_location = None

    if not clear and os.path.isfile(conf_path):
        LOG.debug(f"Loading existing nginx config: '{conf_path}")
        with open(conf_path, 'r') as file_object:
            for line in file_object:
                if 'server {' in line:
                    collecting_directive_data = True
                elif not line.strip():
                    continue  # continue if blank line
                elif 'location' in line:
                    collecting_directive_data = False
                    current_location = line.strip()[9:-2]
                    if current_location not in locations:
                        collecting_location_data = True
                        locations[current_location] = []
                    else:
                        current_location = None
                elif '}' in line and collecting_location_data:
                    collecting_location_data = False
                    current_location = None
                elif collecting_location_data:
                    locations[current_location].append(line.strip())
                elif '}' in line and collecting_directive_data:
                    collecting_directive_data = False
                elif collecting_directive_data:
                    data_split = line.split(maxsplit=1)
                    if data_split[0] not in directives:
                        directives[data_split[0]] = data_split[1].strip()

    LOG.debug(f"Writing nginx config: '{conf_path}")
    with open(conf_path, 'w') as file_object:
        file_object.write('server {\n')

        for key, value in directives.items():
            if not value.endswith(';'):
                value = value + ';'
            file_object.write(f'    {key} {value}\n')

        for key, value_list in locations.items():
            file_object.write(f'    location {key} ' + '{\n')
            if type(value_list) is str:
                value_list = value_list.split('\n')
            for value in value_list:
                if not value.endswith(';'):
                    value = value + ';'
                file_object.write(f'        {value}\n')
            file_object.write('    }\n')

        file_object.write('}\n')

    cmd = (f'nginx -t')
    stdout, stderr, rc = sub_proc_exec(cmd)
    LOG.debug(f"Command: \'{cmd}\'\nstdout: \'{stdout}\'\n"
              f"stderr: \'{stderr}\'\nrc: {rc}")
    if rc != 0:
        LOG.warning('Nginx configuration check failed')
    elif reload:
        cmd = ('systemctl restart nginx.service')
        stdout, stderr, rc = sub_proc_exec(cmd)
        LOG.debug(f"Command: \'{cmd}\'\nstdout: \'{stdout}\'\n"
                  f"stderr: \'{stderr}\'\nrc: {rc}")
        if rc != 0:
            LOG.warning('Nginx failed to start')

    return rc


def dnsmasq_add_dhcp_range(dhcp_range,
                           lease_time='1h',
                           conf_path='/etc/dnsmasq.conf',
                           reload=True):
    """Add DHCP range to existing dnsmasq configuration

    Args:
        dhcp_range (str, optional): Range of IP addresses to lease to clients
                                    formatted as "<start_ip>,<end_ip>"
        lease_time (str, optional): Time duration of IP leases
        conf_path (str, optional): Path to dnsmasq configuration file
        reload (bool, optional): Reload dnsmasq after writing config

    Returns:
        int: Return code from nginx syntax check ('dnsmasq --test')
             If syntax check rc=0 and reload=True the return code
             from 'systemctl restart dnsmasq.service'
    """

    append_line(conf_path, f'dhcp-range={dhcp_range},{lease_time}',
                check_exists=True)
    cmd = (f'dnsmasq --test')
    stdout, stderr, rc = sub_proc_exec(cmd)
    LOG.debug(f"Command: \'{cmd}\'\nstdout: \'{stdout}\'\n"
              f"stderr: \'{stderr}\'\nrc: {rc}")
    if rc != 0:
        LOG.warning('dnsmasq configuration check failed')
    elif reload:
        cmd = ('systemctl restart dnsmasq.service')
        stdout, stderr, rc = sub_proc_exec(cmd)
        LOG.debug(f"Command: \'{cmd}\'\nstdout: \'{stdout}\'\n"
                  f"stderr: \'{stderr}\'\nrc: {rc}")
        if rc != 0:
            LOG.error('dnsmasq service restart failed')

    return rc


def dnsmasq_config_pxelinux(interface=None,
                            dhcp_range=None,
                            lease_time='1h',
                            default_route=None,
                            tftp_root=None,
                            conf_path='/etc/dnsmasq.conf',
                            reload=True):
    """Create dnsmasq configuration to support PXE boots

    *note*: This is overwrite any existing configuration located at
            'conf_path'!

    Args:
        interface (str, optional): Only listen for requests on given interface
        dhcp_range (str, optional): Range of IP addresses to lease to clients
                                    formatted as "<start_ip>,<end_ip>"
        lease_time (str, optional): Time duration of IP leases
        default_route (str, optional): IP pushed to clients as default route
        conf_path (str, optional): Path to dnsmasq configuration file
        reload (bool, optional): Reload dnsmasq after writing config

    Returns:
        int: Return code from nginx syntax check ('dnsmasq --test')
             If syntax check rc=0 and reload=True the return code
             from 'systemctl restart dnsmasq.service'
    """

    if tftp_root is None:
        if 'rhel' in linux_distribution(full_distribution_name=False):
            tftp_root = '/var/lib/tftpboot'
        if 'ubuntu' in linux_distribution(full_distribution_name=False):
            tftp_root = '/tftpboot'

    backup_file(conf_path)

    with open(conf_path, 'w') as file_object:
        file_object.write(
            "# POWER-Up generated configuration file for dnsmasq\n\n")

        if interface is not None:
            file_object.write(f"interface={interface}\n\n")

        file_object.write(dedent(f"""\
            dhcp-lease-max=1000
            dhcp-authoritative
            dhcp-boot=pxelinux.0

            enable-tftp
            tftp-root={tftp_root}
            user=root
        \n"""))

        if default_route is not None:
            file_object.write(f"dhcp-option=3,{default_route}\n\n")

        if dhcp_range is not None:
            file_object.write(f"dhcp-range={dhcp_range},{lease_time}\n")

    cmd = (f'dnsmasq --test')
    stdout, stderr, rc = sub_proc_exec(cmd)
    LOG.debug(f"Command: \'{cmd}\'\nstdout: \'{stdout}\'\n"
              f"stderr: \'{stderr}\'\nrc: {rc}")
    if rc != 0:
        LOG.warning('dnsmasq configuration check failed')
    elif reload:
        cmd = 'systemctl enable dnsmasq.service'
        resp, err, rc = sub_proc_exec(cmd)
        if rc != 0:
            LOG.error('Failed to enable dnsmasq service')

        cmd = 'systemctl restart dnsmasq.service'
        stdout, stderr, rc = sub_proc_exec(cmd)
        LOG.debug(f"Command: \'{cmd}\'\nstdout: \'{stdout}\'\n"
                  f"stderr: \'{stderr}\'\nrc: {rc}")
        if rc != 0:
            LOG.error('dnsmasq service restart failed')

    return rc


def pxelinux_set_default(server,
                         kernel,
                         initrd,
                         kickstart=None,
                         kopts=None,
                         dir_path=None):
    """Create default pxelinux profile

    This function assumes that the server is hosting the kernel,
    initrd, and kickstart (if specified) over http. The default
    'dir_path' requires root access.

    Args:
        server (str): IP or hostname of http server hosting files
        kernel (str): HTTP path to installer kernel
        initrd (str): HTTP path to installer initrd
        kickstart (str, optional): HTTP path to installer kickstart
        kopts (str, optional): Any additional kernel options
        dir_path (str, optional): Path to pxelinux directory
    """

    if dir_path is None:
        if 'rhel' in linux_distribution(full_distribution_name=False):
            dir_path = '/var/lib/tftpboot/pxelinux.cfg/'
        if 'ubuntu' in linux_distribution(full_distribution_name=False):
            dir_path = '/tftpboot/pxelinux.cfg/'

    kopts_base = (f"ksdevice=bootif lang=  kssendmac text")

    if kickstart is not None:
        if 'ubuntu' in kernel.lower():
            ks_key = 'url'
        else:
            ks_key = 'ks'
        kopts_base += f"  {ks_key}=http://{server}/{kickstart}"

    if kopts is not None:
        kopts = kopts_base + f"  {kopts}"
    else:
        kopts = kopts_base

    default = os.path.join(dir_path, 'default')
    os.makedirs(dir_path, exist_ok=True)

    with open(default, 'w') as file_object:
        file_object.write(dedent(f"""\
            DEFAULT {kernel.split('/')[1]}

            LABEL local
              MENU LABEL (local)
              MENU DEFAULT
              LOCALBOOT -1

            LABEL {kernel.split('/')[1]}
              MENU LABEL PXE Install: {kernel.split('/')[1]}
              KERNEL http://{server}/{kernel}
              INITRD http://{server}/{initrd}
              IPAPPEND 2
              APPEND  {kopts}

        """))


def pxelinux_set_local_boot(dir_path=None):
    """Disable PXE install by setting boot device to 'local'

    Args:
        dir_path (str, optional): Path to pxelinux directory
    """

    if dir_path is None:
        if 'rhel' in linux_distribution(full_distribution_name=False):
            dir_path = '/var/lib/tftpboot/pxelinux.cfg/'
        if 'ubuntu' in linux_distribution(full_distribution_name=False):
            dir_path = '/tftpboot/pxelinux.cfg/'

    replace_regex(os.path.join(dir_path, 'default'),
                  r'^DEFAULT.*$', 'DEFAULT local')


def firewall_add_services(services):
    """Add services to be allowed in firewall rules

    Args:
        services (str or list): Service(s) to be permanently allowed

    Returns:
        int: Binary error code
    """

    if type(services) is str:
        services = [services]

    fw_err = 0
    if 'rhel' in linux_distribution(full_distribution_name=False):
        firewall_service = 'firewalld.service'
        firewall_enable_cmd = 'firewall-cmd --permanent --add-service='
        firewall_reload_cmd = 'firewall-cmd --reload'
    elif 'ubuntu' in linux_distribution(full_distribution_name=False):
        firewall_service = 'ufw.service'
        firewall_enable_cmd = 'ufw allow '
        firewall_reload_cmd = 'true'
        return 0  # TODO: Need to add firewall configuration for Ubuntu
    cmd = f'systemctl status {firewall_service}'
    resp, err, rc = sub_proc_exec(cmd)
    if 'Active: active (running)' in resp.splitlines()[2]:
        LOG.debug('Firewall is running')
    else:
        cmd = f'systemctl enable {firewall_service}'
        resp, err, rc = sub_proc_exec(cmd)
        if rc != 0:
            fw_err += 1
            LOG.error('Failed to enable firewall service')

        cmd = f'systemctl start {firewall_service}'
        resp, err, rc = sub_proc_exec(cmd)
        if rc != 0:
            fw_err += 10
            LOG.error('Failed to start firewall')

    for service in services:
        cmd = f'{firewall_enable_cmd}{service}'
        resp, err, rc = sub_proc_exec(cmd)
        if rc != 0:
            fw_err += 100
            LOG.error(f'Failed to enable {service} service on firewall')

    resp, err, rc = sub_proc_exec(firewall_reload_cmd)
    if 'success' not in resp:
        fw_err += 1000
        LOG.error('Error attempting to restart firewall')

    return fw_err


def extract_iso_image(iso_path, dest_dir):
    """Extract ISO image into directory

    If a (non-empty) directory matching the iso file already exists in
    the destination directory extraction is not attempted.

    Args:
        iso_path (str): Path to ISO file
        dest_dir (str): Path to an existing directory that the ISO will
                        be extracted into. A subdirectory matching the
                        image filename will be created.

    Returns:
        tuple: ('str: Relative path to kernel',
                'str: Relative path to initrd')

    Raises:
        UserException: iso_path is not a valid file path
                       iso_path does not end in '.iso'
                       can't find kernel or initrd in extracted image
    """

    if not os.path.isfile(iso_path):
        raise UserException(f"Invalid iso_path: '{iso_path}")
    elif not iso_path.lower().endswith('.iso'):
        raise UserException(f"File does not end with '.iso': '{iso_path}'")

    name = os.path.basename(iso_path)[:-4]
    iso_dir = os.path.join(dest_dir, name)

    if not os.path.isdir(iso_dir):
        os.makedirs(iso_dir)

    if len(os.listdir(iso_dir)) == 0:
        bash_cmd(f'xorriso -osirrox on -indev {iso_path} -extract / {iso_dir}')
        bash_cmd(f'chmod 755 {iso_dir}')

    filename_parsed = {item.lower() for item in name.split('-')}
    kernel = None
    initrd = None
    if {'ubuntu', 'amd64'}.issubset(filename_parsed):
        sub_path = 'install/netboot/ubuntu-installer/amd64'
        kernel = os.path.join(name, sub_path, 'linux')
        initrd = os.path.join(name, sub_path, 'initrd.gz')
        if not os.path.isfile(kernel):
            sub_path = 'casper'
            kernel = os.path.join(name, sub_path, 'vmlinux')
            initrd = os.path.join(name, sub_path, 'initrd')
    elif {'ubuntu', 'ppc64el'}.issubset(filename_parsed):
        sub_path = 'install/netboot/ubuntu-installer/ppc64el'
        kernel = os.path.join(name, sub_path, 'vmlinux')
        initrd = os.path.join(name, sub_path, 'initrd.gz')
    elif ({'rhel', 'x86_64'}.issubset(filename_parsed) or
            {'centos', 'x86_64'}.issubset(filename_parsed)):
        sub_path = 'images/pxeboot'
        kernel = os.path.join(name, sub_path, 'vmlinuz')
        initrd = os.path.join(name, sub_path, 'initrd.img')
    elif ({'rhel', 'ppc64le'}.issubset(filename_parsed) or
            {'centos', 'ppc64le'}.issubset(filename_parsed)):
        sub_path = 'ppc/ppc64'
        kernel = os.path.join(name, sub_path, 'vmlinuz')
        initrd = os.path.join(name, sub_path, 'initrd.img')

    if not os.path.isfile(os.path.join(dest_dir, kernel)):
        kernel = None
    if not os.path.isfile(os.path.join(dest_dir, initrd)):
        initrd = None

    # If kernel or initrd isn't in the above matrix search for them
    if kernel is None or initrd is None:
        kernel_names = {'linux', 'vmlinux', 'vmlinuz'}
        initrd_names = {'initrd.gz', 'initrd.img', 'initrd'}

        for dirpath, dirnames, filenames in os.walk(iso_dir):
            if kernel is None and not kernel_names.isdisjoint(set(filenames)):
                rel_dir = os.path.relpath(dirpath, dest_dir)
                kernel = (os.path.join(
                    rel_dir, kernel_names.intersection(set(filenames)).pop()))
            if initrd is None and not initrd_names.isdisjoint(set(filenames)):
                rel_dir = os.path.relpath(dirpath, dest_dir)
                initrd = (os.path.join(
                    rel_dir, initrd_names.intersection(set(filenames)).pop()))
            if kernel is not None and initrd is not None:
                break

    if kernel is None or initrd is None:
        raise UserException("Unable to find kernel and/or initrd in ISO image:"
                            f" kernel: '{kernel}' initrd: '{initrd}'")

    return kernel, initrd


def timestamp():
    return datetime.datetime.now().strftime("%d-%h-%Y-%H-%M-%S")


def sha1sum(file_path):
    """ Calculate sha1 checksum of single file

    Args:
        file_path (str): Path to file

    Returns:
        str: sha1 checksum
    """
    sha1sum = hashlib.sha1()
    with open(file_path, 'rb') as file_object:
        for block in iter(lambda: file_object.read(sha1sum.block_size), b''):
            sha1sum.update(block)
    return sha1sum.hexdigest()


def clear_curses():
    """ Curses cleanup

    Reset terminal normal mode after running curses application
    """
    from curses import nocbreak, echo, endwin
    nocbreak()
    echo()
    endwin()


def interact(**kwargs):
    """ Wrapper for code.interact with curses cleanup

    Args:
        **kwargs: See code.interact documentation
    """
    import code
    clear_curses()
    code.interact(**kwargs)


def breakpoint():
    """ Wrapper for pdb.set_trace() with curses cleanup

    Note: python>=3.7 includes a built-in 'breakpoint()'
    """
    from pdb import set_trace
    from _curses import error
    try:
        clear_curses()
    except error:
        pass
    set_trace()


def parse_pypi_filenames(filenames):
    """Returns the basename and version for a pypi package name filelist.
    Args:
        filenames(list): Package filenames of form named-ver-bld.type. Package
        names can have dashes or underscores. Filenames can also have underscores
        or dashes which don't alwys match the package names
    returns:

    """
    if isinstance(filenames, list):
        _dict = {}
        for _file in filenames:
            if _file.endswith('.whl') or _file.endswith('.gz') or \
                    _file.endswith('.bz2') or _file.endswith('.zip'):
                fnd = re.search(r'[-=]((\d+\.)+\d+)[-.]', _file)
                if fnd:
                    ver = fnd.group(1)
                    name = _file[:fnd.span()[0]]  # strip trailing eq_eq chars
                    bld = _file[fnd.span()[1]:]
                else:
                    ver = ''
                    bld = ''
                    name = _file
                    LOG.error(f'Unable to extract version from {_file}')
                if name in _dict:
                    _dict[name]['ver_bld'].append((ver, bld))
                else:
                    _dict[name] = {}
                    _dict[name]['ver_bld'] = [(ver, bld)]
    return _dict


def parse_conda_filenames(filenames):
    """Returns the basename, version and release for a conda package file list.
    list elements must be of form <name>-<version>-<build>.tar.bz2. Dashes must
    appear on both sides of the version and may appear in the name , but nowhere
    else.
    Args:
        filenames(list): list of filenames.
    Returns:
        dictionary of form: {basename: {'ver': version, 'rel': release lvl}}
    """
    def get_parts(filename):
        """Returns the basename, version and release for a conda package file.
        of the form basename-ver-release.tar.bz2.
        """
        filename = filename.strip()
        if not '.tar.bz2' == filename[-8:]:
            LOG.error(f'Improper conda filename: {filename}. Missing ".tar.bz2"')
            name = ''
            version = ''
            build = ''
        else:
            filename = filename[:-8]
            _split = filename.rsplit('-', 1)
            build = _split[-1]
            _split = _split[0].rsplit('-', 1)
            version = _split[-1]
            name = _split[0]

        return name, version, build

    if isinstance(filenames, list):
        _dict = {}
        for _file in filenames:
            name, version, build = get_parts(_file)
            if name not in _dict:
                _dict[name] = {}
                _dict[name]['ver_bld'] = []

            _dict[name]['ver_bld'].append((version, build))

        return _dict

    elif isinstance(filenames, str):
        return get_parts(filenames)


def get_rpm_info(filelist, _dir):
    def get_parts(info):
        name = ep = ver = rel = ''
        if 'Name' in info:
            name = info.split('Name', 1)[-1].lstrip(' :')
            name = name[:name.index('\n')]
        else:
            LOG.error(f'Name not found in rpm package info {info}')
        if 'Epoch' in info:
            ep = info.split('Epoch', 1)[-1].lstrip(' :')
            ep = ep[:ep.index('\n')]
        if 'Version' in info:
            ver = info.split('Version', 1)[-1].lstrip(' :')
            ver = ver[:ver.index('\n')]
        if 'Release' in info:
            rel = info.split('Release', 1)[-1].lstrip(' :')
            rel = rel[:rel.index('\n')]

        return name, ep, ver, rel

    if isinstance(filelist, list):
        _dict = {}
        for _file in filelist:
            path = os.path.join(_dir, _file)
            cmd = f'rpm -qip {path}'
            resp, err, rc = sub_proc_exec(cmd)
            if rc != 0:
                LOG.error(f'Error querying package {path}')
            name, ep, ver, rel = get_parts(resp)
            if name in _dict:
                if ep > _dict[name]['ep']:
                    _dict[name]['ver'] = ver
                    _dict[name]['rel'] = rel
                    _dict[name]['ep'] = ep
                elif rel > _dict[name]['rel'] and ver == _dict[name]['ver']:
                    _dict[name]['rel'] = rel
                elif ver > _dict[name]['ver']:
                    _dict[name]['ver'] = ver
                    _dict[name]['rel'] = rel
            else:
                _dict[name] = {}
                _dict[name]['ep'] = ep
                _dict[name]['ver'] = ver
                _dict[name]['rel'] = rel

        return _dict


def parse_rpm_filenames(filename, form='list'):
    """ returns the basename, epoch, version and release lvl for an rpm file
        If form is set to 'list', the components are returned as lists.
        If filename is a string, the components are returned as strings.
        if form is set to 'dict', a dictionary is returned. The keys are the
            basenames, the values are a dictionary with keys: ep, ver, rel.
            {basename: {'ep': epoch, 'ver': version, 'rel': release}} where
            epoch, version and release are strings.
    Args:
        filename (str or list)
        form
    Returns basename and version
    """
    def get_parts(_filename):
        """ Return a basename, epoch, version and release from a filename of
        form: basename-epoch:version-release.type.rpm
        The trailing .rpm is optional.  If only a basename is present,
        the epoch, version and release are returned as empty strings.
        The parsing algorithm assumes that the filenames reasonably follow
        the rpm naming convention: dashes are only allowed in the basename,
        not in the epoch, version or release, and dashes separate the version
        from the release level and the basename from the epoch:version where
        epoch is optional. If epoch is present it is separated from the release
        by a ':'. The algorithm parses right to left.
        """
        _filename = _filename.rstrip('.rpm')
        _file_nt = _filename.rsplit('.', 1)[0]  # drop the type (ie ppc64le)
        if _filename != _file_nt:
            tmp = _file_nt.rsplit('-', 1)
            if len(tmp) > 1:
                rel = tmp[-1]
            else:
                rel = ''
            _file_nr = tmp[0]
            tmp = _file_nr.rsplit('-', 1)
            if len(tmp) > 1:
                ver = tmp[1].split(':')[-1]
                if ':' in tmp[-1]:
                    ep = tmp[1].split(':')[0]
                else:
                    ep = ''
            else:
                ep = ''
                ver = ''
            basename = tmp[0]
        else:  # basename only
            basename = _file
            ver = ''
            rel = ''
            ep = ''
        return basename, ep, ver, rel

    if isinstance(filename, str):
        return get_parts(filename)
    elif form == 'list':
        basename = []
        version = []
        release = []
        epoch = []
        for _file in filename:
            bn, ep, ver, rel = get_parts(_file)
            basename.append(bn)
            version.append(ver)
            release.append(rel)
            epoch.append(ep)
        return basename, epoch, version, release
    elif form == 'dict':
        _dict = {}
        for _file in filename:
            basename, ep, ver, rel = get_parts(_file)
            if basename not in _dict:
                _dict[basename] = {}
                _dict[basename]['ver'] = ver
                _dict[basename]['rel'] = rel
                _dict[basename]['ep'] = ep
            else:  # if already in dict, replace if newer
                if ep > _dict[basename]['ep']:
                    _dict[basename]['ver'] = ver
                    _dict[basename]['rel'] = rel
                    _dict[basename]['ep'] = ep
                elif rel > _dict[basename]['rel'] and ver == _dict[basename]['ver']:
                    _dict[basename]['rel'] = rel
                elif ver > _dict[basename]['ver']:
                    _dict[basename]['ver'] = ver
                    _dict[basename]['rel'] = rel
            # print(i, _file, basename, ver, rel)
        return _dict
    else:
        epoch = None
        basename = None
        version = None

    return basename, epoch, version, release


def lscpu():
    """ Get 'lscpu' output as dictionary

    Returns:
        dict: Output from 'lscpu'
    """
    stdout, stderr, returncode = sub_proc_exec('lscpu')
    lscpu_dict = {}
    for line in stdout.splitlines():
        split = line.split(':', 1)
        lscpu_dict[split[0].strip()] = split[1].strip()
    return lscpu_dict
