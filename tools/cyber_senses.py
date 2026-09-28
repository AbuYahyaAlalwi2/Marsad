"""cyber_senses.py — حواس سيبرانية (NVD / ExploitDB / CISA)."""
from __future__ import annotations
import os, json, time, logging
from pathlib import Path
from typing import Dict, Any, List, Optional

import httpx

logger = logging.getLogger(__name__)
CACHE = Path(os.environ.get("CG_CACHE_DIR", str(Path.home() / "marsad_cache")))
CACHE.mkdir(parents=True, exist_ok=True)

UA = {"User-Agent": "Marsad-CyberAgent/1.0 (research)"}
TIMEOUT = 20


def _cache_path(key: str) -> Path:
    return CACHE / f"{key}.json"


def _cache_get(key: str, max_age: int = 86400) -> Optional[dict]:
    p = _cache_path(key)
    if p.exists() and (time.time() - p.stat().st_mtime) < max_age:
        try:
            return json.loads(p.read_text())
        except Exception:
            return None
    return None


def _cache_set(key: str, data: dict):
    try:
        _cache_path(key).write_text(json.dumps(data))
    except Exception:
        pass


# ─── NVD (National Vulnerability Database) ─────────────────
def cve_lookup(cve_id: str) -> Dict[str, Any]:
    """يجلب تفاصيل CVE من NVD API."""
    cve_id = cve_id.upper().strip()
    cached = _cache_get(f"nvd_{cve_id}")
    if cached:
        return {**cached, "_cached": True}

    headers = dict(UA)
    api_key = os.environ.get("NVD_API_KEY")
    if api_key:
        headers["apiKey"] = api_key

    try:
        r = httpx.get(
            "https://services.nvd.nist.gov/rest/json/cves/2.0",
            params={"cveId": cve_id},
            headers=headers, timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        if not data.get("vulnerabilities"):
            return {"error": "not_found", "cve": cve_id}

        v = data["vulnerabilities"][0]["cve"]
        metrics = v.get("metrics", {})
        cvss = None
        for k in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            if k in metrics:
                cvss = metrics[k][0]["cvssData"]
                break

        desc = next((d["value"] for d in v.get("descriptions", [])
                     if d["lang"] == "en"), "")

        result = {
            "cve": cve_id,
            "description": desc,
            "published": v.get("published"),
            "cvss_score": cvss.get("baseScore") if cvss else None,
            "cvss_severity": cvss.get("baseSeverity") if cvss else None,
            "vector": cvss.get("vectorString") if cvss else None,
            "references": [r["url"] for r in v.get("references", [])][:10],
        }
        _cache_set(f"nvd_{cve_id}", result)
        return result
    except Exception as e:
        logger.warning("NVD lookup failed: %s", e)
        return {"error": str(e), "cve": cve_id}


# ─── CISA Known Exploited Vulnerabilities ──────────────────
def cisa_kev(search: str = "", limit: int = 20) -> Dict[str, Any]:
    """يبحث في CISA KEV (المستغلة فعلياً)."""
    cached = _cache_get("cisa_kev", max_age=86400 * 7)
    if not cached:
        try:
            r = httpx.get(
                "https://www.cisa.gov/sites/default/files/feeds/"
                "known_exploited_vulnerabilities.json",
                headers=UA, timeout=30,
            )
            r.raise_for_status()
            cached = r.json()
            _cache_set("cisa_kev", cached)
        except Exception as e:
            return {"error": str(e)}

    vulns = cached.get("vulnerabilities", [])
    if search:
        s = search.lower()
        vulns = [v for v in vulns
                 if s in v.get("cveID", "").lower()
                 or s in v.get("vulnerabilityName", "").lower()
                 or s in v.get("vendorProject", "").lower()]

    return {
        "total_matches": len(vulns),
        "results": vulns[:limit],
    }


# ─── ExploitDB Search (عبر GitLab mirror) ──────────────────
def exploit_search(keyword: str, limit: int = 15) -> Dict[str, Any]:
    """يبحث في ExploitDB عبر GitHub CSV."""
    cached = _cache_get("edb_csv", max_age=86400 * 3)
    if not cached:
        try:
            r = httpx.get(
                "https://gitlab.com/exploit-database/exploitdb/"
                "-/raw/main/files_exploits.csv",
                headers=UA, timeout=40,
            )
            r.raise_for_status()
            rows = []
            # CSV: id,file,description,date,author,...
            # نستخدم csv module للتعامل مع quoted fields
            import csv, io
            reader = csv.reader(io.StringIO(r.text))
            next(reader, None)  # skip header
            for parts in reader:
                if len(parts) >= 4:
                    rows.append({
                        "id": parts[0],
                        "path": parts[1],
                        "description": parts[2],
                        "date": parts[3],
                    })
            cached = {"rows": rows}
            _cache_set("edb_csv", cached)
        except Exception as e:
            return {"error": str(e)}

    rows = cached.get("rows", [])
    s = keyword.lower()
    matches = [r for r in rows if s in r["description"].lower()]
    return {"total_matches": len(matches), "results": matches[:limit]}


# ─── Threat summary ─────────────────────────────────────────
def _keywords_from_nvd(nvd: Dict[str, Any], max_kw: int = 3) -> List[str]:
    """يستخرج كلمات مفتاحية من وصف NVD للبحث في ExploitDB."""
    import re
    desc = nvd.get("description", "")
    # أسماء المنتجات الشائعة
    known = ["log4j", "apache", "struts", "spring", "tomcat", "nginx",
             "jenkins", "wordpress", "drupal", "jira", "confluence",
             "exchange", "openssl", "openssh", "sudo", "polkit",
             "chrome", "firefox", "kubernetes", "docker", "redis"]
    found = []
    low = desc.lower()
    for k in known:
        if k in low:
            found.append(k)
    # إذا لم نجد، خذ أول كلمات من الوصف
    if not found:
        words = re.findall(r"[A-Za-z]{5,}", desc)[:max_kw]
        found = words
    return found[:max_kw]


def threat_summary(cve_id: str) -> Dict[str, Any]:
    """ملخص شامل: NVD + CISA + ExploitDB."""
    nvd = cve_lookup(cve_id)
    cisa = cisa_kev(cve_id, limit=5)

    # ابحث بـ: رقم CVE + كلمات من NVD + اسم عام
    queries = [cve_id]
    queries.extend(_keywords_from_nvd(nvd))
    if not nvd.get("description"):
        queries.append("")

    all_exploits = []
    seen_ids = set()
    for q in queries:
        if not q:
            continue
        r = exploit_search(q, limit=10)
        for e in r.get("results", []):
            if e["id"] not in seen_ids:
                seen_ids.add(e["id"])
                all_exploits.append(e)
        if len(all_exploits) >= 10:
            break

    return {
        "cve": cve_id,
        "nvd": nvd,
        "cisa_exploited": cisa.get("total_matches", 0) > 0,
        "exploit_available": len(all_exploits) > 0,
        "exploits": all_exploits[:10],
        "search_queries": queries,
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(json.dumps(threat_summary(sys.argv[1]),
                         indent=2, ensure_ascii=False))
    else:
        print("usage: cyber_senses.py CVE-2024-1234")
