#! /bin/bash

# Absolute path to this script
SCRIPT=$(readlink -f "$0")
# Absolute path this script is in
BASEDIR=$(dirname "$SCRIPT")

# Run Teller
python $BASEDIR/teller.py "$@"