#!/usr/bin/env python3
"""
consolidate_release_v1.py — يدمج كل دفعات mutations_stream/* في إصدار واحد نظيف:
  إزالة التكرار عبر الدورات + سقف لكل مشروع + تقسيم عالمي حسب المشروع + NOTICE + نصوص الرخص.
الاستعمال:
  python3 consolidate_release_v1.py --out release [--stream-dir DIR]      # DIR محلي لاختبار بلا شبكة
  HF_TOKEN=... python3 consolidate_release_v1.py --out release --hf-repo AbuYahya2/Marsad --upload release_latest
"""
import argparse, glob, os, shutil, subprocess, sys, tempfile


def fetch_missing_licenses(out):
    """يجلب نص الرخصة من واجهة GitHub لأي مستودع بلا ملف رخصة (المصدر الرسمي)."""
    import base64, gzip, json
    urls = {}
    for part in ("train", "eval"):
        p = os.path.join(out, part + ".jsonl.gz")
        if os.path.exists(p):
            for ln in gzip.open(p, "rt", encoding="utf-8"):
                r = json.loads(ln); urls.setdefault(r["repo"], r.get("repo_url", ""))
    os.makedirs(os.path.join(out, "licenses"), exist_ok=True)
    got, miss = 0, []
    for repo, u in sorted(urls.items()):
        dst = os.path.join(out, "licenses", repo + ".LICENSE.txt")
        if os.path.exists(dst) or "github.com/" not in u:
            if not os.path.exists(dst): miss.append(repo)
            continue
        r = subprocess.run(["gh", "api", "repos/" + u.split("github.com/")[1].strip("/") + "/license"], capture_output=True, text=True)
        try:
            txt = base64.b64decode(json.loads(r.stdout)["content"]).decode("utf-8", "replace")
            open(dst, "w", encoding="utf-8").write(txt); got += 1
        except Exception:
            miss.append(repo)
    print(f"licenses fetched from GitHub: {got}; still missing: {len(miss)} {miss[:10]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="release")
    ap.add_argument("--stream-dir")
    ap.add_argument("--hf-repo")
    ap.add_argument("--streams", nargs="*", default=["mutations_stream", "mutations_v1"])
    ap.add_argument("--upload")
    ap.add_argument("--cap-per-repo", default="800")
    ap.add_argument("--cap-real-per-repo", default="300")
    a = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix="consol_")
    roots = []
    if a.stream_dir:
        roots = [a.stream_dir]
    else:
        from huggingface_hub import snapshot_download
        snapshot_download(repo_id=a.hf_repo, repo_type="dataset", allow_patterns=[p + "/**" for p in a.streams],
                          local_dir=tmp + "/dl", token=os.environ["HF_TOKEN"])
        for p in a.streams:
            d = os.path.join(tmp, "dl", p)
            if os.path.isdir(d):
                roots.append(d)
    inp = os.path.join(tmp, "in"); os.makedirs(inp)
    n = 0
    cycles = []
    for root in roots:
        if os.path.exists(os.path.join(root, "train.jsonl.gz")):          # مجلد واحد هو دورة بذاته (مثل mutations_v1)
            cycles.append((os.path.basename(root), root))
        else:
            cycles += [(c_, os.path.join(root, c_)) for c_ in sorted(os.listdir(root)) if os.path.isdir(os.path.join(root, c_))]
    for cyc, cd in cycles:
        for part in ("train", "eval"):
            f = os.path.join(cd, part + ".jsonl.gz")
            if os.path.exists(f) and os.path.getsize(f) > 40:
                shutil.copyfile(f, os.path.join(inp, f"muttriples_{cyc}_{part}.jsonl.gz")); n += 1
        for lp in glob.glob(os.path.join(cd, "licenses", "*.LICENSE.txt")):
            nm = os.path.basename(lp)[:-len(".LICENSE.txt")]
            shutil.copyfile(lp, os.path.join(inp, f"license_{nm}.txt"))
    print(f"cycles files merged: {n}")
    here = os.path.dirname(os.path.abspath(__file__))
    r = subprocess.run([sys.executable, os.path.join(here, "build_mut_bundle_v6.py"), "--in-dir", inp, "--out-dir", a.out,
                        "--specs", "--cap-per-repo", a.cap_per_repo, "--cap-real-per-repo", a.cap_real_per_repo])
    if r.returncode != 0:
        sys.exit("bundle build failed")
    fetch_missing_licenses(a.out)
    if a.upload:
        from huggingface_hub import HfApi
        HfApi(token=os.environ["HF_TOKEN"]).upload_folder(folder_path=a.out, path_in_repo=a.upload, repo_id=a.hf_repo, repo_type="dataset",
                                                         delete_patterns="*", commit_message="consolidated release")
        print("uploaded to", a.upload)
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
