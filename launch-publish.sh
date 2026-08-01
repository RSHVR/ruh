#!/bin/zsh
# Publishes extension v0.3.0 to the Chrome Web Store via CI.
# Order matters: the VITE_API_KEY secret must exist BEFORE main builds.
# Run:  zsh /Users/mars/Documents/github-repos/personal-saas/ruh-development/launch-publish.sh
set -e
cd /Users/mars/Documents/github-repos/personal-saas/ruh-development

echo "==> [1/3] setting VITE_API_KEY repo secret (from backend/.env)"
set -a; source backend/.env; set +a
printf "%s" "$API_KEY" | gh secret set VITE_API_KEY -R RSHVR/ruh
echo "    secret set ✓"

echo "==> [2/3] pushing development -> main (triggers CI build + CWS publish)"
git push origin development:main

echo "==> [3/3] watching CI run"
sleep 12
RUN_ID=$(gh run list -R RSHVR/ruh -L 1 --json databaseId -q '.[0].databaseId')
gh run watch "$RUN_ID" -R RSHVR/ruh --exit-status && \
  echo "✅ v0.3.0 uploaded to Chrome Web Store (now in review)" || \
  echo "⚠️  CI run failed — check: gh run view $RUN_ID -R RSHVR/ruh --log-failed"
