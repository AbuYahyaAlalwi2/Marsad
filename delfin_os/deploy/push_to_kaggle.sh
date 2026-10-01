#!/data/data/com.termux/files/usr/bin/bash
# رفع النوت بوك إلى Kaggle كـ Kernel من Termux.
# يفحص قبل الرفع: صحة الميتاداتا، وغياب أي سر داخل النوت بوك. (تحديثات الكود تُرفع عبر git،
# ثم تغيّر السر MARSAD_REF إلى بصمة الـ commit الجديد بعد مراجعتك.)
set -euo pipefail
cd "$(dirname "$0")"

for f in marsad_kaggle_notebook.ipynb kernel-metadata.json; do
  [ -f "$f" ] || { echo "ملف مفقود: $f" >&2; exit 1; }
done

python3 - << 'PY'
import json, re, sys
meta = json.load(open("kernel-metadata.json", encoding="utf-8"))
for k in ("id", "title", "code_file", "kernel_type"):
    if not meta.get(k):
        sys.exit(f"حقل ناقص في kernel-metadata.json: {k}")
if meta["code_file"] != "marsad_kaggle_notebook.ipynb":
    sys.exit("code_file لا يطابق اسم النوت بوك")
if not meta.get("is_private", False):
    sys.exit("النوت بوك يجب أن يبقى خاصاً (is_private: true)")
nb = json.load(open("marsad_kaggle_notebook.ipynb", encoding="utf-8"))
# نفحص الكود بعد فك JSON (النص الخام يُهرّب علامات الاقتباس فيُفلت منه السر)
raw = "\n".join("".join(c.get("source", [])) for c in nb["cells"])
raw += "\n" + json.dumps(nb, ensure_ascii=False)
patterns = [r"gh[pousr]_[A-Za-z0-9]{30,}", r"github_pat_[A-Za-z0-9_]{40,}", r"hf_[A-Za-z0-9]{30,}",
            r"sk-[A-Za-z0-9_\-]{20,}", r"AKIA[0-9A-Z]{16}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
            r"HF_TOKEN\s*=\s*[\"'\\\\]+[^\"'\\\\\s]+"]
for p in patterns:
    if re.search(p, raw):
        sys.exit("وُجد سر محتمل داخل النوت بوك. انقله إلى Kaggle Secrets قبل الرفع.")
print("✓ فحص ما قبل الرفع سليم")
PY

if [ "${DRY_RUN:-0}" = "1" ]; then echo "تجربة بلا رفع"; exit 0; fi

if ! command -v kaggle >/dev/null 2>&1; then
  pip install --user -q kaggle
  export PATH="$HOME/.local/bin:$PATH"
fi
[ -f "$HOME/.kaggle/kaggle.json" ] || { echo "ضع kaggle.json في ~/.kaggle/ أولاً (Kaggle > Settings > API)" >&2; exit 1; }
chmod 600 "$HOME/.kaggle/kaggle.json"

DEST="$HOME/Marsad/kaggle-deploy"
mkdir -p "$DEST"
cp marsad_kaggle_notebook.ipynb kernel-metadata.json "$DEST/"
kaggle kernels push -p "$DEST"
echo "تم الرفع — تابع الحالة على kaggle.com/code"
