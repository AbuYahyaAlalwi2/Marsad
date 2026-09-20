"""
وكيل استخبارات الثغرات — كليرنت + دارك
يجمع CVE وPoC لحماية النموذج ذاتياً
"""
import os
import time
import json
import hashlib
import requests
from datetime import datetime
from typing import List, Dict, Any

try:
    from db import insert_sample, log_event
    from config import CLEARNET_VULN_SOURCES, DARKWEB_FORUMS, ENABLE_DARKWEB_MONITORING
except Exception:
    CLEARNET_VULN_SOURCES = {}
    DARKWEB_FORUMS = []
    ENABLE_DARKWEB_MONITORING = True
    def insert_sample(*a, **k): pass
    def log_event(*a, **k): pass

try:
    from agents.vpn_agent import vpn_agent
except Exception:
    vpn_agent = None

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MarsadIntel/1.0; +security-research)",
    "Accept": "application/json, text/html, */*",
}

class VulnIntelAgent:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.collected = 0

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()

    def fetch_nvd(self, limit: int = 20) -> List[dict]:
        items = []
        try:
            url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
            r = self.session.get(url, params={"resultsPerPage": limit}, timeout=30)
            if r.status_code != 200:
                return items
            data = r.json()
            for v in data.get("vulnerabilities", []):
                cve = v.get("cve", {})
                cve_id = cve.get("id", "")
                descs = cve.get("descriptions", [])
                desc = next((d["value"] for d in descs if d.get("lang") == "en"), "")
                items.append({
                    "id": cve_id,
                    "title": cve_id,
                    "content": desc[:4000],
                    "source": "nvd",
                    "url": f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                    "severity": "public",
                })
        except Exception as e:
            log_event("vuln_intel", {"source": "nvd", "error": str(e)})
        return items

    def fetch_cisa_kev(self) -> List[dict]:
        items = []
        try:
            url = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
            r = self.session.get(url, timeout=30)
            if r.status_code != 200:
                return items
            data = r.json()
            for v in data.get("vulnerabilities", [])[:30]:
                items.append({
                    "id": v.get("cveID", ""),
                    "title": f"{v.get('cveID')} — {v.get('vulnerabilityName', '')}",
                    "content": f"{v.get('shortDescription','')} | vendor={v.get('vendorProject','')} | product={v.get('product','')} | ransomware={v.get('knownRansomwareCampaignUse','')}",
                    "source": "cisa_kev",
                    "url": f"https://nvd.nist.gov/vuln/detail/{v.get('cveID','')}",
                    "severity": "public",
                })
        except Exception as e:
            log_event("vuln_intel", {"source": "cisa", "error": str(e)})
        return items

    def fetch_github_advisories(self, limit: int = 20) -> List[dict]:
        items = []
        try:
            r = self.session.get(
                "https://api.github.com/advisories",
                params={"per_page": limit},
                timeout=30,
            )
            if r.status_code != 200:
                return items
            for a in r.json():
                items.append({
                    "id": a.get("ghsa_id") or a.get("cve_id") or "",
                    "title": a.get("summary", "")[:200],
                    "content": (a.get("description") or "")[:4000],
                    "source": "github_advisories",
                    "url": a.get("html_url", ""),
                    "severity": "public",
                })
        except Exception as e:
            log_event("vuln_intel", {"source": "github", "error": str(e)})
        return items

    def fetch_exploitdb_rss_style(self) -> List[dict]:
        """مرآة GitHub لـ Exploit-DB CSV (أحدث السطور)"""
        items = []
        try:
            url = "https://raw.githubusercontent.com/offensive-security/exploitdb/main/files_exploits.csv"
            r = self.session.get(url, timeout=40)
            if r.status_code != 200:
                return items
            lines = r.text.strip().splitlines()
            # header + last 25
            for line in lines[-25:]:
                parts = line.split(",")
                if len(parts) < 5:
                    continue
                eid, file_path, desc = parts[0], parts[1], parts[2]
                items.append({
                    "id": f"EDB-{eid}",
                    "title": desc.strip('"')[:200],
                    "content": f"path={file_path} desc={desc}",
                    "source": "exploitdb",
                    "url": f"https://www.exploit-db.com/exploits/{eid}",
                    "severity": "public",
                })
        except Exception as e:
            log_event("vuln_intel", {"source": "exploitdb", "error": str(e)})
        return items

    def fetch_reddit_rss(self, sub: str = "netsec") -> List[dict]:
        items = []
        try:
            url = f"https://www.reddit.com/r/{sub}/.rss"
            r = self.session.get(url, timeout=20)
            if r.status_code != 200:
                return items
            # parse simple titles/links
            import re
            titles = re.findall(r"<title>(.*?)</title>", r.text, re.I)
            links = re.findall(r"<link>(.*?)</link>", r.text, re.I)
            for i, t in enumerate(titles[1:15]):  # skip channel title
                link = links[i + 1] if i + 1 < len(links) else ""
                items.append({
                    "id": self._hash(t)[:16],
                    "title": t[:200],
                    "content": t,
                    "source": f"reddit_{sub}",
                    "url": link,
                    "severity": "public",
                })
        except Exception as e:
            log_event("vuln_intel", {"source": f"reddit_{sub}", "error": str(e)})
        return items

    def store(self, items: List[dict]):
        for it in items:
            content = f"[{it.get('id')}] {it.get('title')}\n{it.get('content')}\nURL: {it.get('url')}"
            h = self._hash(content)
            try:
                insert_sample(
                    sha256=h,
                    content=content[:8000],
                    source=it.get("source", "vuln"),
                    platform=it.get("source", "vuln"),
                    language="text",
                    sample_type="vulnerability",
                )
                self.collected += 1
            except Exception:
                pass

    def run_cycle(self) -> dict:
        """دورة جمع واحدة — حماية ذاتية"""
        all_items = []
        sources_ok = []

        for name, fn in [
            ("nvd", self.fetch_nvd),
            ("cisa_kev", self.fetch_cisa_kev),
            ("github_advisories", self.fetch_github_advisories),
            ("exploitdb", self.fetch_exploitdb_rss_style),
            ("reddit_netsec", lambda: self.fetch_reddit_rss("netsec")),
            ("reddit_ExploitDev", lambda: self.fetch_reddit_rss("ExploitDev")),
        ]:
            try:
                items = fn()
                if items:
                    self.store(items)
                    all_items.extend(items)
                    sources_ok.append(name)
            except Exception as e:
                log_event("vuln_intel", {"source": name, "error": str(e)})

        # darkweb monitor if enabled
        if ENABLE_DARKWEB_MONITORING:
            try:
                from darkweb_agents.darkweb_monitor import DarkWebMonitor
                mon = DarkWebMonitor()
                # one-shot scrape if method exists
                if hasattr(mon, "scrape_all"):
                    mon.scrape_all()
                elif hasattr(mon, "run_once"):
                    mon.run_once()
                sources_ok.append("darkweb_monitor")
            except Exception as e:
                log_event("vuln_intel", {"source": "darkweb", "error": str(e)})

        result = {
            "status": "ok",
            "collected": len(all_items),
            "sources": sources_ok,
            "ts": time.time(),
        }
        log_event("vuln_intel", result)
        return result

vuln_intel_agent = VulnIntelAgent()
