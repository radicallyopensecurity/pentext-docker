#!/bin/sh
cd "${CI_PROJECT_DIR}"

EXTRA_ARGS=""
if [ "${MERGE_STRATEGY}" != "" ]; then
	EXTRA_ARGS="$EXTRA_ARGS --merge-strategy=${MERGE_STRATEGY}"
fi

set -e
set -x
python3 /scripts/convert.py ${EXTRA_ARGS}

ls -al findings/
ls -al non-findings/
ls -alR uploads/
