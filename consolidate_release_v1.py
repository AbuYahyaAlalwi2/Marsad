#!/usr/bin/env python3
"""
consolidate_release_v1.py — يدمج كل دفعات mutations_stream/* في إصدار واحد نظيف:
  إزالة التكرار عبر الدورات + سقف لكل مشروع + تقسيم عالمي حسب المشروع + NOTICE + نصوص الرخص.
الاستعمال:
  python3 consolidate_release_v1.py --out release [--stream-dir DIR]      # DIR محلي لاختبار بلا شبكة
  HF_TOKEN=... python3 consolidate_release_v1.py --out release --hf-repo AbuYahya2/Marsad --upload release_latest
"""
import argparse, glob, os, shutil, subprocess, sys, tempfile


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="release")
    ap.add_argument("--stream-dir")
    ap.add_argument("--hf-repo")
    ap.add_argument("--prefix", default="mutations_stream")
    ap.add_argument("--upload")
    ap.add_argument("--cap-per-repo", default="800")
    ap.add_argument("--cap-real-per-repo", default="300")
    a = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix="consol_")
    if a.stream_dir:
        root = a.stream_dir
    else:
        from huggingface_hub import snapshot_download
        snapshot_download(repo_id=a.hf_repo, repo_type="dataset", allow_patterns=f"{a.prefix}/**", local_dir=tmp + "/dl",
                          token=os.environ["HF_TOKEN"])
        root = os.path.join(tmp, "dl", a.prefix)
    inp = os.path.join(tmp, "in"); os.makedirs(inp)
    n = 0
    for cyc in sorted(os.listdir(root)):
        cd = os.path.join(root, cyc)
        if not os.path.isdir(cd):
            continue
        for part in ("train", "eval"):
            f = os.path.join(cd, part + ".jsonl.gz")
            if os.path.exists(f) and os.path.getsize(f) > 40:
                shutil.copyfile(f, os.path.join(inp, f"muttriples_{cyc}_{part}.jsonl.gz")); n += 1
        for lp in glob.glob(os.path.join(cd, "licenses", "*.LICENSE.txt")):
            nm = os.path.basename(lp)[:-len(".LICENSE.txt")]
            shutil.copyfile(lp, os.path.join(inp, f"license_{nm}.txt"))
    print(f"cycles files merged: {n}")
    here = os.path.dirname(os.path.abspath(__file__))
    r = subprocess.run([sys.executable, os.path.join(here, "build_mut_bundle_v5.py"), "--in-dir", inp, "--out-dir", a.out,
                        "--specs", "--cap-per-repo", a.cap_per_repo, "--cap-real-per-repo", a.cap_real_per_repo])
    if r.returncode != 0:
        sys.exit("bundle build failed")
    if a.upload:
        from huggingface_hub import HfApi
        HfApi(token=os.environ["HF_TOKEN"]).upload_folder(folder_path=a.out, path_in_repo=a.upload, repo_id=a.hf_repo, repo_type="dataset",
                                                         delete_patterns="*", commit_message="consolidated release")
        print("uploaded to", a.upload)
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
