#!/bin/sh
cd "${CI_PROJECT_DIR}"

set -e
set -x
python3 /convert.py

ls -al findings/
ls -al non-findings/
ls -alR uploads/
