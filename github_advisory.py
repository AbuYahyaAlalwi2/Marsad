"""
github_advisory.py — جلب تحذيرات أمنية من GitHub Advisory Database
=====================================================================
⚠ هذا الملف مكتوب للتنفيذ بواسطة Qwen3-Coder

المهمة:
    جلب Security Advisories من GitHub عبر GraphQL API
    وحفظها في ~/Marsad/output/advisories/

GitHub Advisory Database:
    https://github.com/advisories
    API: https://api.github.com/graphql

لا يحتاج API key للقراءة العامة.
مع Personal Access Token: حد أعلى (5000 طلب/ساعة)

الاستخدام بعد التنفيذ:
    python github_advisory.py --recent 50
    python github_advisory.py --ecosystem python
    python github_advisory.py --severity HIGH
    python github_advisory.py --cve CVE-2024-1234    ← بحث بـ CVE ID
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiohttp

# ─── الإعدادات ─────────────────────────────────────────────────────────────────

GITHUB_GRAPHQL = "https://api.github.com/graphql"
GITHUB_REST    = "https://api.github.com/advisories"    # REST endpoint (أبسط)
GITHUB_TOKEN   = os.getenv("GITHUB_TOKEN", "")          # اختياري لكن يرفع الحد

OUTPUT_DIR  = Path.home() / "Marsad" / "output" / "advisories"

# Ecosystems المدعومة في GitHub Advisory
ECOSYSTEMS = ["PYTHON", "NPM", "RUBYGEMS", "MAVEN", "NUGET", "COMPOSER", "GO", "RUST", "ERLANG", "SWIFT"]

# ─── ⬇ قسم Qwen: نفّذ هذه الوظائف ────────────────────────────────────────────
#
# تعليمات:
#   1. استخدم REST endpoint أولاً (أبسط من GraphQL)
#      GET https://api.github.com/advisories?per_page=50&sort=published
#   2. احفظ كل advisory كملف JSON باسم {ghsa_id}.json
#      مثال: GHSA-1234-5678-abcd.json
#   3. تحقق من وجود الملف قبل الحفظ — لا تعيد التنزيل
#
# ─────────────────────────────────────────────────────────────────────────────


async def fetch_recent_advisories(
    count: int = 50,
) -> list:
    """
    يجلب آخر `count` advisory من GitHub.

    REST endpoint:
        GET https://api.github.com/advisories
            ?per_page=50
            &sort=published
            &direction=desc
            &type=reviewed          ← مراجعة فقط (أعلى جودة)

    Headers:
        Accept: application/vnd.github+json
        X-GitHub-Api-Version: 2022-11-28
        Authorization: Bearer {token}   ← فقط إذا GITHUB_TOKEN موجود

    يعيد: قائمة advisory objects
    """
    # ── TODO: Qwen ينفّذ هنا ─────────────────────────────────────────────────
    raise NotImplementedError("Qwen: نفّذ fetch_recent_advisories")


async def fetch_advisories_by_ecosystem(
    ecosystem: str,   # PYTHON | NPM | RUBYGEMS | ...
    count:     int = 50,
) -> list:
    """
    يجلب advisories لبيئة برمجية محددة.

    endpoint يضيف: &ecosystem=PYTHON

    تحقق أن ecosystem في ECOSYSTEMS list أعلاه
    إذا لم يكن موجوداً: اطبع الخيارات المتاحة وارجع قائمة فارغة
    """
    # ── TODO: Qwen ينفّذ هنا ─────────────────────────────────────────────────
    raise NotImplementedError("Qwen: نفّذ fetch_advisories_by_ecosystem")


async def fetch_advisories_by_severity(
    severity: str,   # LOW | MODERATE | HIGH | CRITICAL
    count:    int = 50,
) -> list:
    """
    يجلب advisories بمستوى خطورة محدد.

    endpoint يضيف: &severity=HIGH

    مستويات GitHub: low | moderate | high | critical
    حوّل المدخل لـ lowercase قبل الإرسال
    """
    # ── TODO: Qwen ينفّذ هنا ─────────────────────────────────────────────────
    raise NotImplementedError("Qwen: نفّذ fetch_advisories_by_severity")


async def fetch_advisory_by_cve(cve_id: str) -> Optional[dict]:
    """
    يبحث عن advisory بـ CVE ID.

    endpoint يضيف: &cve_id=CVE-2024-1234

    يعيد dict واحد أو None إذا لم يجد
    """
    # ── TODO: Qwen ينفّذ هنا ─────────────────────────────────────────────────
    raise NotImplementedError("Qwen: نفّذ fetch_advisory_by_cve")


def save_advisory(advisory: dict) -> Path:
    """
    يحفظ advisory واحد كملف JSON.

    المدخل: dict من GitHub API
    المخرج: مسار الملف المحفوظ

    اسم الملف: {ghsa_id}.json
    مثال: GHSA-1234-5678-abcd.json

    إذا الملف موجود → تجاهل

    بنية advisory في GitHub API:
        {
          "ghsa_id": "GHSA-1234-5678-abcd",
          "cve_id": "CVE-2024-1234",
          "summary": "...",
          "description": "...",
          "severity": "HIGH",
          "cvss_score": 7.5,
          "cvss_vector_string": "CVSS:3.1/AV:N/...",
          "published_at": "2024-01-15T00:00:00Z",
          "updated_at": "2024-01-16T00:00:00Z",
          "vulnerabilities": [{"package": {...}, "patched_versions": [...]}],
          "references": [{"url": "..."}],
          ...
        }
    """
    # ── TODO: Qwen ينفّذ هنا ─────────────────────────────────────────────────
    raise NotImplementedError("Qwen: نفّذ save_advisory")


def get_cvss_score(advisory: dict) -> float:
    """
    يستخرج CVSS score من advisory.

    حقل GitHub: advisory["cvss"]["score"] أو advisory["cvss_score"]
    إذا لم يجد: يحوّل severity النصي:
        CRITICAL → 9.5
        HIGH     → 7.5
        MODERATE → 5.0
        LOW      → 2.5
        unknown  → 0.0
    """
    # ── TODO: Qwen ينفّذ هنا ─────────────────────────────────────────────────
    raise NotImplementedError("Qwen: نفّذ get_cvss_score")


async def _make_github_request(
    url:    str,
    params: dict = None,
) -> list:
    """
    يرسل طلب GET لـ GitHub API مع معالجة Rate Limiting.

    Headers الأساسية:
        Accept: application/vnd.github+json
        X-GitHub-Api-Version: 2022-11-28

    إذا GITHUB_TOKEN موجود أضف:
        Authorization: Bearer {GITHUB_TOKEN}

    Rate Limiting:
        - بدون token: 60 طلب/ساعة → انتظر 1 ثانية بين الطلبات
        - مع token: 5000 طلب/ساعة → لا تأخير

    إذا جاء HTTP 403: طبع رسالة "تجاوزت الحد — انتظر ساعة أو أضف GITHUB_TOKEN"
    إذا جاء HTTP 404: أعد قائمة فارغة
    """
    # ── TODO: Qwen ينفّذ هنا ─────────────────────────────────────────────────
    raise NotImplementedError("Qwen: نفّذ _make_github_request")


# ─── سطر الأوامر (جاهز — لا تعدّله) ─────────────────────────────────────────

async def _main():
    import sys
    args = sys.argv[1:]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not args or "--help" in args:
        print("github_advisory.py — جلب Security Advisories من GitHub")
        print()
        print("الاستخدام:")
        print("  python github_advisory.py --recent    [count=50]")
        print("  python github_advisory.py --ecosystem python|npm|... [count=50]")
        print("  python github_advisory.py --severity  HIGH|CRITICAL|... [count=50]")
        print("  python github_advisory.py --cve       CVE-2024-1234")
        print()
        print(f"Ecosystems المدعومة: {', '.join(e.lower() for e in ECOSYSTEMS)}")
        print()
        print("متغيرات البيئة:")
        print("  GITHUB_TOKEN=ghp_xxx  ← يرفع الحد إلى 5000 طلب/ساعة")
        return

    advisories = []

    if "--recent" in args:
        idx   = args.index("--recent")
        count = int(args[idx + 1]) if idx + 1 < len(args) and args[idx + 1].isdigit() else 50
        print(f"جلب آخر {count} advisory...")
        advisories = await fetch_recent_advisories(count)

    elif "--ecosystem" in args:
        idx       = args.index("--ecosystem")
        ecosystem = args[idx + 1].upper()
        count     = int(args[idx + 2]) if idx + 2 < len(args) and args[idx + 2].isdigit() else 50
        print(f"جلب advisories لـ {ecosystem}...")
        advisories = await fetch_advisories_by_ecosystem(ecosystem, count)

    elif "--severity" in args:
        idx      = args.index("--severity")
        severity = args[idx + 1]
        count    = int(args[idx + 2]) if idx + 2 < len(args) and args[idx + 2].isdigit() else 50
        print(f"جلب advisories بمستوى {severity}...")
        advisories = await fetch_advisories_by_severity(severity, count)

    elif "--cve" in args:
        idx    = args.index("--cve")
        cve_id = args[idx + 1]
        print(f"البحث عن {cve_id}...")
        result = await fetch_advisory_by_cve(cve_id)
        advisories = [result] if result else []

    else:
        print("أمر غير معروف. استخدم --help")
        return

    saved = 0
    for adv in advisories:
        try:
            path  = save_advisory(adv)
            score = get_cvss_score(adv)
            ghsa  = adv.get("ghsa_id", "unknown")
            sev   = adv.get("severity", "unknown")
            print(f"  ✓ {ghsa} — {sev} — CVSS {score}")
            saved += 1
        except Exception as e:
            print(f"  ✗ خطأ: {e}")

    print(f"\n✅ تم حفظ {saved}/{len(advisories)} advisory في {OUTPUT_DIR}")
    print(f"   سيعالجها agent_output_pipeline.py تلقائياً")


if __name__ == "__main__":
    asyncio.run(_main())
