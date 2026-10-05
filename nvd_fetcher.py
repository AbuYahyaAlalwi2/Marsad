"""
nvd_fetcher.py — جلب CVEs من NVD (National Vulnerability Database)
====================================================================
⚠ هذا الملف مكتوب للتنفيذ بواسطة Qwen3-Coder

المهمة:
    جلب CVEs من https://services.nvd.nist.gov/rest/json/cves/2.0
    وحفظها في مجلد ~/Marsad/output/cves/
    بحيث يعالجها agent_output_pipeline.py تلقائياً

التوثيق الرسمي:
    https://nvd.nist.gov/developers/vulnerabilities

الإعداد (لا يحتاج API key بالنسبة للنسخة المجانية):
    - معدل مجاني: 5 طلبات / 30 ثانية
    - مع API key: 50 طلب / 30 ثانية
    - API key اختياري: https://nvd.nist.gov/developers/request-an-api-key

الاستخدام بعد التنفيذ:
    python nvd_fetcher.py --recent 100       ← آخر 100 CVE
    python nvd_fetcher.py --keyword "python" ← CVEs خاصة بـ Python
    python nvd_fetcher.py --severity HIGH    ← CVEs خطيرة فقط
    python nvd_fetcher.py --date 2024-01-01  ← من تاريخ معين
"""

import asyncio
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import aiohttp

# ─── الإعدادات ─────────────────────────────────────────────────────────────────

NVD_BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
NVD_API_KEY  = os.getenv("NVD_API_KEY", "")        # اختياري
OUTPUT_DIR   = Path.home() / "Marsad" / "output" / "cves"
RESULTS_DIR  = Path.home() / "Marsad" / "output" / "cves" / "raw"

# ─── ⬇ قسم Qwen: نفّذ هذه الوظائف ────────────────────────────────────────────
#
# التعليمات:
#   1. كل وظيفة لها توضيح كامل — لا تغيّر الـ signature
#   2. استخدم aiohttp للطلبات (مثبَّت مسبقاً)
#   3. احفظ كل CVE كملف JSON منفصل في OUTPUT_DIR
#   4. اسم الملف: {cve_id}.json مثل CVE-2024-1234.json
#   5. لا تحذف CVEs موجودة — تحقق قبل التنزيل
#
# ─────────────────────────────────────────────────────────────────────────────


async def fetch_recent_cves(
    count:   int = 50,
    api_key: str = NVD_API_KEY,
) -> list:
    """
    يجلب آخر `count` CVE من NVD.

    المخرج المطلوب:
        قائمة من dicts، كل dict هو CVE واحدة بالصيغة الأصلية من NVD

    مثال على الـ endpoint:
        GET https://services.nvd.nist.gov/rest/json/cves/2.0
            ?resultsPerPage=50
            &startIndex=0

    ملاحظة: resultsPerPage الحد الأقصى هو 2000
    """
    # ── TODO: Qwen ينفّذ هنا ─────────────────────────────────────────────────
    raise NotImplementedError("Qwen: نفّذ fetch_recent_cves")


async def fetch_cves_by_keyword(
    keyword:  str,
    count:    int = 50,
    api_key:  str = NVD_API_KEY,
) -> list:
    """
    يبحث عن CVEs بكلمة مفتاحية.

    مثال:
        await fetch_cves_by_keyword("python", 30)
        await fetch_cves_by_keyword("sql injection", 20)

    الـ endpoint يستخدم: &keywordSearch=python
    """
    # ── TODO: Qwen ينفّذ هنا ─────────────────────────────────────────────────
    raise NotImplementedError("Qwen: نفّذ fetch_cves_by_keyword")


async def fetch_cves_by_severity(
    severity: str,   # LOW | MEDIUM | HIGH | CRITICAL
    count:    int = 50,
    api_key:  str = NVD_API_KEY,
) -> list:
    """
    يجلب CVEs بمستوى خطورة محدد.

    الـ endpoint يستخدم: &cvssV3Severity=HIGH
    مستويات الخطورة: LOW (0-3.9) | MEDIUM (4-6.9) | HIGH (7-8.9) | CRITICAL (9-10)
    """
    # ── TODO: Qwen ينفّذ هنا ─────────────────────────────────────────────────
    raise NotImplementedError("Qwen: نفّذ fetch_cves_by_severity")


async def fetch_cves_since_date(
    since:   str,    # YYYY-MM-DD
    count:   int = 100,
    api_key: str = NVD_API_KEY,
) -> list:
    """
    يجلب CVEs منشورة منذ تاريخ محدد.

    الـ endpoint يستخدم:
        &pubStartDate=2024-01-01T00:00:00.000
        &pubEndDate=2024-12-31T23:59:59.999
    """
    # ── TODO: Qwen ينفّذ هنا ─────────────────────────────────────────────────
    raise NotImplementedError("Qwen: نفّذ fetch_cves_since_date")


def save_cve(cve_data: dict) -> Path:
    """
    يحفظ CVE واحدة كملف JSON.

    المدخل: dict واحد من قائمة vulnerabilities[].cve
    المخرج: مسار الملف المحفوظ

    اسم الملف يكون: {cve_id}.json
    مثال: CVE-2024-1234.json

    إذا الملف موجود → تجاهل (لا تعيد الكتابة)

    بنية CVE في NVD:
        {
          "id": "CVE-2024-1234",
          "descriptions": [{"lang": "en", "value": "..."}],
          "metrics": {
            "cvssMetricV31": [{"cvssData": {"baseScore": 7.5, ...}}]
          },
          "published": "2024-01-15T00:00:00.000",
          ...
        }
    """
    # ── TODO: Qwen ينفّذ هنا ─────────────────────────────────────────────────
    raise NotImplementedError("Qwen: نفّذ save_cve")


def get_cvss_score(cve_data: dict) -> float:
    """
    يستخرج درجة CVSS من CVE.
    يجرب v3.1 أولاً، ثم v3.0، ثم v2.

    يعيد 0.0 إذا لم يجد
    """
    # ── TODO: Qwen ينفّذ هنا ─────────────────────────────────────────────────
    raise NotImplementedError("Qwen: نفّذ get_cvss_score")


async def _make_nvd_request(
    params:  dict,
    api_key: str = "",
) -> dict:
    """
    يرسل طلب GET لـ NVD API مع معالجة Rate Limiting.

    Headers المطلوبة:
        إذا كان api_key موجوداً: {"apiKey": api_key}
        بدون key: بدون header خاص

    Rate Limiting:
        - بدون key: انتظر 6 ثوانٍ بين كل طلب
        - مع key: انتظر 0.6 ثانية بين كل طلب

    إذا جاء HTTP 403 أو 429: انتظر 30 ثانية ثم أعد المحاولة مرة واحدة
    """
    # ── TODO: Qwen ينفّذ هنا ─────────────────────────────────────────────────
    raise NotImplementedError("Qwen: نفّذ _make_nvd_request")


# ─── سطر الأوامر (جاهز — لا تعدّله) ─────────────────────────────────────────

async def _main():
    import sys
    args = sys.argv[1:]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    if not args or "--help" in args:
        print("nvd_fetcher.py — جلب CVEs من NVD")
        print()
        print("الاستخدام:")
        print("  python nvd_fetcher.py --recent  [count=50]")
        print("  python nvd_fetcher.py --keyword <keyword> [count=50]")
        print("  python nvd_fetcher.py --severity HIGH|CRITICAL|MEDIUM|LOW [count=50]")
        print("  python nvd_fetcher.py --date    YYYY-MM-DD [count=100]")
        print()
        print("متغيرات البيئة:")
        print("  NVD_API_KEY=xxx  ← يرفع الحد من 5 إلى 50 طلب/30ث")
        return

    cves = []

    if "--recent" in args:
        idx   = args.index("--recent")
        count = int(args[idx + 1]) if idx + 1 < len(args) and args[idx + 1].isdigit() else 50
        print(f"جلب آخر {count} CVE...")
        cves = await fetch_recent_cves(count)

    elif "--keyword" in args:
        idx     = args.index("--keyword")
        keyword = args[idx + 1]
        count   = int(args[idx + 2]) if idx + 2 < len(args) and args[idx + 2].isdigit() else 50
        print(f"بحث عن '{keyword}'...")
        cves = await fetch_cves_by_keyword(keyword, count)

    elif "--severity" in args:
        idx      = args.index("--severity")
        severity = args[idx + 1].upper()
        count    = int(args[idx + 2]) if idx + 2 < len(args) and args[idx + 2].isdigit() else 50
        print(f"جلب CVEs بمستوى {severity}...")
        cves = await fetch_cves_by_severity(severity, count)

    elif "--date" in args:
        idx   = args.index("--date")
        since = args[idx + 1]
        count = int(args[idx + 2]) if idx + 2 < len(args) and args[idx + 2].isdigit() else 100
        print(f"جلب CVEs منذ {since}...")
        cves = await fetch_cves_since_date(since, count)

    else:
        print(f"أمر غير معروف. استخدم --help")
        return

    saved = 0
    for cve in cves:
        try:
            path = save_cve(cve)
            score = get_cvss_score(cve)
            cve_id = cve.get("id", "unknown")
            print(f"  ✓ {cve_id} — CVSS {score}")
            saved += 1
        except Exception as e:
            print(f"  ✗ خطأ: {e}")

    print(f"\n✅ تم حفظ {saved}/{len(cves)} CVE في {OUTPUT_DIR}")
    print(f"   سيعالجها agent_output_pipeline.py تلقائياً عند التشغيل")


if __name__ == "__main__":
    asyncio.run(_main())
