#!/bin/bash

# This script is completely unused now, I think, but I'm too chicken to delete it.


set +x
set -e

cd /lake

source scripts/setenv.sh

# force color
export PYTEST_ADDOPTS="--color=yes"

echo pip install py, apt-get install verilator
set -x
yes | pip install py | head -100
apt-get update
# apt-get install verilator

echo python3 -m pycodestyle lake/
python3 -m pycodestyle lake/

echo python3 -m pycodestyle tests/
python3 -m pycodestyle tests/

echo pytest -v tests/
pytest -v tests/

set -x
