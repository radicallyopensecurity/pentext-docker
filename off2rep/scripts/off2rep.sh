#!/bin/sh
set -e
cd "$CI_PROJECT_DIR"

java -jar /saxon.jar  -s:source/offerte.xml -xsl:xslt/off2rep.xsl -o:source/report.xml -xi

git add source/report.xml
git config user.name "GitLab CI"
git config user.email "infra+ci@radicallyopensecurity.com"
git commit -m "convert pentext offerte to report"
git remote -v

git remote rm origin
git remote add origin "https://CI:${PROJECT_ACCESS_TOKEN}@${CI_SERVER_HOST}/${CI_PROJECT_PATH}"

git push origin HEAD:${CI_DEFAULT_BRANCH}
