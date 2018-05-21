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

from __future__ import nested_scopes, generators, division, absolute_import, \
    with_statement, print_function, unicode_literals

import os
import re
import sys
import time
import subprocess
import fileinput
import readline
from shutil import copy2, Error
from subprocess import Popen, PIPE
import code
import lib.logger as logger

PATTERN_MAC = '[\da-fA-F]{2}:){5}[\da-fA-F]{2}'
CalledProcessError = subprocess.CalledProcessError


def bash_cmd(cmd):
    """Run command in Bash subprocess

    Args:
        cmd (str): Command to run

    Returns:
        output (str): stdout from command
    """
    log = logger.getlogger()
    command = ['bash', '-c', cmd]
    log.debug('Run subprocess: %s' % ' '.join(command))
    output = subprocess.check_output(command, universal_newlines=True,
                                     stderr=subprocess.STDOUT).decode('utf-8')
    log.debug(output)

    return output


def backup_file(path):
    """Save backup copy of file

    Backup copy is saved as the name of the original with '.orig'
    appended. The backup copy filemode is set to read-only.

    Args:
        path (str): Path of file to backup
    """
    log = logger.getlogger()
    backup_path = path + '.orig'
    version = 0
    while os.path.exists(backup_path):
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


def copy_file(source, dest):
    """Copy a file to a given destination

    Args:
        source (str): Path of source file
        dest (str): Destination path to copy file to
    """
    log = logger.getlogger()
    log.debug('Copy file, source:%s dest:%s' % (source, dest))
    copy2(source, dest)


def sub_proc_launch(cmd, stdout=PIPE, stderr=PIPE):
    """Launch a subprocess and return the Popen process object.
    This is non blocking. This is useful for long running processes.
    """
    proc = Popen(cmd.split(), stdout=stdout, stderr=stderr)
    return proc


def sub_proc_exec(cmd, stdout=PIPE, stderr=PIPE):
    """Launch a subprocess wait for the process to finish.
    Returns stdout from the process
    This is blocking
    """
    proc = Popen(cmd.split(), stdout=stdout, stderr=stderr)
    stdout, stderr = proc.communicate()
    return stdout.decode('utf-8'), stderr.decode('utf-8'), proc.returncode


def sub_proc_display(cmd, stdout=None, stderr=None):
    """Popen subprocess created without PIPES to allow subprocess printing
    to the parent screen. This is a blocking function.
    """
    proc = Popen(cmd.split(), stdout=stdout, stderr=stderr)
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
    yellow = '\033[93m'
    blue = '\033[94m'
    purple = '\033[95m'
    cyan = '\033[96m'
    white = '\033[97m'
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


def heading1(text='-', width=79):
    text1 = f'          {Color.bold}{Color.underline}{text}{Color.endc}'
    print(f'\n{text1: <{width + 8}}')


def bold(text):
    return Color.bold + text + Color.endc


def rlinput(prompt, prefill=''):
    readline.set_startup_hook(lambda: readline.insert_text(prefill))
    try:
        return input(prompt)
    finally:
        readline.set_startup_hook()


def get_url(url='http://', prompt_name=''):
    """Input a URL from user. The URL is checked for validity using curl
    and the user can continue modifying it indefinitely until a response
    is obtained or he can enter 'S' to skip (stop) entry.
    """
    response = False
    while not response:
        resp = rlinput(f'Enter {prompt_name} URL (S to skip): ', url)
        if resp == 'S':
            return None
        url = resp
        try:
            cmd = f'curl -I {url}/'
            reply, err, rc = sub_proc_exec(cmd)
        except:
            pass
        else:
            response = re.search(r'HTTP\/\d+.\d+\s+200\s+ok', reply, re.IGNORECASE)
            if response:
                print(response.group(0))
                time.sleep(1.5)
                response = True
                return url
            else:
                err = re.search('curl: .+', err)
                if err:
                    print(err.group(0))
                tmp = re.search(r'HTTP\/\d+.\d+\s+.+', reply)
                if tmp:
                    print(tmp.group(0))


def get_yesno(prompt='', yesno='yes/n'):
    r = ' '
    yn = yesno.split('/')
    while r not in yn:
        r = input(f'{prompt}({yesno})? ')
    return r


def get_selection(items, choices=None, sep='\n', prompt='Enter a selection: '):
    """Prompt user to select a choice. Entered choice can be a member of choices or
    items, but a member of choices is always returned as choice. If choices is not
    specified a numeric list is generated. Note that if choices or items is a string
    it will be 'split' using sep. If you wish to include sep in the displayed
    choices or items, an alternate seperator can be specified.
    ex: ch, item = get_selection('Apple pie\nChocolate cake')
    ex: ch, item = get_selection('Apple pie.Chocolate cake', 'Item 1.Item 2', sep='.')
    Inputs:
        choices (str or list or tuple): Choices
        choices_only (bool) : Set to false to allow descs as valid choices
        descs (str or list or tuple): Description of choices
    returns:
       ch (str): One of the elements in choices
       item (str): mathing item from items
    """
    if not isinstance(items, (list, tuple)):
        items = items.rstrip(sep)
        items = items.split(sep)
    if not choices:
        choices = [str(i) for i in range(1, 1 + len(items))]
    if not isinstance(choices, (list, tuple)):
        choices = choices.rstrip(sep)
        choices = choices.split(sep)
    if len(choices) == 1:
        return choices[0]
    maxw = 1
    for ch in choices:
        maxw = max(maxw, len(ch))
    print()
    for i in range(min(len(choices), len(items))):
        print(f'{bold(choices[i]): <{maxw}}' + ' - ' + items[i])
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
    return ch, item
