#!/usr/bin/env python
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


import sys
import argparse
import logging
import tarfile
import os
import tempfile
import time
from setuptools.archive_util import unpack_tarfile


COMPRESSION = "gz"
RC_SUCCESS = 0
RC_ERROR = 99  # generic failure
RC_ARGS = 2  # failed to parse args given
RC_SRV = 20  # generic failure
RC_USER_EXIT = 40  # keyboard exit

PAIE_SRV = "/srv/"
PAIE_EXTRACT_SRV = "/tmp/srv/"
ENG_MODE = False
LOG = ""
STANDALONE = True
if (sys.version_info > (3, 0)):
    try:
        TOP_DIR = os.path.join(os.getcwd(), os.path.dirname(__file__), '../../..')
        SCRIPT_DIR = 'scripts/python'
        sys.path.append(os.path.join(TOP_DIR, SCRIPT_DIR))
        import lib.logger as log
        LOG = log.getlogger()
        STANDALONE = False
    except:
        LOG = logging.getLogger(__name__)
        STANDALONE = True
else:
    LOG = logging.getLogger(__name__)


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
            else:  # rc == RC_ERROR:
                raise Exception(err)


def build_files_of_this(thing, exclude=None):
    files = []
    for dirname, dirnames, fnames in os.walk(thing):
        for filename in fnames + dirnames:
            longpath = os.path.join(dirname, filename)
            thisFile = longpath.replace(thing, '', 1).lstrip('/')
            files.append(thisFile)
            LOG.debug(thisFile)
    return files


def unarchive_this(src, dest):
    try:
        unpack_tarfile(src, dest)
    except Exception as e:
        exit(RC_ERROR, "Uncaught exception {0}".format(e))


def archive_this(thing, exclude=None, fileObj=None, compress=False):
    """
        Archive utility
    ex: fileObj = archive_this('file.txt')
    Inputs:
        thing (str): root directory
        exclude (str or None): list of full path of files to exclude
        fileObj (fileobj): file object
    returns:
       fileObj (fileobj): file object
    """
    if not fileObj:
        fileObj = tempfile.NamedTemporaryFile()
    mode = 'w:'
    if compress:
        mode += COMPRESSION
    with tarfile.open(mode=mode, fileobj=fileObj) as t:
        files = build_files_of_this(thing, exclude)
        if exclude is None:
            exclude = []
        for path in files:
            full_path = os.path.join(thing, path)
            if full_path in exclude:
                continue
            i = t.gettarinfo(full_path, arcname=path)
            try:
                if i.isfile():
                    try:
                        with open(full_path, 'rb') as f:
                            t.addfile(i, f)
                    except IOError:
                        LOG.error(
                            'Can not read file: {}'.format(full_path))
                else:
                    t.addfile(i, None)
            except Exception as e:
                if i is not None:
                    LOG.error(e)

    fileObj.seek(0)
    return fileObj


def setup_logging(debug="INFO"):
    '''
    Method to setup logging based on debug flag
    '''
    LOG.setLevel(debug)
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    LOG.addHandler(ch)


def parse_input(args):
    parser = argparse.ArgumentParser(description="Utility for Archiving/Unarchiving\
                                     PowerAIE Node Deployer environment")
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
            sub_parser.set_defaults(func=globals()[cmd])

        sub_parser.add_argument('-ll', '--loglevel', type=str,
                                choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                                default="INFO",
                                help='Set the logging level')

    if ENG_MODE is True:
        add_subparser('archive', "Compress directory",
                      [('path', 'path to archive', True),
                       ('dest', 'destination file', True)])
        subparsers.choices['archive'].add_argument('--compress',
                                                   dest="compress",
                                                   required=False, action="store_true",
                                                   help='compress using gzip')

        add_subparser('unarchive', "Uncompress file",
                      [('src', 'source file to unarchive', True),
                       ('dest', 'destination directory', True)])
    add_subparser('list', "List files in tar object",
                  [('src', 'source file to list', True)])

    add_subparser('bundle', "Bundle Paie software, assume bundle from /srv directory",
                  [('to', 'bundle paie software to?', True)])

    subparsers.choices['bundle'].add_argument('--compress', dest="compress",
                                              required=False, action="store_true",
                                              help='compres using gzip')

    add_subparser('extract_bundle', "Extract bundle Paie software assume to /srv",
                  [('from_archive', 'from which archive to extract paie software?', True)])

    if not args:
        parser.print_help()
        sys.exit(RC_ARGS)
    args = parser.parse_args(args)

    if STANDALONE is True:
        LOG.setLevel(args.loglevel)
    return args


def validate_path(path):
    return do_validate_exists("path", path)


def validate_from_archive(path):
    return do_validate_exists("from_archive", path)


def validate_to(path):
    return do_validate_warn_exists("to", path)


def do_validate_exists(name, path):
    if not os.path.exists(path):
        exit(RC_ARGS, "{1} does not exist ({0})".format(path, name))
    LOG.debug("{1} = {0}".format(path, name))
    return path


def do_validate_warn_exists(name, path):
    if os.path.isfile(path):
        LOG.warning("Destination exist {0}".format(path))
    LOG.debug("{1} = {0}".format(path, name))
    return path


def validate_dest(path):
    return do_validate_warn_exists("dest", path)


def validate_src(path):
    return do_validate_exists("src", path)


def list(args):
    try:
        with tarfile.open(args.src) as tarlist:
            for i in tarlist:
                LOG.info(i.name)
    except Exception as e:
        exit(RC_ERROR, "{0}".format(e))


def archive(args):
    dir_path = os.path.dirname(os.path.realpath(args.dest))
    file_name = os.path.splitext(args.dest)[0]
    file_name_ext = os.path.splitext(args.dest)[1]
    try:
        try:
            fileobj = tempfile.NamedTemporaryFile(delete=False, prefix=file_name,
                                                  suffix=file_name_ext, dir=dir_path)
        except OSError as e:
            LOG.error(e)
            try:
                os.makedirs(dir_path)
                fileobj = tempfile.NamedTemporaryFile(delete=False, prefix=file_name,
                                                      suffix=file_name_ext, dir=dir_path)
            except Exception as e:
                exit(RC_ERROR, "Unable to create directory: {0}".format(e))

        if args.compress is False or args.compress is None:
            args.compress = False
            LOG.info("not compressing")

        try:
            LOG.info("archiving {0}".format(args.path))
            start = time.time()
            archive_this(args.path, fileObj=fileobj, compress=args.compress)
            end = time.time()
        except Exception as e:
            if fileobj is not None:
                os.unlink(fileobj.name)
            exit(RC_ERROR, "Uncaught exception: {0}".format(e))
        else:
            LOG.info("created: {0}, size in bytes: {1},\
                     total time: {2} seconds".format(fileobj.name,
                                                     os.stat(fileobj.name).st_size,
                                                     (end - start)))
        finally:
            if fileobj is not None:
                fileobj.close()
    except KeyboardInterrupt as e:
        if fileobj is not None:
            os.unlink(fileobj.name)
        raise e
    except Exception as e:
        raise e


def unarchive(args):
    unarchive_this(args.src, args.dest)


def do_bundle(args):
    LOG.debug("bundle : {0}".format(args))
    if os.path.isdir(args.path):
        archive(args)
    else:
        exit(RC_SRV, "Unable to find {0}".format(args.path))


class Arguments(object):
    def __init__(self):
        self.path = None
        self.dest = None
        self.compress = False


def bundle_this(path, dest):
    args = Arguments()
    args.path = path
    args.dest = dest
    do_bundle(args)


def bundle(args):
    args.path = PAIE_SRV
    args.dest = args.to
    do_bundle(args)


def do_extract_bundle(args):
    LOG.debug("unarchiving : {0}".format(args))
    if os.path.isdir(args.dest):
        unarchive(args)
    else:
        exit(RC_SRV, "Unable to find {0}".format(args.dest))


def bundle_extract(src, dest):
    args = Arguments()
    args.dest = dest
    args.src = src
    do_extract_bundle(args)


def extract_bundle(args):
    args.dest = PAIE_SRV
    args.src = args.from_archive
    do_extract_bundle(args)


def main(args):
    """Paie archive environment"""
    try:
        if STANDALONE is True:
            setup_logging()
        parsed_args = parse_input(args)
        LOG.info("Running operation '%s'", ' '.join(args))
        parsed_args.func(parsed_args)
        exit(RC_SUCCESS, "Operation %s completed successfully" % args[0])
    except KeyboardInterrupt as k:
        exit(RC_USER_EXIT, "Exiting at user request ... {0}".format(k))
    #  except Exception as e:
        #  exit(RC_ERROR, "Uncaught exception: {0}".format(e))


if __name__ == "__main__":
    main(sys.argv[1:])
