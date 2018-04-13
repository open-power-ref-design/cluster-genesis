#!/usr/bin/env python
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

import yaml
from orderedattrdict.yamlutils import AttrDictYAMLLoader
import os.path
import wget
import hashlib
import sys

import lib.logger as logger
from lib.config import Config
from lib.genesis import get_os_images_path
from lib.genesis import check_os_profile
from lib.exception import UserException

OS_IMAGES_URLS_FILENAME = 'os-image-urls.yml'


def _sha1sum(file_path):
    sha1sum = hashlib.sha1()
    with open(file_path, 'rb') as file_object:
        for block in iter(lambda: file_object.read(sha1sum.block_size), b''):
            sha1sum.update(block)
    return sha1sum.hexdigest()


def download_os_images():
    """Download OS installation images"""

    log = logger.getlogger()
    os_images_path = get_os_images_path() + "/"
    os_image_urls_yaml_path = os_images_path + OS_IMAGES_URLS_FILENAME

    cfg = Config()
    os_image_urls = yaml.load(open(os_image_urls_yaml_path),
                              Loader=AttrDictYAMLLoader).os_image_urls

    for os_profile in cfg.yield_ntmpl_os_profile():
        for os_image_url in os_image_urls:
            if check_os_profile(os_profile) in os_image_url.name:
                for image in os_image_url.images:
                    dest = os_images_path
                    if 'filename' in image:
                        dest += image.filename
                    else:
                        dest += image.url.split("/")[-1]
                    if not os.path.isfile(dest):
                        log.info('Downloading OS image: %s' % image.url)
                        wget.download(image.url, out=dest)
                        print('')
                        sys.stdout.flush()
                    log.info('Verifying OS image sha1sum: %s' % dest)
                    sha1sum = _sha1sum(dest)
                    if image.sha1sum != sha1sum:
                        msg = ('OS image sha1sum verification failed: %s' %
                               dest)
                        log.error(msg)
                        raise UserException(msg)


if __name__ == '__main__':
    logger.create()

    download_os_images()
