"""
nvd_fetcher.py — جلب CVEs من NVD (National Vulnerability Database)
====================================================================
⚠ هذا الملف مكتوب للتنفيذ بواسطة Qwen3-Coder
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
NVD_API_KEY  = os.getenv("NVD_API_KEY", "")
OUTPUT_DIR   = Path.home() / "Marsad" / "output" / "cves"
RESULTS_DIR  = Path.home() / "Marsad" / "output" / "cves" / "raw"

async def _make_nvd_request(params: dict, api_key: str = "") -> dict:
    headers = {}
    if api_key:
        headers["apiKey"] = api_key
    delay = 0.6 if api_key else 6.0
    
    async with aiohttp.ClientSession() as session:
        for attempt in range(2):
            try:
                async with session.get(NVD_BASE_URL, params=params, headers=headers) as response:
                    if response.status in [403, 429]:
                        if attempt == 0:
                            print("⚠️ NVD Rate Limit reached. Waiting 30 seconds...")
                            await asyncio.sleep(30)
                            continue
                        else:
                            print("❌ NVD API request failed after retry.")
                            return {}
                    response.raise_for_status()
                    data = await response.json()
                    await asyncio.sleep(delay)
                    return data
            except aiohttp.ClientError as e:
                print(f"❌ NVD Network Error: {e}")
                return {}
    return {}

async def fetch_recent_cves(count: int = 50, api_key: str = NVD_API_KEY) -> list:
    params = {"resultsPerPage": count, "startIndex": 0}
    data = await _make_nvd_request(params, api_key)
    return [item['cve'] for item in data.get('vulnerabilities', [])]

async def fetch_cves_by_keyword(keyword: str, count: int = 50, api_key: str = NVD_API_KEY) -> list:
    params = {"keywordSearch": keyword, "resultsPerPage": count, "startIndex": 0}
    data = await _make_nvd_request(params, api_key)
    return [item['cve'] for item in data.get('vulnerabilities', [])]

async def fetch_cves_by_severity(severity: str, count: int = 50, api_key: str = NVD_API_KEY) -> list:
    params = {"cvssV3Severity": severity.upper(), "resultsPerPage": count, "startIndex": 0}
    data = await _make_nvd_request(params, api_key)
    return [item['cve'] for item in data.get('vulnerabilities', [])]

async def fetch_cves_since_date(since: str, count: int = 100, api_key: str = NVD_API_KEY) -> list:
    start_date = f"{since}T00:00:00.000"
    end_date = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.999')
    params = {"pubStartDate": start_date, "pubEndDate": end_date, "resultsPerPage": count, "startIndex": 0}
    data = await _make_nvd_request(params, api_key)
    return [item['cve'] for item in data.get('vulnerabilities', [])]

def save_cve(cve_data: dict) -> Path:
    cve_id = cve_data.get("id", "unknown")
    file_path = OUTPUT_DIR / f"{cve_id}.json"
    if file_path.exists():
        return file_path
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(cve_data, f, ensure_ascii=False, indent=2)
    return file_path

def get_cvss_score(cve_data: dict) -> float:
    metrics = cve_data.get("metrics", {})
    if "cvssMetricV31" in metrics and metrics["cvssMetricV31"]:
        return metrics["cvssMetricV31"][0].get("cvssData", {}).get("baseScore", 0.0)
    if "cvssMetricV30" in metrics and metrics["cvssMetricV30"]:
        return metrics["cvssMetricV30"][0].get("cvssData", {}).get("baseScore", 0.0)
    if "cvssMetricV2" in metrics and metrics["cvssMetricV2"]:
        return metrics["cvssMetricV2"][0].get("cvssData", {}).get("baseScore", 0.0)
    return 0.0

# ─── سطر الأوامر (جاهز — لا تعدّله) ─────────────────────────────────────────
async def _main():
    import sys
    args = sys.argv[1:]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    if not args or "--help" in args:
        print("nvd_fetcher.py — جلب CVEs من NVD")
        return

    cves = []
    if "--recent" in args:
        idx = args.index("--recent")
        count = int(args[idx + 1]) if idx + 1 < len(args) and args[idx + 1].isdigit() else 50
        print(f"جلب آخر {count} CVE...")
        cves = await fetch_recent_cves(count)
    elif "--keyword" in args:
        idx = args.index("--keyword")
        keyword = args[idx + 1]
        count = int(args[idx + 2]) if idx + 2 < len(args) and args[idx + 2].isdigit() else 50
        print(f"بحث عن '{keyword}'...")
        cves = await fetch_cves_by_keyword(keyword, count)
    elif "--severity" in args:
        idx = args.index("--severity")
        severity = args[idx + 1].upper()
        count = int(args[idx + 2]) if idx + 2 < len(args) and args[idx + 2].isdigit() else 50
        print(f"جلب CVEs بمستوى {severity}...")
        cves = await fetch_cves_by_severity(severity, count)
    elif "--date" in args:
        idx = args.index("--date")
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

if __name__ == "__main__":
    asyncio.run(_main())
