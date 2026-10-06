import os, sys, json, time, hashlib, re, http.client, urllib.parse
from pathlib import Path
from typing import List, Dict, Optional, Tuple

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
NVD_API_KEY = os.environ.get("NVD_API_KEY")
OUTPUT_DIR = Path("mined_historical_truth")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS_GH = {"Authorization": f"token {GITHUB_TOKEN}", "User-Agent": "Marsad-Miner"} if GITHUB_TOKEN else {"User-Agent": "Marsad-Miner"}
NVD_HOST = "services.nvd.nist.gov"
GH_HOST = "api.github.com"

FIX_KEYWORDS = ["fix", "patch", "sanitize", "validate", "prevent", "secure", "remediate", "resolve"]

OFFICIAL_REPOS = {
    'apache': {'log4j': 'apache/logging-log4j2', 'struts': 'apache/struts'},
    'spring': {'framework': 'spring-projects/spring-framework', 'boot': 'spring-projects/spring-boot'},
    'ghostscript': {'artifex': 'ArtifexSoftware/ghostpdl'},
    'django': {'django': 'django/django'},
    'openssl': {'openssl': 'openssl/openssl'}
}

def http_get(host: str, path: str, headers: dict = {}, timeout: int = 15) -> Optional[str]:
    """طلب HTTP خام باستخدام http.client (لا Latin-1 Bug)"""
    try:
        conn = http.client.HTTPSConnection(host, timeout=timeout)
        conn.request("GET", path, headers=headers)
        resp = conn.getresponse()
        body = resp.read().decode('utf-8', errors='replace')
        conn.close()
        if resp.status == 200:
            return body
        return None
    except Exception as e:
        print(f"   ❌ خطأ اتصال {host}: {e}")
        return None

class HistoricalTruthMiner:
    def __init__(self):
        self.stats = {"cves_processed": 0, "pairs_found": 0, "repos_skipped": 0}

    def get_cve_details(self, cve_id: str) -> Optional[Dict]:
        safe_cve = urllib.parse.quote(cve_id, safe='')
        path = f'/rest/json/cves/2.0?cveId={safe_cve}'
        headers = {'apiKey': NVD_API_KEY} if NVD_API_KEY else {}
        
        body = http_get(NVD_HOST, path, headers)
        if not body:
            return None
            
        try:
            data = json.loads(body)
            vulns = data.get("vulnerabilities", [])
            if not vulns:
                return None
                
            cve_item = vulns[0]["cve"]
            cpes = []
            for config in cve_item.get("configurations", []):
                for node in config.get("nodes", []):
                    for cpe_match in node.get("cpeMatch", []):
                        if cpe_match.get("vulnerable"):
                            cpes.append(cpe_match["criteria"])
                            
            return {
                "cve_id": cve_id,
                "cpes": cpes,
                "description": cve_item.get("descriptions", [{}])[0].get("value", "")[:500],
                "published": cve_item.get("published", "")
            }
        except Exception as e:
            print(f"   ❌ فشل تحليل {cve_id}: {e}")
            return None

    def find_github_repo_from_cpe(self, cpe: str) -> Optional[str]:
        parts = cpe.split(":")
        if len(parts) >= 5:
            vendor = parts[3].lower()
            product = parts[4].lower()
            
            # فحص القائمة الرسمية أولاً
            if vendor in OFFICIAL_REPOS:
                for key, repo in OFFICIAL_REPOS[vendor].items():
                    if key in product or product in key:
                        print(f'    مطابقة رسمية: {repo}')
                        return repo
            
            # البحث العام كخيار ثاني
            query = f"{vendor}/{product}"
            safe_query = urllib.parse.quote(query, safe='/')
            path = f"/search/repositories?q={safe_query}&per_page=1"
            
            body = http_get(GH_HOST, path, HEADERS_GH)
            if body:
                try:
                    items = json.loads(body).get("items", [])
                    if items:
                        return items[0]["full_name"]
                except:
                    pass
        return None

    def extract_fix_commit(self, repo_full_name: str, cve_description: str) -> Optional[Dict]:
        try:
            owner, repo = repo_full_name.split("/")
            keywords_query = " OR ".join(FIX_KEYWORDS[:3])
            safe_commits_query = urllib.parse.quote(keywords_query, safe='')
            
            path = f"/repos/{owner}/{repo}/commits?q={safe_commits_query}&per_page=5"
            body = http_get(GH_HOST, path, HEADERS_GH)
            if not body:
                return None
                
            commits = json.loads(body)
            desc_words = set(re.findall(r'\w+', cve_description.lower())[:10])
            
            for commit in commits:
                msg = commit.get("commit", {}).get("message", "").lower()
                sha = commit.get("sha")
                msg_words = set(re.findall(r'\w+', msg))
                overlap = len(desc_words & msg_words)
                
                if overlap >= 2 or any(kw in msg for kw in FIX_KEYWORDS):
                    diff_path = f"/repos/{owner}/{repo}/commits/{sha}"
                    diff_headers = {**HEADERS_GH, "Accept": "application/vnd.github.v3.diff"}
                    
                    conn = http.client.HTTPSConnection(GH_HOST, timeout=10)
                    conn.request("GET", diff_path, headers=diff_headers)
                    resp = conn.getresponse()
                    diff_content = resp.read().decode('utf-8', errors='replace')[:5000]
                    conn.close()
                    
                    if resp.status == 200:
                        added_lines = [l[1:] for l in diff_content.split('\n') if l.startswith('+') and not l.startswith('+++')]
                        removed_lines = [l[1:] for l in diff_content.split('\n') if l.startswith('-') and not l.startswith('---')]
                        
                        if added_lines and removed_lines:
                            return {
                                "commit_sha": sha,
                                "commit_url": commit.get("html_url"),
                                "commit_message": commit["commit"]["message"],
                                "vulnerable_snippet": "\n".join(removed_lines[:20]),
                                "fixed_snippet": "\n".join(added_lines[:20]),
                                "diff_preview": diff_content[:1000],
                                "repo": repo_full_name
                            }
        except Exception as e:
            print(f"    فشل استخراج commit من {repo_full_name}: {e}")
        return None

    def mine_cve(self, cve_id: str) -> Optional[Dict]:
        print(f"🔍 معالجة {cve_id}...")
        self.stats["cves_processed"] += 1
        
        cve_data = self.get_cve_details(cve_id)
        if not cve_data:
            return None
        
        repo_name = None
        for cpe in cve_data["cpes"]:
            repo_name = self.find_github_repo_from_cpe(cpe)
            if repo_name:
                break
        
        if not repo_name:
            print(f"   ⚠️ لم يُعثر على مستودع لـ {cve_id}")
            self.stats["repos_skipped"] += 1
            return None
        
        print(f"    مستودع محتمل: {repo_name}")
        
        fix_pair = self.extract_fix_commit(repo_name, cve_data["description"])
        if not fix_pair:
            print(f"   ⚠️ لم يُعثر على commit تصليحي في {repo_name}")
            return None
        
        result = {
            "cve_id": cve_id,
            "cve_description": cve_data["description"],
            "repo": repo_name,
            **fix_pair,
            "_source": "historical_truth_miner",
            "_mined_at": time.time(),
            "_hash": hashlib.sha256(json.dumps(fix_pair["commit_sha"] + repo_name).encode()).hexdigest()
        }
        
        self.stats["pairs_found"] += 1
        print(f"   ✅ تم استخراج زوج تصليح: {fix_pair['commit_sha'][:8]}")
        return result

    def run_batch(self, cve_list: List[str], output_file: str):
        print(f"⛏️ بدء التنقيب عن {len(cve_list)} CVE...")
        results = []
        
        for i, cve_id in enumerate(cve_list):
            result = self.mine_cve(cve_id)
            if result:
                results.append(result)
            
            delay = 1.0 if GITHUB_TOKEN else 60.0
            if i < len(cve_list) - 1:
                time.sleep(delay)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for r in results:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        
        print(f"\n📊 تقرير المنقّب:")
        print(f"   CVEs مُعالجة: {self.stats['cves_processed']}")
        print(f"   أزواج تصليح مستخرجة: {self.stats['pairs_found']}")
        print(f"   مستودعات لم تُطابق: {self.stats['repos_skipped']}")
        print(f"   الملف المخرَج: {output_file}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("الاستخدام: python historical_truth_miner.py cves.txt output.jsonl")
        sys.exit(1)
    
    cve_file = sys.argv[1]
    output_file = sys.argv[2]
    
    with open(cve_file, 'r') as f:
        cves = [line.strip() for line in f if line.strip().startswith("CVE-")]
    
    miner = HistoricalTruthMiner()
    miner.run_batch(cves, output_file)
