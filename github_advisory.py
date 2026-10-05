"""
github_advisory.py — جلب تحذيرات أمنية من GitHub Advisory Database
=====================================================================
⚠ هذا الملف مكتوب للتنفيذ بواسطة Qwen3-Coder
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
GITHUB_REST    = "https://api.github.com/advisories"
GITHUB_TOKEN   = os.getenv("GITHUB_TOKEN", "")
OUTPUT_DIR  = Path.home() / "Marsad" / "output" / "advisories"

ECOSYSTEMS = ["PYTHON", "NPM", "RUBYGEMS", "MAVEN", "NUGET", "COMPOSER", "GO", "RUST", "ERLANG", "SWIFT"]

async def _make_github_request(url: str, params: dict = None) -> list:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
        
    delay = 0.0 if GITHUB_TOKEN else 1.0
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status == 403:
                    print("❌ تجاوزت الحد — انتظر ساعة أو أضف GITHUB_TOKEN")
                    return []
                if response.status == 404:
                    return []
                    
                response.raise_for_status()
                data = await response.json()
                if delay > 0: await asyncio.sleep(delay)
                return data
        except aiohttp.ClientError as e:
            print(f"❌ GitHub Network Error: {e}")
            return []

async def fetch_recent_advisories(count: int = 50) -> list:
    params = {
        "per_page": count,
        "sort": "published",
        "direction": "desc",
        "type": "reviewed"
    }
    return await _make_github_request(GITHUB_REST, params)

async def fetch_advisories_by_ecosystem(ecosystem: str, count: int = 50) -> list:
    eco_upper = ecosystem.upper()
    if eco_upper not in ECOSYSTEMS:
        print(f"⚠️ Ecosystem غير مدعوم. الخيارات المتاحة: {', '.join(e.lower() for e in ECOSYSTEMS)}")
        return []
        
    params = {
        "per_page": count,
        "ecosystem": eco_upper,
        "sort": "published",
        "direction": "desc"
    }
    return await _make_github_request(GITHUB_REST, params)

async def fetch_advisories_by_severity(severity: str, count: int = 50) -> list:
    params = {
        "per_page": count,
        "severity": severity.lower(),
        "sort": "published",
        "direction": "desc"
    }
    return await _make_github_request(GITHUB_REST, params)

async def fetch_advisory_by_cve(cve_id: str) -> Optional[dict]:
    params = {"cve_id": cve_id}
    results = await _make_github_request(GITHUB_REST, params)
    return results[0] if results else None

def save_advisory(advisory: dict) -> Path:
    ghsa_id = advisory.get("ghsa_id", "unknown")
    file_path = OUTPUT_DIR / f"{ghsa_id}.json"
    
    if file_path.exists():
        return file_path
        
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(advisory, f, ensure_ascii=False, indent=2)
        
    return file_path

def get_cvss_score(advisory: dict) -> float:
    if "cvss" in advisory and isinstance(advisory["cvss"], dict) and "score" in advisory["cvss"]:
        return float(advisory["cvss"]["score"])
    if "cvss_score" in advisory and advisory["cvss_score"] is not None:
        return float(advisory["cvss_score"])
        
    severity_map = {
        "CRITICAL": 9.5,
        "HIGH": 7.5,
        "MODERATE": 5.0,
        "LOW": 2.5,
        "UNKNOWN": 0.0
    }
    sev = advisory.get("severity", "unknown").upper()
    return severity_map.get(sev, 0.0)

# ─── سطر الأوامر (جاهز — لا تعدّله) ─────────────────────────────────────────
async def _main():
    import sys
    args = sys.argv[1:]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not args or "--help" in args:
        print("github_advisory.py — جلب Security Advisories من GitHub")
        return

    advisories = []
    if "--recent" in args:
        idx = args.index("--recent")
        count = int(args[idx + 1]) if idx + 1 < len(args) and args[idx + 1].isdigit() else 50
        print(f"جلب آخر {count} advisory...")
        advisories = await fetch_recent_advisories(count)
    elif "--ecosystem" in args:
        idx = args.index("--ecosystem")
        ecosystem = args[idx + 1].upper()
        count = int(args[idx + 2]) if idx + 2 < len(args) and args[idx + 2].isdigit() else 50
        print(f"جلب advisories لـ {ecosystem}...")
        advisories = await fetch_advisories_by_ecosystem(ecosystem, count)
    elif "--severity" in args:
        idx = args.index("--severity")
        severity = args[idx + 1]
        count = int(args[idx + 2]) if idx + 2 < len(args) and args[idx + 2].isdigit() else 50
        print(f"جلب advisories بمستوى {severity}...")
        advisories = await fetch_advisories_by_severity(severity, count)
    elif "--cve" in args:
        idx = args.index("--cve")
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
            path = save_advisory(adv)
            score = get_cvss_score(adv)
            ghsa = adv.get("ghsa_id", "unknown")
            sev = adv.get("severity", "unknown")
            print(f"  ✓ {ghsa} — {sev} — CVSS {score}")
            saved += 1
        except Exception as e:
            print(f"  ✗ خطأ: {e}")

    print(f"\n✅ تم حفظ {saved}/{len(advisories)} advisory في {OUTPUT_DIR}")

if __name__ == "__main__":
    asyncio.run(_main())
