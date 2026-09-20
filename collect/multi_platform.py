"""
الجمع متعدد المنصات — 8+ منصات حقيقية مع APIs حقيقية
"""
import os
import time
import requests
from bs4 import BeautifulSoup
from db import insert_sample, log_event, register_source, bump_source
from config import DATASET_PLATFORMS, REQUEST_TIMEOUT, ENABLE_VPN, ENABLE_PROXY

# Import key_manager and vpn_manager
try:
    from key_manager import key_collector_proxy, key_manager
except ImportError:
    key_collector_proxy = None
    key_manager = None

try:
    from vpn_config import vpn_manager
except ImportError:
    vpn_manager = None


class MultiPlatformCollector:
    """
    جمع البيانات من 8+ منصات حقيقية
    """

    PLATFORMS = [
        "github", "gitlab", "bitbucket", "huggingface_datasets",
        "stackoverflow", "exploitdb", "cve", "packetstorm",
        "shodan", "virus_total", "vulners", "threatfox",
        "alienvault_otx", "metasploit", "kaggle", "arxiv"
    ]

    def collect_all(self, query: str = "security vulnerability", limit: int = 100) -> dict:
        """
        جمع من جميع المنصات
        """
        results = {}

        # Register every platform as a data source
        for platform in self.PLATFORMS:
            try:
                register_source(
                    source_key=platform,
                    name=platform.replace("_", " ").title(),
                    platform=platform,
                    url=""
                )
            except Exception:
                pass

        # Connect VPN if enabled
        if ENABLE_VPN and vpn_manager:
            try:
                vpn_manager.connect_vpn()
            except Exception as e:
                log_event("vpn", {"action": "connect", "error": str(e)})

        for platform in self.PLATFORMS:
            try:
                # تحقق من وجود auth إذا لزم الأمر
                if platform in DATASET_PLATFORMS:
                    config = DATASET_PLATFORMS[platform]
                    if config.get("auth") and not self._check_auth(platform):
                        results[platform] = {
                            "status": "auth_required",
                            "message": f"يرجى تعين {config['auth']}"
                        }
                        continue
                
                collector = getattr(self, f"_collect_{platform}", self._collect_generic)
                results[platform] = collector(query, limit)
            except Exception as e:
                results[platform] = {"status": "error", "error": str(e)}

            time.sleep(0.5)  # تجنب rate limiting

            # Bump source count if succeeded
            try:
                r = results.get(platform, {})
                if r.get("status") == "success":
                    bump_source(platform, r.get("count", 0))
            except Exception:
                pass

        return results

    def _check_auth(self, platform_key: str) -> bool:
        """التحقق من توافر مفاتيح المصادقة"""
        config = DATASET_PLATFORMS.get(platform_key, {})
        auth = config.get("auth", {})
        if not auth:
            return True
        
        if isinstance(auth, dict):
            for key, env_var in auth.items():
                if not os.environ.get(env_var):
                    return False
        return True

    # --- GitHub ---
    def _collect_github(self, query: str, limit: int) -> dict:
        """جمع من GitHub API"""
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            return {"status": "auth_required", "message": "يرجى تعين GITHUB_TOKEN"}
        
        headers = {"Authorization": f"token {token}"}
        url = "https://api.github.com/search/code"
        
        try:
            response = requests.get(
                url,
                headers=headers,
                params={"q": query, "per_page": min(limit, 100)},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])[:limit]
                count = 0
                for item in items:
                    sha256 = insert_sample(
                        content=item.get("name", ""),
                        source=item.get("html_url", ""),
                        platform="github",
                        language="code"
                    )
                    if sha256:
                        count += 1
                return {"status": "success", "count": count}
            else:
                return {"status": "error", "code": response.status_code, "message": response.text[:200]}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # --- GitLab ---
    def _collect_gitlab(self, query: str, limit: int) -> dict:
        """جمع من GitLab API"""
        token = os.environ.get("GITLAB_TOKEN")
        if not token:
            return {"status": "auth_required", "message": "يرجى تعين GITLAB_TOKEN"}
        
        headers = {"PRIVATE-TOKEN": token}
        url = "https://gitlab.com/api/v4/projects"
        
        try:
            response = requests.get(
                url,
                headers=headers,
                params={"search": query, "per_page": min(limit, 100)},
                timeout=30
            )
            
            if response.status_code == 200:
                projects = response.json()[:limit]
                count = 0
                for project in projects:
                    sha256 = insert_sample(
                        content=project.get("name", ""),
                        source=project.get("web_url", ""),
                        platform="gitlab",
                        language="code"
                    )
                    if sha256:
                        count += 1
                return {"status": "success", "count": count}
            else:
                return {"status": "error", "code": response.status_code}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # --- Bitbucket ---
    def _collect_bitbucket(self, query: str, limit: int) -> dict:
        """جمع من Bitbucket API"""
        username = os.environ.get("BITBUCKET_USERNAME")
        app_password = os.environ.get("BITBUCKET_APP_PASSWORD")
        if not username or not app_password:
            return {"status": "auth_required", "message": "يرجى تعين BITBUCKET_USERNAME و BITBUCKET_APP_PASSWORD"}
        
        auth = (username, app_password)
        url = "https://api.bitbucket.org/2.0/repositories"
        
        try:
            response = requests.get(
                url,
                auth=auth,
                params={"q": f"name={query}", "pagelen": min(limit, 100)},
                timeout=30
            )
            
            if response.status_code == 200:
                repos = response.json().get("values", [])[:limit]
                count = 0
                for repo in repos:
                    sha256 = insert_sample(
                        content=repo.get("name", ""),
                        source=repo.get("links", {}).get("html", {}).get("href", ""),
                        platform="bitbucket",
                        language="code"
                    )
                    if sha256:
                        count += 1
                return {"status": "success", "count": count}
            else:
                return {"status": "error", "code": response.status_code}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # --- ExploitDB ---
    def _collect_exploitdb(self, query: str, limit: int) -> dict:
        """جمع من ExploitDB (GitHub raw CSV)"""
        try:
            url = "https://raw.githubusercontent.com/offensive-security/exploitdb/main/files_exploits.csv"
            response = requests.get(url, timeout=60)
            
            if response.status_code == 200:
                lines = response.text.strip().split("\n")[1:limit+1]
                count = 0
                for line in lines:
                    parts = line.split(",")
                    if len(parts) > 2:
                        exploit_id = parts[0]
                        description = parts[2] if len(parts) > 2 else ""
                        url = f"https://www.exploit-db.com/exploits/{exploit_id}"
                        
                        sha256 = insert_sample(
                            content=f"{exploit_id}: {description}",
                            source=url,
                            platform="exploitdb",
                            language="text"
                        )
                        if sha256:
                            count += 1
                return {"status": "success", "count": count}
            else:
                return {"status": "error", "code": response.status_code}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # --- CVE/NVD ---
    def _collect_cve(self, query: str, limit: int) -> dict:
        """جمع من CVE/NVD API"""
        api_key = os.environ.get("NVD_API_KEY")
        if not api_key:
            return {"status": "auth_required", "message": "يرجى تعين NVD_API_KEY"}
        
        headers = {"api-key": api_key}
        url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
        
        try:
            response = requests.get(
                url,
                headers=headers,
                params={"keywordSearch": query, "resultsPerPage": min(limit, 2000)},
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                vulnerabilities = data.get("vulnerabilities", [])
                count = 0
                for vuln in vulnerabilities[:limit]:
                    cve = vuln.get("cve", {})
                    cve_id = cve.get("id", "unknown")
                    desc = cve.get("descriptions", [{}])[0].get("value", "")
                    
                    sha256 = insert_sample(
                        content=f"{cve_id}: {desc}",
                        source=f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                        platform="cve",
                        language="text"
                    )
                    if sha256:
                        count += 1
                return {"status": "success", "count": count}
            else:
                return {"status": "error", "code": response.status_code}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # --- PacketStorm ---
    def _collect_packetstorm(self, query: str, limit: int) -> dict:
        """جمع من PacketStorm باستخدام scraping"""
        try:
            url = f"https://packetstormsecurity.com/files/tag/{query}/"
            response = requests.get(url, timeout=60)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                links = soup.select("dl.files a")[:limit]
                count = 0
                for link in links:
                    href = link.get("href", "")
                    if href:
                        full_url = f"https://packetstormsecurity.com{href}" if not href.startswith("http") else href
                        
                        sha256 = insert_sample(
                            content=link.text.strip(),
                            source=full_url,
                            platform="packetstorm",
                            language="text"
                        )
                        if sha256:
                            count += 1
                return {"status": "success", "count": count}
            else:
                return {"status": "error", "code": response.status_code}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # --- StackOverflow ---
    def _collect_stackoverflow(self, query: str, limit: int) -> dict:
        """جمع من StackOverflow API"""
        try:
            response = requests.get(
                "https://api.stackexchange.com/2.3/questions",
                params={
                    "order": "desc",
                    "sort": "votes",
                    "site": "stackoverflow",
                    "tagged": query,
                    "pagesize": min(limit, 100)
                },
                timeout=30
            )
            
            if response.status_code == 200:
                questions = response.json().get("items", [])
                count = 0
                for q in questions[:limit]:
                    sha256 = insert_sample(
                        content=q.get("title", ""),
                        source=q.get("link", ""),
                        platform="stackoverflow",
                        language="text"
                    )
                    if sha256:
                        count += 1
                return {"status": "success", "count": count}
            else:
                return {"status": "error", "code": response.status_code}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # --- HuggingFace Datasets ---
    def _collect_huggingface_datasets(self, query: str, limit: int) -> dict:
        """جمع من HuggingFace Datasets API"""
        token = os.environ.get("HF_TOKEN")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        
        try:
            response = requests.get(
                "https://huggingface.co/api/datasets",
                headers=headers,
                params={"search": query, "limit": min(limit, 100)},
                timeout=30
            )
            
            if response.status_code == 200:
                datasets = response.json()
                count = 0
                for ds in datasets[:limit]:
                    sha256 = insert_sample(
                        content=ds.get("description", ""),
                        source=f"https://huggingface.co/datasets/{ds.get('id')}",
                        platform="huggingface",
                        language="text"
                    )
                    if sha256:
                        count += 1
                return {"status": "success", "count": count}
            else:
                return {"status": "error", "code": response.status_code}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # --- Shodan ---
    def _collect_shodan(self, query: str, limit: int) -> dict:
        """جمع من Shodan API"""
        api_key = os.environ.get("SHODAN_API_KEY")
        if not api_key:
            return {"status": "auth_required", "message": "يرجى تعين SHODAN_API_KEY"}
        
        try:
            response = requests.get(
                f"https://api.shodan.io/shodan/host/search",
                params={"key": api_key, "query": query, "limit": min(limit, 100)},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                hosts = data.get("matches", [])
                count = 0
                for host in hosts[:limit]:
                    sha256 = insert_sample(
                        content=str(host),
                        source=f"https://www.shodan.io/host/{host.get('ip_str')}",
                        platform="shodan",
                        language="json"
                    )
                    if sha256:
                        count += 1
                return {"status": "success", "count": count}
            else:
                return {"status": "error", "code": response.status_code}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # --- VirusTotal ---
    def _collect_virus_total(self, query: str, limit: int) -> dict:
        """جمع من VirusTotal API"""
        api_key = os.environ.get("VIRUSTOTAL_API_KEY")
        if not api_key:
            return {"status": "auth_required", "message": "يرجى تعين VIRUSTOTAL_API_KEY"}
        
        try:
            response = requests.get(
                f"https://www.virustotal.com/api/v3/files/search",
                params={"apikey": api_key, "query": query, "limit": min(limit, 40)},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                files = data.get("data", [])
                count = 0
                for file_info in files[:limit]:
                    sha256 = insert_sample(
                        content=file_info.get("sha256", ""),
                        source=file_info.get("permalink", ""),
                        platform="virus_total",
                        language="text"
                    )
                    if sha256:
                        count += 1
                return {"status": "success", "count": count}
            else:
                return {"status": "error", "code": response.status_code}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # --- Vulners ---
    def _collect_vulners(self, query: str, limit: int) -> dict:
        """جمع من Vulners API"""
        api_key = os.environ.get("VULNERS_API_KEY")
        if not api_key:
            return {"status": "auth_required", "message": "يرجى تعين VULNERS_API_KEY"}
        
        try:
            response = requests.get(
                "https://vulners.com/api/v3/find",
                params={"apiKey": api_key, "query": query, "limit": min(limit, 100)},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                results = data.get("result", {}).get("RESULTS", [])
                count = 0
                for result in results[:limit]:
                    sha256 = insert_sample(
                        content=result.get("description", ""),
                        source=result.get("href", ""),
                        platform="vulners",
                        language="text"
                    )
                    if sha256:
                        count += 1
                return {"status": "success", "count": count}
            else:
                return {"status": "error", "code": response.status_code}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # --- ThreatFox ---
    def _collect_threatfox(self, query: str, limit: int) -> dict:
        """جمع من ThreatFox API"""
        try:
            response = requests.get(
                "https://threatfox-api.abuse.ch/api/v1/",
                params={"search": query, "limit": min(limit, 100)},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                results = data.get("data", [])
                count = 0
                for result in results[:limit]:
                    sha256 = insert_sample(
                        content=result.get("malware_printable", ""),
                        source=result.get("reference", ""),
                        platform="threatfox",
                        language="text"
                    )
                    if sha256:
                        count += 1
                return {"status": "success", "count": count}
            else:
                return {"status": "error", "code": response.status_code}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # --- AlienVault OTX ---
    def _collect_alienvault_otx(self, query: str, limit: int) -> dict:
        """جمع من AlienVault OTX API"""
        api_key = os.environ.get("OTX_API_KEY")
        if not api_key:
            return {"status": "auth_required", "message": "يرجى تعين OTX_API_KEY"}
        
        headers = {"X-OTX-API-KEY": api_key}
        try:
            response = requests.get(
                "https://otx.alienvault.com/api/v1/indicators/export",
                headers=headers,
                params={"limit": min(limit, 100)},
                timeout=30
            )
            
            if response.status_code == 200:
                indicators = response.json()
                count = 0
                for indicator in indicators[:limit]:
                    sha256 = insert_sample(
                        content=indicator.get("indicator", ""),
                        source=indicator.get("url", ""),
                        platform="alienvault_otx",
                        language="text"
                    )
                    if sha256:
                        count += 1
                return {"status": "success", "count": count}
            else:
                return {"status": "error", "code": response.status_code}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # --- Metasploit ---
    def _collect_metasploit(self, query: str, limit: int) -> dict:
        """جمع من Metasploit DB (GitHub)"""
        try:
            url = "https://raw.githubusercontent.com/rapid7/metasploit-framework/master/modules/exploits/"
            response = requests.get(url, timeout=60)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                links = soup.find_all('a')[:limit]
                count = 0
                for link in links:
                    href = link.get('href', '')
                    if href.endswith('.rb'):
                        sha256 = insert_sample(
                            content=href,
                            source=f"https://github.com/rapid7/metasploit-framework/blob/master/modules/exploits/{href}",
                            platform="metasploit",
                            language="ruby"
                        )
                        if sha256:
                            count += 1
                return {"status": "success", "count": count}
            else:
                return {"status": "error", "code": response.status_code}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # --- Kaggle ---
    def _collect_kaggle(self, query: str, limit: int) -> dict:
        """جمع من Kaggle API"""
        username = os.environ.get("KAGGLE_USERNAME")
        key = os.environ.get("KAGGLE_KEY")
        if not username or not key:
            return {"status": "auth_required", "message": "يرجى تعين KAGGLE_USERNAME و KAGGLE_KEY"}
        
        try:
            response = requests.get(
                "https://www.kaggle.com/api/v1/datasets/list",
                params={"search": query, "limit": min(limit, 100)},
                auth=(username, key),
                timeout=30
            )
            
            if response.status_code == 200:
                datasets = response.json().get("datasets", [])
                count = 0
                for ds in datasets[:limit]:
                    sha256 = insert_sample(
                        content=ds.get("title", ""),
                        source=ds.get("url", ""),
                        platform="kaggle",
                        language="text"
                    )
                    if sha256:
                        count += 1
                return {"status": "success", "count": count}
            else:
                return {"status": "error", "code": response.status_code}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # --- arXiv ---
    def _collect_arxiv(self, query: str, limit: int) -> dict:
        """جمع من arXiv API"""
        try:
            response = requests.get(
                "https://export.arxiv.org/api/query",
                params={
                    "search_query": f"all:{query}",
                    "start": 0,
                    "max_results": min(limit, 100)
                },
                timeout=30
            )
            
            if response.status_code == 200:
                # Parse arXiv XML response
                from xml.etree import ElementTree as ET
                root = ET.fromstring(response.text)
                entries = root.findall("{http://www.w3.org/2005/Atom}entry")
                count = 0
                for entry in entries[:limit]:
                    title = entry.find("{http://www.w3.org/2005/Atom}title")
                    summary = entry.find("{http://www.w3.org/2005/Atom}summary")
                    
                    sha256 = insert_sample(
                        content=f"{title.text if title is not None else ''}: {summary.text if summary is not None else ''}",
                        source=entry.find("{http://www.w3.org/2005/Atom}id").text if entry.find("{http://www.w3.org/2005/Atom}id") is not None else "",
                        platform="arxiv",
                        language="text"
                    )
                    if sha256:
                        count += 1
                return {"status": "success", "count": count}
            else:
                return {"status": "error", "code": response.status_code}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _collect_generic(self, query: str, limit: int) -> dict:
        """جمع عام"""
        return {"status": "not_implemented"}

    def store_sample(self, content: str, source: str, platform: str, language: str = "text"):
        """تخزين عينة"""
        return insert_sample(
            content=content,
            source=source,
            platform=platform,
            language=language,
            sample_type="collected"
        )


collector = MultiPlatformCollector()
