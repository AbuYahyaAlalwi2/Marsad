#!/data/data/com.termux/files/usr/bin/bash
# يرسل أمر تحكم لحلقة Self-Play على Kaggle ويطبع آخر حالة.
# استخدام: ./control_send.sh run | pause | stop | status
# التوكن يُقرأ من ملف (افتراضياً ~/.marsad_secrets/hf_token بصلاحية 600)، ولا يمر على سطر الأوامر.
set -euo pipefail

ACTION="${1:-status}"
case "$ACTION" in
  run|pause|stop|status) ;;
  *) echo "أمر غير صالح: المسموح run | pause | stop | status" >&2; exit 2 ;;
esac

REPO="${MARSAD_CONTROL_REPO:-AbuYahya2/marsad-endpoints}"
TOKEN_FILE="${HF_TOKEN_FILE:-$HOME/.marsad_secrets/hf_token}"

if [ ! -r "$TOKEN_FILE" ]; then
  echo "ملف التوكن غير موجود: $TOKEN_FILE" >&2; exit 1
fi
PERM="$(stat -c %a "$TOKEN_FILE" 2>/dev/null || echo 000)"
case "$PERM" in
  600|400) ;;
  *) echo "صلاحيات ملف التوكن ($PERM) غير آمنة. نفّذ: chmod 600 $TOKEN_FILE" >&2; exit 1 ;;
esac

if [ "${DRY_RUN:-0}" = "1" ]; then
  echo "تجربة بلا إرسال: الأمر $ACTION إلى $REPO"; exit 0
fi

mkdir -p "$HOME/.cache"
TMP="$(mktemp -d "${TMPDIR:-$HOME/.cache}/marsad.XXXXXX")"     # /tmp غير موجود في Termux
trap 'rm -rf "$TMP"' EXIT
if [ "$ACTION" != "status" ]; then
  printf '{"action": "%s"}\n' "$ACTION" > "$TMP/commands.json"
fi

ACTION="$ACTION" REPO="$REPO" TOKEN_FILE="$TOKEN_FILE" TMP="$TMP" python3 - << 'PY'
import json, os
from huggingface_hub import HfApi, hf_hub_download

tok = open(os.environ["TOKEN_FILE"]).read().strip()
repo, action, tmp = os.environ["REPO"], os.environ["ACTION"], os.environ["TMP"]
if action != "status":
    HfApi(token=tok).upload_file(path_or_fileobj=f"{tmp}/commands.json", path_in_repo="commands.json",
                                 repo_id=repo, repo_type="dataset")
    print("أُرسل الأمر:", action)
try:
    p = hf_hub_download(repo, "status.json", repo_type="dataset", token=tok, force_download=True)
    print("آخر حالة:", json.load(open(p)))
except Exception as e:
    print("لا توجد حالة بعد:", type(e).__name__)
PY
