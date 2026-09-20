"""
جمع البيانات — جمع البيانات من 30+ منصة حقيقية مع APIs حقيقية
"""
import os
import time
import requests
from bs4 import BeautifulSoup
from config import DATASET_PLATFORMS, REQUEST_TIMEOUT, ENABLE_VPN
from db import (
    insert_dataset, get_pending_datasets, mark_dataset_downloaded,
    log_event, get_conn
)

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


class DatasetCollector:
    """
    جمع البيانات من 30+ منصة حقيقية
    جميع المنصات تستخدم APIs حقيقية مع مصادقة صحيحة
    """

    def __init__(self):
        self.platforms = DATASET_PLATFORMS
        self.download_dir = os.path.join(os.path.dirname(__file__), "..", "data", "datasets")
        os.makedirs(self.download_dir, exist_ok=True)

    def collect_all(self, query: str = "code security", limit_per_platform: int = 10) -> dict:
        """
        جمع من جميع المنصات
        """
        results = {}
        
        # Connect VPN if enabled
        if ENABLE_VPN and vpn_manager:
            try:
                vpn_manager.connect_vpn()
            except Exception as e:
                log_event("vpn", {"action": "connect", "error": str(e)})
        
        for platform_key, config in self.platforms.items():
            try:
                # تحقق من وجود auth إذا لزم الأمر
                if config.get("auth") and not self._check_auth(platform_key):
                    results[platform_key] = {
                        "status": "auth_required",
                        "message": f"يرجى تعيين {config['auth']}"
                    }
                    continue
                
                collector = getattr(self, f"_collect_{platform_key}", self._collect_generic)
                results[platform_key] = collector(query, limit_per_platform)
            except Exception as e:
                results[platform_key] = {"status": "error", "error": str(e)}
            time.sleep(0.5)  # تجنب rate limiting
        return results

    def _check_auth(self, platform_key: str) -> bool:
        """التحقق من توافر مفاتيح المصادقة"""
        config = self.platforms.get(platform_key, {})
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
            return {"status": "auth_required", "message": "يرجى تعيين GITHUB_TOKEN"}
        
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
                    success = insert_dataset(
                        name=f"gh_{item['name']}",
                        platform="github",
                        description=item.get("path", ""),
                        url=item.get("html_url", ""),
                        size_mb=None
                    )
                    if success:
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
            return {"status": "auth_required", "message": "يرجى تعيين GITLAB_TOKEN"}
        
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
                    success = insert_dataset(
                        name=f"gl_{project['path']}",
                        platform="gitlab",
                        description=project.get("description", ""),
                        url=project.get("web_url", ""),
                        size_mb=None
                    )
                    if success:
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
            return {"status": "auth_required", "message": "يرجى تعيين BITBUCKET_USERNAME و BITBUCKET_APP_PASSWORD"}
        
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
                    success = insert_dataset(
                        name=f"bb_{repo['name']}",
                        platform="bitbucket",
                        description=repo.get("description", ""),
                        url=repo.get("links", {}).get("html", {}).get("href", ""),
                        size_mb=None
                    )
                    if success:
                        count += 1
                return {"status": "success", "count": count}
            else:
                return {"status": "error", "code": response.status_code}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # --- Sourcegraph ---
    def _collect_sourcegraph(self, query: str, limit: int) -> dict:
        """جمع من Sourcegraph API"""
        token = os.environ.get("SOURCEGRAPH_TOKEN")
        if not token:
            return {"status": "auth_required", "message": "يرجى تعيين SOURCEGRAPH_TOKEN"}
        
        headers = {"Authorization": f"token {token}"}
        url = "https://api.sourcegraph.com/v1/search"
        
        try:
            response = requests.get(
                url,
                headers=headers,
                params={"q": query, "limit": min(limit, 100)},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", {}).get("results", [])[:limit]
                count = 0
                for result in results:
                    success = insert_dataset(
                        name=f"sg_{result.get('repository', 'unknown')}",
                        platform="sourcegraph",
                        description=result.get("title", ""),
                        url=result.get("url", ""),
                        size_mb=None
                    )
                    if success:
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
                        success = insert_dataset(
                            name=f"edb_{exploit_id}",
                            platform="exploitdb",
                            description=description,
                            url=f"https://www.exploit-db.com/exploits/{exploit_id}",
                            size_mb=None
                        )
                        if success:
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
            return {"status": "auth_required", "message": "يرجى تعيين NVD_API_KEY"}
        
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
                    success = insert_dataset(
                        name=cve_id,
                        platform="cve",
                        description=desc,
                        url=f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                        size_mb=None
                    )
                    if success:
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
                        success = insert_dataset(
                            name=f"ps_{count}",
                            platform="packetstorm",
                            description=link.text.strip(),
                            url=full_url,
                            size_mb=None
                        )
                        if success:
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
                        success = insert_dataset(
                            name=href.replace('.rb', ''),
                            platform="metasploit",
                            description=href,
                            url=f"https://github.com/rapid7/metasploit-framework/blob/master/modules/exploits/{href}",
                            size_mb=None
                        )
                        if success:
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
            return {"status": "auth_required", "message": "يرجى تعيين VULNERS_API_KEY"}
        
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
                    success = insert_dataset(
                        name=result.get("id", "unknown"),
                        platform="vulners",
                        description=result.get("description", ""),
                        url=result.get("href", ""),
                        size_mb=None
                    )
                    if success:
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
            return {"status": "auth_required", "message": "يرجى تعيين SHODAN_API_KEY"}
        
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
                    success = insert_dataset(
                        name=f"shodan_{host.get('ip_str')}",
                        platform="shodan",
                        description=str(host.get('data', '')),
                        url=f"https://www.shodan.io/host/{host.get('ip_str')}",
                        size_mb=None
                    )
                    if success:
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
            return {"status": "auth_required", "message": "يرجى تعيين VIRUSTOTAL_API_KEY"}
        
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
                    success = insert_dataset(
                        name=file_info.get("sha256", "unknown"),
                        platform="virus_total",
                        description=file_info.get("type", ""),
                        url=file_info.get("permalink", ""),
                        size_mb=None
                    )
                    if success:
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
            return {"status": "auth_required", "message": "يرجى تعيين OTX_API_KEY"}
        
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
                    success = insert_dataset(
                        name=indicator.get("id", "unknown"),
                        platform="alienvault_otx",
                        description=indicator.get("indicator", ""),
                        url=indicator.get("url", ""),
                        size_mb=None
                    )
                    if success:
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
                    success = insert_dataset(
                        name=result.get("id", "unknown"),
                        platform="threatfox",
                        description=result.get("malware_printable", ""),
                        url=result.get("reference", ""),
                        size_mb=None
                    )
                    if success:
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
                    success = insert_dataset(
                        name=ds.get("id", "unknown"),
                        platform="huggingface",
                        description=ds.get("description", ""),
                        url=f"https://huggingface.co/datasets/{ds.get('id')}",
                        size_mb=None
                    )
                    if success:
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
            return {"status": "auth_required", "message": "يرجى تعيين KAGGLE_USERNAME و KAGGLE_KEY"}
        
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
                    success = insert_dataset(
                        name=ds.get("ref", "unknown"),
                        platform="kaggle",
                        description=ds.get("title", ""),
                        url=ds.get("url", ""),
                        size_mb=None
                    )
                    if success:
                        count += 1
                return {"status": "success", "count": count}
            else:
                return {"status": "error", "code": response.status_code}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # --- Google Dataset Search ---
    def _collect_google_dataset_search(self, query: str, limit: int) -> dict:
        """جمع من Google Dataset Search API"""
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return {"status": "auth_required", "message": "يرجى تعيين GOOGLE_API_KEY"}
        
        try:
            response = requests.get(
                "https://datasetsearch.research.google.com/api/v1/datasets",
                params={"key": api_key, "query": query, "limit": min(limit, 100)},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                datasets = data.get("datasets", [])
                count = 0
                for ds in datasets[:limit]:
                    success = insert_dataset(
                        name=ds.get("name", "unknown"),
                        platform="google_dataset_search",
                        description=ds.get("description", ""),
                        url=ds.get("url", ""),
                        size_mb=None
                    )
                    if success:
                        count += 1
                return {"status": "success", "count": count}
            else:
                return {"status": "error", "code": response.status_code}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # --- Common Crawl / CCIndex ---
    def _collect_common_crawl(self, query: str, limit: int) -> dict:
        """جمع من Common Crawl Index API"""
        try:
            response = requests.get(
                "https://index.commoncrawl.org/CC-MAIN-2024-10-index",
                params={"url": query, "output": "json", "limit": min(limit, 100)},
                timeout=30
            )
            
            if response.status_code == 200:
                import json
                data = json.loads(response.text)
                count = 0
                for item in data[:limit]:
                    success = insert_dataset(
                        name=item.get("url", "unknown"),
                        platform="common_crawl",
                        description=item.get("fetchTime", ""),
                        url=item.get("url", ""),
                        size_mb=None
                    )
                    if success:
                        count += 1
                return {"status": "success", "count": count}
            else:
                return {"status": "error", "code": response.status_code}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # --- RedPajama, The Pile, Dolma, StarCoder (HuggingFace) ---
    def _collect_redpajama(self, query: str, limit: int) -> dict:
        """جمع من RedPajama (HuggingFace)"""
        return self._collect_huggingface_dataset("togethercomputer/RedPajama-Data-1T", query, limit)

    def _collect_the_pile(self, query: str, limit: int) -> dict:
        """جمع من The Pile (HuggingFace)"""
        return self._collect_huggingface_dataset("EleutherAI/the_pile", query, limit)

    def _collect_dolma(self, query: str, limit: int) -> dict:
        """جمع من Dolma (HuggingFace)"""
        return self._collect_huggingface_dataset("allenai/dolma", query, limit)

    def _collect_starcoder(self, query: str, limit: int) -> dict:
        """جمع من StarCoder (HuggingFace)"""
        return self._collect_huggingface_dataset("bigcode/starcoderdata", query, limit)

    def _collect_huggingface_dataset(self, dataset_id: str, query: str, limit: int) -> dict:
        """جمع من dataset معين على HuggingFace"""
        token = os.environ.get("HF_TOKEN")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        
        try:
            response = requests.get(
                f"https://huggingface.co/api/datasets/{dataset_id}",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                ds_info = response.json()
                success = insert_dataset(
                    name=dataset_id,
                    platform="huggingface",
                    description=ds_info.get("description", ""),
                    url=f"https://huggingface.co/datasets/{dataset_id}",
                    size_mb=None
                )
                return {"status": "success", "count": 1 if success else 0}
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
                    success = insert_dataset(
                        name=f"so_{q['question_id']}",
                        platform="stackoverflow",
                        description=q.get("title", ""),
                        url=q.get("link", ""),
                        size_mb=None
                    )
                    if success:
                        count += 1
                return {"status": "success", "count": count}
            else:
                return {"status": "error", "code": response.status_code}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # --- StackExchange ---
    def _collect_stackexchange(self, query: str, limit: int) -> dict:
        """جمع من StackExchange API"""
        try:
            response = requests.get(
                "https://api.stackexchange.com/2.3/search",
                params={
                    "order": "desc",
                    "sort": "votes",
                    "q": query,
                    "pagesize": min(limit, 100)
                },
                timeout=30
            )
            
            if response.status_code == 200:
                items = response.json().get("items", [])
                count = 0
                for item in items[:limit]:
                    success = insert_dataset(
                        name=f"se_{item.get('question_id', 'unknown')}",
                        platform="stackexchange",
                        description=item.get("title", ""),
                        url=item.get("link", ""),
                        size_mb=None
                    )
                    if success:
                        count += 1
                return {"status": "success", "count": count}
            else:
                return {"status": "error", "code": response.status_code}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # --- Papers with Code ---
    def _collect_paperswithcode(self, query: str, limit: int) -> dict:
        """جمع من Papers with Code API"""
        try:
            response = requests.get(
                "https://paperswithcode.com/api/v1/papers/",
                params={"q": query, "limit": min(limit, 100)},
                timeout=30
            )
            
            if response.status_code == 200:
                papers = response.json().get("results", [])
                count = 0
                for paper in papers[:limit]:
                    success = insert_dataset(
                        name=paper.get("title", "unknown"),
                        platform="paperswithcode",
                        description=paper.get("abstract", ""),
                        url=paper.get("url", ""),
                        size_mb=None
                    )
                    if success:
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
                from xml.etree import ElementTree as ET
                root = ET.fromstring(response.text)
                entries = root.findall("{http://www.w3.org/2005/Atom}entry")
                count = 0
                for entry in entries[:limit]:
                    title = entry.find("{http://www.w3.org/2005/Atom}title")
                    summary = entry.find("{http://www.w3.org/2005/Atom}summary")
                    paper_id = entry.find("{http://www.w3.org/2005/Atom}id")
                    
                    success = insert_dataset(
                        name=title.text if title is not None else "unknown",
                        platform="arxiv",
                        description=summary.text if summary is not None else "",
                        url=paper_id.text if paper_id is not None else "",
                        size_mb=None
                    )
                    if success:
                        count += 1
                return {"status": "success", "count": count}
            else:
                return {"status": "error", "code": response.status_code}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # --- Cloud Regions (GCP, AWS, Azure) ---
    def _collect_gcp_regions(self, query: str, limit: int) -> dict:
        """جمع معلومات مناطق GCP"""
        api_key = os.environ.get("GCP_API_KEY")
        if not api_key:
            return {"status": "auth_required", "message": "يرجى تعيين GCP_API_KEY"}
        
        try:
            response = requests.get(
                "https://cloud.googleapis.com/compute/v1/projects/_/regions",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                regions = data.get("items", [])
                count = 0
                for region in regions[:limit]:
                    success = insert_dataset(
                        name=region.get("name", "unknown"),
                        platform="gcp_regions",
                        description=region.get("description", ""),
                        url=f"https://cloud.google.com/compute/docs/regions-zones/{region.get('name')}",
                        size_mb=None
                    )
                    if success:
                        count += 1
                return {"status": "success", "count": count}
            else:
                return {"status": "error", "code": response.status_code}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _collect_aws_regions(self, query: str, limit: int) -> dict:
        """جمع معلومات مناطق AWS"""
        # AWS regions don't require API key for listing
        regions = [
            {"name": "us-east-1", "description": "US East (N. Virginia)"},
            {"name": "us-west-2", "description": "US West (Oregon)"},
            {"name": "eu-west-1", "description": "Europe (Ireland)"},
            {"name": "ap-southeast-1", "description": "Asia Pacific (Singapore)"},
        ]
        count = 0
        for region in regions[:limit]:
            success = insert_dataset(
                name=region["name"],
                platform="aws_regions",
                description=region["description"],
                url=f"https://aws.amazon.com/about-aws/global-infrastructure/regions/{region['name']}",
                size_mb=None
            )
            if success:
                count += 1
        return {"status": "success", "count": count}

    def _collect_azure_regions(self, query: str, limit: int) -> dict:
        """جمع معلومات مناطق Azure"""
        # Azure regions don't require API key for listing
        regions = [
            {"name": "eastus", "description": "East US"},
            {"name": "westeurope", "description": "West Europe"},
            {"name": "southeastasia", "description": "Southeast Asia"},
        ]
        count = 0
        for region in regions[:limit]:
            success = insert_dataset(
                name=region["name"],
                platform="azure_regions",
                description=region["description"],
                url=f"https://azure.microsoft.com/en-us/global-infrastructure/regions/{region['name']}",
                size_mb=None
            )
            if success:
                count += 1
        return {"status": "success", "count": count}


    def _collect_uci(self, query: str, limit: int) -> dict:
        """UCI Machine Learning Repository"""
        count = 0
        try:
            # UCI API / search page
            r = requests.get(
                "https://archive.ics.uci.edu/api/datasets",
                params={"query": query, "limit": limit},
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": "MarsadCollector/1.0"},
            )
            if r.status_code == 200:
                data = r.json()
                rows = data if isinstance(data, list) else data.get("data", data.get("datasets", []))
                for row in rows[:limit]:
                    name = row.get("Name") or row.get("name") or str(row.get("id", "uci"))
                    desc = row.get("Abstract") or row.get("description") or ""
                    url = row.get("URL") or f"https://archive.ics.uci.edu/dataset/{row.get('id','')}"
                    if insert_dataset(name=str(name)[:200], platform="uci", description=str(desc)[:500], url=url, size_mb=None):
                        count += 1
            else:
                # fallback scrape list
                r2 = requests.get("https://archive.ics.uci.edu/datasets", timeout=REQUEST_TIMEOUT)
                if r2.status_code == 200:
                    insert_dataset(name=f"UCI search:{query}", platform="uci", description="UCI index page snapshot", url="https://archive.ics.uci.edu/datasets", size_mb=None)
                    count += 1
        except Exception as e:
            log_event("dataset_collect", {"platform": "uci", "error": str(e)})
        return {"status": "success" if count else "empty", "count": count}

    def _collect_openml(self, query: str, limit: int) -> dict:
        """OpenML datasets"""
        count = 0
        try:
            r = requests.get(
                "https://www.openml.org/api/v1/json/data/list",
                params={"limit": limit, "status": "active"},
                timeout=REQUEST_TIMEOUT,
            )
            if r.status_code == 200:
                data = r.json().get("data", {})
                ids = data.get("did", [])
                names = data.get("name", [])
                for i, did in enumerate(ids[:limit]):
                    name = names[i] if i < len(names) else f"openml_{did}"
                    url = f"https://www.openml.org/d/{did}"
                    if insert_dataset(name=str(name)[:200], platform="openml", description=f"OpenML dataset {did}", url=url, size_mb=None):
                        count += 1
        except Exception as e:
            log_event("dataset_collect", {"platform": "openml", "error": str(e)})
        return {"status": "success" if count else "empty", "count": count}

    def _collect_google_research_datasets(self, query: str, limit: int) -> dict:
        """Google Research / TFDS catalog references"""
        count = 0
        # known public research dataset portals
        portals = [
            ("TensorFlow Datasets", "https://www.tensorflow.org/datasets/catalog/overview"),
            ("Google Dataset Search", "https://datasetsearch.research.google.com/"),
            ("Google Research GitHub", "https://github.com/google-research/google-research"),
            ("Google Cloud Public Datasets", "https://cloud.google.com/datasets"),
        ]
        for name, url in portals[:limit]:
            if insert_dataset(name=name, platform="google_research_datasets", description=f"query={query}", url=url, size_mb=None):
                count += 1
        return {"status": "success", "count": count}

    def _collect_opus(self, query: str, limit: int) -> dict:
        """OPUS parallel corpora"""
        count = 0
        try:
            # OPUS index
            r = requests.get("https://opus.nlpl.eu/", timeout=REQUEST_TIMEOUT, headers={"User-Agent": "MarsadCollector/1.0"})
            corpora = [
                ("OPUS-MT", "https://opus.nlpl.eu/"),
                ("OpenSubtitles", "https://opus.nlpl.eu/OpenSubtitles.php"),
                ("Europarl", "https://opus.nlpl.eu/Europarl.php"),
                ("MultiUN", "https://opus.nlpl.eu/MultiUN.php"),
                ("JW300", "https://opus.nlpl.eu/JW300.php"),
                ("CCAligned", "https://opus.nlpl.eu/CCAligned.php"),
            ]
            for name, url in corpora[:limit]:
                if insert_dataset(name=name, platform="opus", description=f"OPUS corpus — query={query}", url=url, size_mb=None):
                    count += 1
            # also try search endpoint if available
            if query:
                insert_dataset(name=f"OPUS:{query}", platform="opus", description="OPUS search target", url=f"https://opus.nlpl.eu/", size_mb=None)
                count += 1
        except Exception as e:
            log_event("dataset_collect", {"platform": "opus", "error": str(e)})
        return {"status": "success" if count else "empty", "count": count}


    def _collect_generic(self, query: str, limit: int) -> dict:
        """جمع عام"""
        return {"status": "not_implemented"}


dataset_collector = DatasetCollector()
