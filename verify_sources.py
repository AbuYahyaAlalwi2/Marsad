import os, requests
tok = os.environ.get("HF_TOKEN_1") or os.environ.get("HF_TOKEN", "")
H = {"Authorization": f"Bearer {tok}"} if tok else {}
C = ["deepmind/code_contests", "bigcode/commitpackft", "bigcode/commitpack",
     "bigcode/humanevalpack", "bigcode/starcoderdata", "codeparrot/apps",
     "benjis/bigvul", "MickyMike/cvefixes_bigvul",
     "CyberNative/Code_Vulnerability_Security_DPO",
     "google/code_x_glue_cc_defect_detection"]

def j(url):
    try:
        r = requests.get(url, headers=H, timeout=25)
        try: return r.status_code, r.json()
        except Exception: return r.status_code, {}
    except Exception as e:
        return 0, {"err": str(e)}

for ds in C:
    print("=" * 60); print(ds)
    s, m = j(f"https://huggingface.co/api/datasets/{ds}")
    if s != 200:
        print(f"  ❌ غير متاح (HTTP {s})"); continue
    lic = [t for t in m.get("tags", []) if t.startswith("license:")]
    print(f"  gated={m.get('gated')} | downloads={m.get('downloads')} | {lic}")
    s2, z = j(f"https://datasets-server.huggingface.co/size?dataset={ds}")
    if s2 == 200:
        d = z.get("size", {}).get("dataset", {})
        print(f"  rows={d.get('num_rows')} | GB={round((d.get('num_bytes_original_files') or 0)/1e9, 2)}")
    else:
        print(f"  (الحجم غير متاح: HTTP {s2})")
    s3, i = j(f"https://datasets-server.huggingface.co/info?dataset={ds}")
    if s3 == 200:
        for cfg, v in list(i.get("dataset_info", {}).items())[:3]:
            print(f"  config={cfg}: {list((v.get('features') or {}).keys())[:12]}")
