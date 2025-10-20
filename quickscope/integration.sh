#!/usr/bin/env bash
set -e

GIT_USER=CI
GIT_PASS=dummy
REPO_NAME=test-remote.git

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/integration"

TMPDIR="$SCRIPT_DIR/tmp"
REMOTE="$TMPDIR/remote"
SOURCE="$TMPDIR/source"

echo "* Preparing tmp dirs"
rm -rf "$TMPDIR"
mkdir -p "$REMOTE" "$SOURCE"

echo "* Cloning test repo into remote"
git -C "$SCRIPT_DIR/../../lib/pentext" \
  clone . "$REMOTE/$REPO_NAME"

git -C "$REMOTE/$REPO_NAME" config http.receivepack true

echo "* Starting git-http-backend container"
docker rm -f git-http-backend 2>/dev/null || true

docker run -d --name git-http-backend \
  -v "$REMOTE":/git \
  ynohat/git-http-backend@sha256:b6f1e3e3cc06b8ae05fc22174808dfc3b4abd567cf8bc8c8bac311d83361b041

echo "* Running quickscope"
docker run --rm --name quickscope \
  --link git-http-backend \
  -e GIT_SSL_NO_VERIFY=true \
  -e SERVER_PROTOCOL=http \
  -e CI_PROJECT_DIR=/usr/local/src/repo \
  -e CI_SERVER_HOST=git-http-backend \
  -e CI_PROJECT_PATH=git/$REPO_NAME \
  -e CI_DEFAULT_BRANCH=main \
  -e PROJECT_ACCESS_TOKEN=$GIT_PASS \
  -v "$REMOTE/$REPO_NAME":/usr/local/src/repo \
  --entrypoint ash \
  quickscope:latest \
  -c "git config --global http.receivepack true && \
      git config --global --add safe.directory /usr/local/src/repo && \
      exec /usr/local/src/quickscope2off/quickscope2off.sh"

echo "* Preparing for diff"
git -C "$SCRIPT_DIR/../../lib/pentext" \
  clone . "$SOURCE/$REPO_NAME"
docker exec -u 0 git-http-backend rm -rf "/git/$REPO_NAME/.git"
rm -rf "$SOURCE/$REPO_NAME/.git"

echo "* Creating new diff"
diff -ruN "$SOURCE/$REPO_NAME" "$REMOTE/$REPO_NAME" \
  | sed -E 's/^(---|\+\+\+) ([^[:space:]]+).*/\1 \2/' \
  > "$SCRIPT_DIR/new.diff"

echo "* Diffing with current"
diff -u \
  <(sed -E 's/date="[^"]+"/date="IGNORED"/' "$SCRIPT_DIR/current.diff" || true) \
  <(sed -E 's/date="[^"]+"/date="IGNORED"/' "$SCRIPT_DIR/new.diff" || true) \
  > "$SCRIPT_DIR/integration.diff" || test $? -eq 1

echo "* Cleaning up"
docker rm -f git-http-backend || true
rm -rf "$TMPDIR"

echo "* Found diff?"
if [ -s "$SCRIPT_DIR/integration.diff" ]; then
  echo "true"
else
  echo "false"
fi
