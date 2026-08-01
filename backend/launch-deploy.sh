#!/bin/zsh
# One-shot Cloudflare deploy for ruh-api: worker + container + secrets + health check.
# Run from anywhere:  zsh /Users/mars/Documents/github-repos/personal-saas/ruh-development/backend/launch-deploy.sh
set -e
cd /Users/mars/Documents/github-repos/personal-saas/ruh-development/backend

echo "==> [1/3] wrangler deploy (builds + pushes container image; takes a few minutes)"
wrangler deploy

echo "==> [2/3] uploading secrets from .env"
python3 - <<'PY'
import json, pathlib
env = {}
for line in pathlib.Path(".env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        env[k] = v
keys = ["ANTHROPIC_API_KEY","API_KEY","SUPABASE_URL","SUPABASE_KEY","SUPABASE_JWT_SECRET","TAVILY_API_KEY","SERPER_API_KEY","COHERE_API_KEY"]
out = {k: env[k] for k in keys if k in env}
pathlib.Path(".secrets.bulk.json").write_text(json.dumps(out))
print("prepared", len(out), "secrets")
PY
wrangler secret bulk .secrets.bulk.json
rm -f .secrets.bulk.json

echo "==> [3/3] health check (container cold start can take ~1-2 min on first hit)"
sleep 10
for i in {1..12}; do
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 30 https://api.rshvr.com/api/health || true)
  echo "  attempt $i: HTTP $code"
  [ "$code" = "200" ] && { echo "✅ ruh-api LIVE at https://api.rshvr.com"; exit 0; }
  sleep 15
done
echo "⚠️  health check not green yet — check 'wrangler tail ruh-api' for container logs"
