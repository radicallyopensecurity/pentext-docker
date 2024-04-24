#!/bin/env bash

# This script is designed to run a podman container that builds pentext 
# documents from a folder that is not trustworthy. A number of hardening steps
# are used to limit the blast radius of problematic behavior.

# Note that the resulting rendered file may still be malicious in other ways.

if [ $# -eq 0 ]; then
    echo 'No arguments provided, usage: `scriptname.sh /absolute/path-to-pentext-project/ optional-additional-parameters-for-podman-run`'
    exit 1
fi

# explicitly read the UID instead of using $UID to be more compatible
CURRENT_UID=$(id -u)

# User id expected in the container
# Note that this limitation is due to a well-known design problem of docker mounts
# towards non-root container users, which has no easy general solutions
EXPECTED_UID=1000

# TODO in podman 4.3.0, --userns=keep-id has been extended to allow specific UID
# target mapping in the guest, such as --userns=keep-id:uid=1000
# The feature will likely allow a cleaner solution of mismatches between UID on 
# the host and the hardcoded target user UID in the guest
# See https://github.com/containers/podman/issues/15294
# This will take some time to become available in stable OS distributions, but
# can be added here as an alternative code path

if [ $CURRENT_UID -ne $EXPECTED_UID ]; then
    echo "Your user id $CURRENT_UID does not match the id $EXPECTED_UID that is required by the container, exiting"
    exit 1
fi

PENTEXT_FOLDER_PATH=$1
PENTEXT_OUTPUT_SUBFOLDER="/target"
# TODO allow custom project name definitions
CI_PROJECT_NAME=`basename $PENTEXT_FOLDER_PATH`

if [ ! -d "${PENTEXT_FOLDER_PATH}${PENTEXT_OUTPUT_SUBFOLDER}" ]; then
    echo "target folder missing, creating it"
    mkdir -p ${PENTEXT_FOLDER_PATH}${PENTEXT_OUTPUT_SUBFOLDER}
fi

echo "project path: ${PENTEXT_FOLDER_PATH}"
echo "project name: ${CI_PROJECT_NAME}"
echo ""

# Debug notes
# -it --entrypoint=/bin/sh

# Special properties of the container pentext generation
# * rootless podman
# * readonly filesystem except for the target folder
# * extra noexec flags
# * disable networking for the container
# * dropped root privileges inside container (defined there)
# * direct passthrough of uid permissions to container
# * do not keep persistent container results

# TODO --uidmap=0:0:1000 or similar for additional separation of rootless container id

# Note that there are no special resource limitations on the container,
# since resource exhaustion attacks are secondary concerns (for now)

podman run -e "CI_PROJECT_NAME=$CI_PROJECT_NAME" \
	   -e "CI_PROJECT_DIR=/mount" \
	   -v "${PENTEXT_FOLDER_PATH}:/mount:ro,noexec" \
	   -v "${PENTEXT_FOLDER_PATH}${PENTEXT_OUTPUT_SUBFOLDER}:/mount${PENTEXT_OUTPUT_SUBFOLDER}:rw,noexec" \
	   --userns=keep-id \
	   --network=none \
	   --rm=true \
	   "${@:2}" \
	   custom-docbuilder-experiment
