#! /bin/bash

# Absolute path to this script
SCRIPT=$(readlink -f "$0")
# Absolute path this script is in
BASEDIR=$(dirname "$SCRIPT")

# Export DB config
source $BASEDIR/db.conf

# Run Teller
echo python $BASEDIR/teller.py -d statements # teller.db