#!/usr/bin/env python3
"""تحكم عن بُعد بالمصنع من الهاتف (Termux): يحتاج HF_TOKEN في البيئة.
  python3 factory_ctl.py status            يطبع نبض المصنع
  python3 factory_ctl.py off | on          إيقاف/تشغيل الدورات (الحلقة تنتظر ولا تُقتل)
  python3 factory_ctl.py set workers=2 batch=6
  python3 factory_ctl.py seeds name=url ...  بذور أولوية (مشاريع) تُستهلك في الدورة القادمة
"""
import json, os, sys
from huggingface_hub import HfApi, hf_hub_download
from huggingface_hub.utils import EntryNotFoundError

REPO, TOK = os.environ.get("HF_REPO", "AbuYahya2/Marsad"), os.environ["HF_TOKEN"]
api = HfApi(token=TOK)


def get(p):
    try:
        return open(hf_hub_download(REPO, p, repo_type="dataset", token=TOK, force_download=True)).read()
    except EntryNotFoundError:
        return None


def put(p, t):
    api.upload_file(path_or_fileobj=t.encode(), path_in_repo=p, repo_id=REPO, repo_type="dataset", commit_message="ctl " + p)


cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
if cmd == "status":
    print(get("factory/status.json")); print(get("factory/control.json"))
elif cmd in ("on", "off"):
    c = json.loads(get("factory/control.json") or "{}"); c["enabled"] = cmd == "on"; put("factory/control.json", json.dumps(c)); print(c)
elif cmd == "set":
    c = json.loads(get("factory/control.json") or "{}")
    for kv in sys.argv[2:]:
        k, v = kv.split("="); c[k] = int(v)
    put("factory/control.json", json.dumps(c)); print(c)
elif cmd == "seeds":
    cur = (get("factory/seeds.txt") or "").strip()
    put("factory/seeds.txt", "\n".join([x for x in [cur] if x] + sys.argv[2:]) + "\n"); print("seeds queued")
