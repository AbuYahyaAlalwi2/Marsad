#!/data/data/com.termux/files/usr/bin/bash
# نشر المصنع على Railway من الهاتف. لا يطبع أي سر.
set -e
cd "$(dirname "$0")"
set -a; . ~/.marsad_secrets/all.env; set +a
GHT="${GH_TOKEN:-${GITHUB_TOKEN:-${GITHUB_PAT:-${GH_PAT:-}}}}"
if [ -z "$GHT" ]; then echo "لم أجد رمز GitHub في all.env. الأسماء المرشّحة:"; cut -d= -f1 ~/.marsad_secrets/all.env | grep -iE "git|gh_"; exit 1; fi
P=fa03b283-b265-4a51-9c42-68b90c1edbf0; E=production; S=marsad-factory
railway variables --set "GH_TOKEN=$GHT" --project "$P" --environment "$E" --service "$S" --skip-deploys >/dev/null 2>&1 \
  || railway variables --set "GH_TOKEN=$GHT" --service "$S" >/dev/null 2>&1 \
  || { echo "تعذّر ضبط GH_TOKEN عبر CLI: أضفه يدوياً في لوحة Railway (خدمة marsad-factory > Variables)"; }
railway up --project "$P" --environment "$E" --service "$S" --detach
echo "تم الإرسال. المراقبة: python3 factory_ctl.py status"
