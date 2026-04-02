#!/usr/bin/env bash

set -e

artifacts_url="https://api.github.com/repos/$PR_C_REPO/actions/runs/$GITHUB_RUN_ID/artifacts"
artifacts_json=$(curl -s -H "Authorization: token $PR_C_TOKEN" "$artifacts_url")

diffs_id=$(echo "$artifacts_json" | jq -r '.artifacts[] | select(.name=="quickscope-diffs") | .id')
diffs_url="https://github.com/$PR_C_REPO/actions/runs/$GITHUB_RUN_ID/artifacts/$diffs_id"

if [ "$PR_QS_DIFF" = "true" ]; then
  body="**Quickscope:** Found diff. Please check the diffs: [download]($diffs_url)"
else
  body="**Quickscope:** No diff found."
fi

curl -s -H "Authorization: token $PR_C_TOKEN" \
     -H "Content-Type: application/json" \
     -d "$(jq -nc --arg body "$body" '{body: $body}')" \
     "https://api.github.com/repos/$PR_C_REPO/issues/$PR_C_NUMBER/comments"
