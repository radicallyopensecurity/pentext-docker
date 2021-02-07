#!/bin/sh
cd "${CI_PROJECT_DIR}"

set -x
python3 /scripts/convert.py

ls -al findings/
ls -al non-findings/
ls -alR uploads/
