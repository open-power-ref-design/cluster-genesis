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

import sys
import os.path
import logging
from enum import Enum

import lib.genesis as gen


class LogLevel(Enum):
    NOLOG = 'nolog'
    DEBUG = 'debug'
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    CRITICAL = 'critical'


LOG_NAME = 'gen'
LOG_PATH = os.path.join(gen.get_package_path(), 'logs')
LOG_FILE = os.path.join(LOG_PATH, 'gen')

GEN_LOG_LEVEL_FILE = 'GEN_LOG_LEVEL_FILE'
GEN_LOG_LEVEL_PRINT = 'GEN_LOG_LEVEL_PRINT'

DEFAULT_LOG_LEVEL = getattr(logging, LogLevel.DEBUG.name)
DEFAULT_FILE_HANDLER_LEVEL = LogLevel.DEBUG.value
DEFAULT_STREAM_HANDLER_LEVEL = LogLevel.DEBUG.value

FORMAT_FILE = (
    '%(asctime)s'
    ' - %(levelname)s'
    ' - %(message)s')
FORMAT_STREAM = (
    '%(levelname)s'
    ' - %(message)s')
FORMAT_DEBUG = (
    '%(asctime)s'
    ' - %(filename)s|%(funcName)s|%(lineno)d'
    ' - %(levelname)s'
    ' - %(message)s')


def create(log_level_file=None, log_level_print=None):
    if not os.path.exists(LOG_PATH):
        try:
            os.makedirs(LOG_PATH)
        except OSError as exc:
            print(
                "Error: Failed to create '{}' directory - {}".format(
                    LOG_PATH, exc),
                file=sys.stderr)
            exit(1)
    else:
        if not os.path.isdir(LOG_PATH):
            print(
                "Error: '{}' is not a directory".format(LOG_PATH),
                file=sys.stderr)
            exit(1)

    env_file = os.getenv(GEN_LOG_LEVEL_FILE)
    env_print = os.getenv(GEN_LOG_LEVEL_PRINT)

    if env_file is not None:
        level_file = env_file
    elif log_level_file is not None:
        level_file = log_level_file
    else:
        level_file = DEFAULT_FILE_HANDLER_LEVEL
    if env_print is not None:
        level_print = env_print
    elif log_level_print is not None:
        level_print = log_level_print
    else:
        level_print = DEFAULT_STREAM_HANDLER_LEVEL

    if level_file.upper() not in LogLevel.__members__.keys():
        print(
            "Error: Invalid file log level '{}'".format(level_file),
            file=sys.stderr)
        sys.exit(1)
    if level_print.upper() not in LogLevel.__members__.keys():
        print(
            "Error: Invalid print log level '{}'".format(level_print),
            file=sys.stderr)
        sys.exit(1)

    logger = getlogger()
    logger.setLevel(DEFAULT_LOG_LEVEL)

    if level_file == LogLevel.NOLOG.value:
        file_handler = logger.addHandler(logging.NullHandler())
    else:
        file_handler = logging.FileHandler(LOG_FILE)
        file_handler.setLevel(getattr(logging, level_file.upper()))
        if level_file == LogLevel.DEBUG.value:
            file_handler.setFormatter(logging.Formatter(FORMAT_DEBUG))
        else:
            file_handler.setFormatter(logging.Formatter(FORMAT_FILE))
        logger.addHandler(file_handler)

    if level_print == LogLevel.NOLOG.value:
        stream_handler = logger.addHandler(logging.NullHandler())
    else:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(getattr(logging, level_print.upper()))
        if level_print == LogLevel.DEBUG.value:
            stream_handler.setFormatter(logging.Formatter(FORMAT_STREAM))
        else:
            stream_handler.setFormatter(logging.Formatter(FORMAT_STREAM))
        logger.addHandler(stream_handler)


def getlogger():
    return logging.getLogger(LOG_NAME)


def _get_log_level(handler_type):
    for handler in logging.getLogger(LOG_NAME).handlers:
        if handler_type == handler.__class__:
            return logging.getLevelName(handler.level).lower()
    return None


def get_log_level_file():
    return _get_log_level(logging.FileHandler)


def get_log_level_print():
    return _get_log_level(logging.StreamHandler)


def get_log_level_env_var_file():
    return '{}={}'.format(
        GEN_LOG_LEVEL_FILE, _get_log_level(logging.FileHandler))


def get_log_level_env_var_print():
    return '{}={}'.format(
        GEN_LOG_LEVEL_PRINT, _get_log_level(logging.StreamHandler))


def _is_log_level_debug(handler_type):
    for handler in logging.getLogger(LOG_NAME).handlers:
        if handler_type == handler.__class__:
            if handler.level == logging.DEBUG:
                return True
            break
    return False


def is_log_level_file_debug():
    return _is_log_level_debug(logging.FileHandler)


def is_log_level_print_debug():
    return _is_log_level_debug(logging.StreamHandler)
