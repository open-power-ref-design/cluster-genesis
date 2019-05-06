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


PAIE_SRV = "/srv/"
ENG_MODE = True
COMPRESSION = "gz"
RC_SUCCESS = 0
RC_ERROR = 99  # generic failure
RC_ARGS = 2  # failed to parse args given
RC_SRV = 20  # srv directory does not exist
RC_USER_EXIT = 40  # keyboard exit
RC_PERMISSION = 41  # Permission denied
PAIE_EXTRACT_SRV = "/tmp/srv/"
LOG = ""
STANDALONE = True
LOGFILE = os.path.splitext(os.path.basename(__file__))[0] + ".log"
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
            elif rc == RC_PERMISSION:
                raise PermissionError(err)
            else:  # rc == RC_ERROR:
                raise Exception(err)


def get_top_level_dirs(thing, include=None):
    if include is None:
        include = []
    if not thing:
        thing = os.getcwd()
    return [name for name in os.listdir(thing)
            if os.path.isdir(os.path.join(thing, name)) and name in include]


def get_top_level_dir_list_from_tar(extract_file):
    with tarfile.open(extract_file) as tarlist:
        tar_list_names = tarlist.getnames()
        toplevel = [t.split("/")[0] for t in tar_list_names]
        toplevel = set(toplevel)
        return toplevel


def validate_directories(root_dir, extract_file):
    return get_top_level_dirs(root_dir,
                              get_top_level_dir_list_from_tar(extract_file))


def discern_lists(root_dir, tar_list_dirs):
    in_list = []
    for r in root_dir:
        if r in tar_list_dirs:
            in_list.append(r)
    return in_list


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
        LOG.debug("Completed unarchiving {0} to {1}".format(src, dest))
    except PermissionError as e:
        exit(RC_PERMISSION, "unable to write to {1}\n{0}".format(e, dest))
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
    formatString = '%(asctime)s - %(levelname)s - %(message)s'
    ch = logging.StreamHandler()
    formatter = logging.Formatter(formatString)
    ch.setFormatter(formatter)
    LOG.addHandler(ch)
    #  setup file handler
    rfh = logging.FileHandler(filename=LOGFILE)
    rfh.setFormatter(logging.Formatter(formatString))
    LOG.addHandler(rfh)


def parse_input(args):
    parser = argparse.ArgumentParser(description="Utility for Archiving/Unarchiving\
                                     WMLA Node Deployer environment")
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

    add_subparser('bundle', "Bundle WMLA software, assume bundle from {0} directory".format(PAIE_SRV),
                  [('to', 'bundle WMLA software to?', True)])

    subparsers.choices['bundle'].add_argument('--compress', dest="compress",
                                              required=False, action="store_true",
                                              help='compress using gzip')

    add_subparser('extract_bundle', "Extract bundle WMLA software assume to {0}".format(PAIE_SRV),
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
        extlist = get_top_level_dir_list_from_tar(args.src)
        get_top_level_dirs(PAIE_SRV, extlist)
        with tarfile.open(args.src) as tarlist:
            for i in tarlist:
                LOG.info(i.name)
    except Exception as e:
        exit(RC_ERROR, "{0}".format(e))


def archive(args):
    dir_path = args.dest
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
            LOG.debug("not compressing")

        try:
            timestr = time.strftime("%Y_%m%d-%H_%M_%S")
            nameis = "wmla" + "." + timestr + ".tar" + (".gz" if args.compress else "")
            filename = dir_path + nameis
            LOG.info("archiving {0} to {1}".format(args.path, filename))
            start = time.time()
            archive_this(args.path, fileObj=fileobj, compress=args.compress)
            end = time.time()
        except Exception as e:
            if fileobj is not None:
                try:
                    os.unlink(fileobj.name)
                except:
                    pass
            exit(RC_ERROR, "Uncaught exception: {0}".format(e))
        else:
            os.rename(fileobj.name, filename)
            LOG.info("created: {0}, size in bytes: {1}, total time: {2} seconds".format(filename,
                                                                                        os.stat(filename).st_size,
                                                                                        int((end - start))))
        finally:
            if fileobj is not None:
                fileobj.close()
    except KeyboardInterrupt as e:
        try:
            os.unlink(fileobj.name)
        except:
            pass
        raise e
    except Exception as e:
        raise e
    return fileobj


def unarchive(args):
    unarchive_this(args.src, args.dest)


def do_bundle(args):
    LOG.debug("bundle : {0}".format(args))
    if os.path.isdir(args.path):
        return archive(args)
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
    return do_bundle(args)


def bundle(args):
    args.path = PAIE_SRV
    args.dest = args.to
    return do_bundle(args)


def do_extract_bundle(args):
    LOG.debug("unarchiving : {0}".format(args))
    if os.path.isdir(args.dest):
        unarchive(args)
    else:
        exit(RC_SRV, "Unable to find {0}".format(args.dest))


def bundle_extract(src, dest):
    args = Arguments()
    args.src = src
    args.dest = dest
    do_extract_bundle(args)


def extract_bundle(args):
    args.dest = PAIE_SRV
    args.src = args.from_archive
    do_extract_bundle(args)


def main(args):
    """Paie archive environment"""
    try:
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
    STANDALONE = True
    main(sys.argv[1:])
