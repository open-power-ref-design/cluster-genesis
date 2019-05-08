#!/bin/bash
echo "Activating power-up environment"
sed -i 's,^VIRTUAL_ENV=.*,VIRTUAL_ENV='"$PUP_VIRTUAL_ENV"',' $PYTHON_ACTIVATE
source $PYTHON_ACTIVATE
$PROJECT_ROOT/pup-venv/bin/tox

