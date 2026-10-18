#!/usr/bin/env bash
# ينشر لوحة التحكم كـWorker على حساب Cloudflare الأول. يُنفَّذ من مجلد الملف (dash/).
set -euo pipefail
set -a; . "$HOME/.marsad_secrets/all.env"; set +a
GH_TOKEN="${GH_TOKEN:-${GITHUB_TOKEN:-}}"
: "${CF_ACCOUNT_1:?}" "${CF_TOKEN_1:?}" "${HF_TOKEN:?}" "${GH_TOKEN:?}"
NAME=marsad-dash; API="https://api.cloudflare.com/client/v4/accounts/$CF_ACCOUNT_1"
H=(-H "Authorization: Bearer $CF_TOKEN_1")
if [ -z "${DASH_PASS:-}" ]; then
  DASH_PASS="$(python3 -c 'import secrets;print(secrets.token_urlsafe(12))')"
  echo "DASH_PASS=$DASH_PASS" >> "$HOME/.marsad_secrets/all.env"; echo "كلمة مرور اللوحة (حُفظت في all.env): $DASH_PASS"
fi
echo "1) رفع الكود"
curl -sS -X PUT "$API/workers/scripts/$NAME" "${H[@]}" \
  -F 'metadata={"main_module":"worker.js","compatibility_date":"2025-01-01"};type=application/json' \
  -F 'worker.js=@worker.js;type=application/javascript+module' | python3 -c 'import sys,json;r=json.load(sys.stdin);print("ok" if r.get("success") else r)'
for kv in "HF_TOKEN=$HF_TOKEN" "GH_TOKEN=$GH_TOKEN" "DASH_PASS=$DASH_PASS"; do
  k="${kv%%=*}"; v="${kv#*=}"
  printf '{"name":"%s","text":"%s","type":"secret_text"}' "$k" "$v" | curl -sS -X PUT "$API/workers/scripts/$NAME/secrets" "${H[@]}" -H 'content-type: application/json' --data-binary @- | python3 -c 'import sys,json;r=json.load(sys.stdin);print("secret '"$k"':", "ok" if r.get("success") else r)'
done
curl -sS -X POST "$API/workers/scripts/$NAME/subdomain" "${H[@]}" -H 'content-type: application/json' -d '{"enabled":true}' >/dev/null
SUB=$(curl -sS "$API/workers/subdomain" "${H[@]}" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("result",{}).get("subdomain",""))')
echo "الرابط: https://$NAME.$SUB.workers.dev"
