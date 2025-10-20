#!/usr/bin/env ash

set -e
cd "$CI_PROJECT_DIR"

java -jar /saxon.jar  -s:source/quickscope.xml -xsl:xslt/qs2offerte.xsl -o:source/offerte.xml -xi

git add source/offerte.xml
git config user.name "GitLab CI"
git config user.email "infra+ci@radicallyopensecurity.com"
git commit -m "convert pentext quickscope to offerte"
git remote -v

git remote rm origin
git remote add origin "${SERVER_PROTOCOL:-https}://CI:${PROJECT_ACCESS_TOKEN}@${CI_SERVER_HOST}/${CI_PROJECT_PATH}"

git push origin HEAD:refs/heads/${CI_DEFAULT_BRANCH}
