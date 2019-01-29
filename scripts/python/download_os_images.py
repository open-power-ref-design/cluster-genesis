#!/usr/bin/env python3
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

import argparse
import sys
import os.path
import wget
import hashlib

import lib.logger as logger
from lib.config import Config
from lib.genesis import check_os_profile, get_os_images_path, GEN_PATH, \
    get_os_image_urls
from lib.exception import UserException


def _sha1sum(file_path):
    sha1sum = hashlib.sha1()
    with open(file_path, 'rb') as file_object:
        for block in iter(lambda: file_object.read(sha1sum.block_size), b''):
            sha1sum.update(block)
    return sha1sum.hexdigest()


def download_os_images(config_path=None):
    """Download OS installation images"""

    log = logger.getlogger()
    cfg = Config(config_path)
    os_images_path = get_os_images_path() + "/"
    os_image_urls = get_os_image_urls()

    for os_profile in cfg.yield_ntmpl_os_profile():
        for os_image_url in os_image_urls:
            if check_os_profile(os_profile) in os_image_url['name']:
                for image in os_image_url['images']:
                    dest = os_images_path
                    if 'filename' in image:
                        dest += image['filename']
                    else:
                        dest += image['url'].split("/")[-1]
                    if not os.path.isfile(dest):
                        log.info(f"Downloading OS image: {image['url']}")
                        wget.download(image['url'], out=dest)
                        print('')
                        sys.stdout.flush()
                    log.info('Verifying OS image sha1sum: %s' % dest)
                    sha1sum = _sha1sum(dest)
                    if image['sha1sum'] != sha1sum:
                        msg = ('OS image sha1sum verification failed: %s' %
                               dest)
                        log.error(msg)
                        raise UserException(msg)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('config_path', default='config.yml',
                        help='Config file path.  Absolute path or relative '
                        'to power-up/')

    parser.add_argument('--print', '-p', dest='log_lvl_print',
                        help='print log level', default='info')

    parser.add_argument('--file', '-f', dest='log_lvl_file',
                        help='file log level', default='info')

    args = parser.parse_args()

    if not os.path.isfile(args.config_path):
        args.config_path = GEN_PATH + args.config_path
        print('Using config path: {}'.format(args.config_path))
    if not os.path.isfile(args.config_path):
        sys.exit('{} does not exist'.format(args.config_path))

    logger.create(args.log_lvl_print, args.log_lvl_file)
    download_os_images(args.config_path)
