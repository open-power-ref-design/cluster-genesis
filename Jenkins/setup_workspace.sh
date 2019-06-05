#!/bin/bash
rm -rf $PROJECT_ROOT/pup-venv/
cd $PROJECT_ROOT &&  $PROJECT_ROOT/scripts/./venv_install.sh
$PUP_VENV/bin/pip install tox
