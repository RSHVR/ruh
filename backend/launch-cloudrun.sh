#!/bin/zsh
# Revive ruh-api on Cloud Run at the ORIGINAL URL (published extension v0.2.2 depends on it).
# Prereq: gcloud auth login (interactive). Run:
#   zsh /Users/mars/Documents/github-repos/personal-saas/ruh-development/backend/launch-cloudrun.sh
set -e
cd /Users/mars/Documents/github-repos/personal-saas/ruh-development/backend

PID=$(gcloud projects list --filter="projectNumber=948739110049" --format="value(projectId)")
[ -z "$PID" ] && { echo "❌ could not resolve GCP project for number 948739110049"; exit 1; }
echo "==> project: $PID"

# Build env-var flags from .env (skip localhost-only + unused vars)
ENVFLAGS=$(python3 - <<'PY'
import pathlib
env = {}
for line in pathlib.Path(".env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        env[k] = v
keys = ["ANTHROPIC_API_KEY","API_KEY","SUPABASE_URL","SUPABASE_KEY","TAVILY_API_KEY","SERPER_API_KEY","COHERE_API_KEY"]
pairs = [f"{k}={env[k]}" for k in keys if k in env]
pairs.append("ALLOWED_ORIGINS=chrome-extension://mjgicecpbfabjaebiaioaijelbepihcl,https://rshvr.com")
pairs.append("DEBUG=false")
print("@".join(pairs))
PY
)

echo "==> deploying ruh-api to Cloud Run (us-central1) from source"
gcloud run deploy ruh-api \
  --source . \
  --region us-central1 \
  --project "$PID" \
  --allow-unauthenticated \
  --memory 1Gi \
  --set-env-vars "^@^${ENVFLAGS}"

echo "==> health check"
for i in {1..8}; do
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 30 https://ruh-api-948739110049.us-central1.run.app/api/health || true)
  echo "  attempt $i: HTTP $code"
  [ "$code" = "200" ] && { echo "✅ Cloud Run ruh-api LIVE at original URL"; exit 0; }
  sleep 15
done
echo "⚠️  not green yet — check Cloud Run logs"
