#!/bin/env bash

# This script is designed to watch a folder and run commands if file changes are detected.
# The specific use case is watching a pentext folder and triggering a document re-build
# on all file changes except some temporary files and files in the git folder.
# The script will watch the current working directory.

# Usage example:
# cd target-folder; /some/path/this-script.sh "commandA && commandB"

# This script requires `inotifywait` which is available via `inotify-tools` under Debian
# and Ubuntu.

# Case insensitive regex matching against the path of the changed file
# ignore multiple forms of jedit intermediary files that end with # or ~
# ignore changes in the .git folder
# ignore temporary vim files
# TODO ignore more files, e.g. git-related?
REGEX_EXCLUDE_PATHS='(#$|~$|/\.git/|.swp$|.swx$)'

# When extending this script, take care to avoid command injection or functional
# issues when operating on unusual paths.

while true; 
do
inotifywait -r -e create,modify,move,delete --excludei "$REGEX_EXCLUDE_PATHS" "$PWD" && \
$@;
done
