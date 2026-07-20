#!/bin/zsh
# E2E verification of the live Ruh backend. Usage:
#   zsh verify-live.sh [base_url]   (default: https://api.rshvr.com)
set -e
cd /Users/mars/Documents/github-repos/personal-saas/ruh-development/backend
BASE="${1:-https://api.rshvr.com}"
set -a; source .env; set +a

echo "== health =="
curl -s --max-time 30 "$BASE/api/health"; echo

echo "== analyze (real IKEA product, may take 60-120s on cache miss) =="
curl -s --max-time 300 -X POST "$BASE/api/analyze" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"product_url": "https://www.ikea.com/us/en/p/sniglar-crib-beech-50248541/"}' \
  | python3 -c "
import json,sys
try:
    d = json.load(sys.stdin)
except Exception as e:
    print('❌ non-JSON response:', e); sys.exit(1)
a = d.get('analysis') or {}
print('product:', a.get('product_name'))
print('overall_score:', a.get('overall_score'))
print('allergens:', len(a.get('allergens_detected') or []))
print('pfas:', len(a.get('pfas_detected') or []))
print('other_concerns:', len(a.get('other_concerns') or []))
print('cached:', d.get('cached'))
ok = isinstance(a.get('overall_score'), (int, float))
print('✅ E2E PASS' if ok else '❌ E2E FAIL — no score in response')
sys.exit(0 if ok else 1)
"
