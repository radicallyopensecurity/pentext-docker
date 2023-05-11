#!/bin/sh
cd "${CI_PROJECT_DIR}"

EXTRA_ARGS=""
if [ "${MERGE_STRATEGY}" != "" ]; then
	EXTRA_ARGS="$EXTRA_ARGS --merge-strategy=${MERGE_STRATEGY}"
fi

if [ "${INCLUDE_LABELS}" != "" ]; then
	EXTRA_ARGS="$EXTRA_ARGS --include-labels"
fi

set -e
set -x
python3 /scripts/convert.py ${EXTRA_ARGS}

ls -al findings/
ls -al non-findings/
ls -alR uploads/

# CVE-2023-21036 - Acropalypse
# Sanitize all images
find "uploads" -type f -exec python3 /scripts/sanitize-acropalypse.py {} \;
