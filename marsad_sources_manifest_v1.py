#!/usr/bin/env python3
"""
marsad_sources_manifest_v1.py — ملف مصادر مرصد (روابط مثبّتة بدل نسخ البيانات)

يبني sources_manifest.json: لكل مصدر اسمه، الترخيص، رقم النسخة المثبّتة (commit SHA)،
هل هو مقيّد (gated) أو خاص، آخر تعديل، عدد ملفاته وحجمها. ويضع علامة تحذير لو تغيّر
الترخيص أو اختفى المصدر. لا يحمّل أي بيانات، ويحتاج `requests` فقط (يعمل على Termux).

الاستعمال:
  python3 marsad_sources_manifest_v1.py            # يسأل واجهة HF ويكتب sources_manifest.json
  python3 marsad_sources_manifest_v1.py --offline  # بلا شبكة: يكتب البذرة فقط
المفتاح اختياري (HF_TOKEN_1 أو HF_TOKEN من البيئة) ولا يُطبع ولا يُخزَّن.
"""
import argparse, datetime, json, os, sys

# ما "تحقق منه فعلاً" مأخوذ من بطاقات HF يوم 2026-10-12 (قراءة، لا تنفيذ). "unverified" = لم يُفحص بعد.
SEED = [
    {
        "id": "deepmind/code_contests", "kind": "hf_dataset", "status": "in_use",
        "role": "ثلاثيات (حل خاطئ/صحيح + اختبارات) بتحقق بالتنفيذ، Python3 حالياً",
        "license_seen": "cc-by-4.0",
        "verified": ["train ≈ 3.8K مسألة، ≈ 2.1GB parquet", "أعمدة: solutions / incorrect_solutions / public,private,generated_tests"],
        "unverified": [],
        "notes": "يُستعمل في marsad_triples.py. المردود المقيس: 105 ثلاثيات من 120 مسألة (نسخة 1).",
    },
    {
        "id": "open-r1/codeforces", "kind": "hf_dataset", "status": "candidate",
        "role": "مسائل Codeforces مع اختبارات رسمية ومدقّق (checker) للمسائل متعددة الأجوبة",
        "license_seen": "cc-by-4.0",
        "verified": ["config verifiable: ≈ 8.3K train / 422 test", "أعمدة: official_tests, official_tests_complete, generated_checker, executable, input_mode, editorial, rating, tags"],
        "unverified": ["كم مسألة official_tests_complete=True", "صيغة generated_checker وكيف نُجمّعه ونشغّله بأمان"],
        "notes": "مرشّح لحل مشكلة المسائل متعددة الأجوبة وللتحقق بالتنفيذ لتقديمات Codeforces.",
    },
    {
        "id": "open-r1/codeforces-submissions", "kind": "hf_dataset", "status": "candidate",
        "role": "تقديمات حقيقية (كود المصدر + قرار الحكم) لتكوين أزواج خاطئ/صحيح لنفس المسألة",
        "license_seen": "cc-by-4.0",
        "verified": ["default: ≈ 12.6M صف، ≈ 5.6GB", "selected_accepted ≈ 42.5K، selected_incorrect ≈ 18.1K",
                     "أعمدة: submission_id, source, contestId, problem_index, programmingLanguage, verdict, passedTestCount, creationTimeSeconds, problem_id",
                     "لا يوجد عمود للمستخدم => لا يمكن إثبات أن نفس الشخص أخطأ ثم أصلح"],
        "unverified": ["تطابق مفتاح الربط مع open-r1/codeforces (contest_id+index مقابل contestId+problem_index)", "توزيع اللغات", "هل الكود كامل وقابل للتشغيل"],
        "notes": "ابدأ بالنسختين selected_* الصغيرتين قبل الـ 12.6M.",
    },
    {
        "id": "OSV (osv.dev) + commits الإصلاح على GitHub", "kind": "external", "status": "in_use",
        "role": "إصلاحات ثغرات حقيقية (طبقة الأمن)", "license_seen": None,
        "verified": [], "unverified": ["ترخيص كل مصدر داخل OSV يُراجع على حدة", "التحقق الحالي pattern_only وليس تنفيذاً"],
        "notes": "historical_truth_miner_v1.py. القياس السابق: 270 عيّنة فريدة من جلسة واحدة.",
    },
    {
        "id": "CVEfixes (Zenodo)", "kind": "external", "status": "planned", "role": "دفعة أساس لطبقة الأمن",
        "license_seen": None, "verified": ["≈ 5,495 commit / 5,365 CVE حتى يونيو 2021 (من الورقة البحثية)"],
        "unverified": ["الترخيص", "توافر الأزواج قبل/بعد بالشكل المطلوب"], "notes": "",
    },
    {
        "id": "MegaVul", "kind": "external", "status": "planned", "role": "دفعة أساس لطبقة الأمن (C/C++)",
        "license_seen": None, "verified": ["≈ 9,019 commit و17,380 دالة ضعيفة حتى 2023 (من الورقة البحثية)"],
        "unverified": ["الترخيص", "مكان التحميل الرسمي"], "notes": "",
    },
]


def hf_get(session, repo_id, token):
    url = f"https://huggingface.co/api/datasets/{repo_id}?blobs=true"
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    r = session.get(url, headers=headers, timeout=30)
    return r.status_code, (r.json() if r.status_code == 200 else {})


def license_from(info):
    for t in info.get("tags", []) or []:
        if t.startswith("license:"):
            return t.split(":", 1)[1]
    return (info.get("cardData") or {}).get("license")


def enrich(entry, status_code, info):
    out = dict(entry)
    out["checked_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out["http_status"] = status_code
    flags = []
    if status_code != 200:
        flags.append("UNAVAILABLE_OR_PRIVATE")
    else:
        sib = info.get("siblings") or []
        out["pinned_revision"] = info.get("sha")
        out["last_modified"] = info.get("lastModified")
        out["gated"] = info.get("gated")
        out["license_now"] = license_from(info)
        out["files"] = len(sib)
        out["total_bytes"] = sum((s.get("size") or 0) for s in sib)
        if entry.get("license_seen") and out["license_now"] != entry["license_seen"]:
            flags.append("LICENSE_CHANGED")
        if info.get("gated"):
            flags.append("GATED")
    out["flags"] = flags
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--out", default="sources_manifest.json")
    args = ap.parse_args()
    token = os.environ.get("HF_TOKEN_1") or os.environ.get("HF_TOKEN") or ""
    session = None
    if not args.offline:
        import requests
        session = requests.Session()
    rows = []
    for e in SEED:
        if args.offline or e["kind"] != "hf_dataset":
            row = dict(e)
            row["flags"] = ["MANUAL_CHECK"] if e["kind"] != "hf_dataset" else ["NOT_CHECKED_OFFLINE"]
        else:
            try:
                code, info = hf_get(session, e["id"], token)
            except Exception as ex:
                code, info = 0, {}
                print(f"  ⚠️ {e['id']}: {type(ex).__name__}", file=sys.stderr)
            row = enrich(e, code, info)
        rows.append(row)
    manifest = {"version": 1, "sources": rows}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"{'المصدر':44} {'الترخيص':12} {'النسخة':10} {'ملفات':>6}  علامات")
    for r in rows:
        print(f"{r['id'][:44]:44} {str(r.get('license_now') or r.get('license_seen') or '-'):12} "
              f"{str(r.get('pinned_revision') or '-')[:8]:10} {str(r.get('files') or '-'):>6}  {','.join(r['flags'])}")
    print(f"\nكُتب: {args.out}")


if __name__ == "__main__":
    main()
