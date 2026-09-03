"""
وكيل الجمع (Collector) — فعلي، يعمل، لا تصميم نظري.

المصدر: GitHub REST API — منصة تسمح صراحة بهذا (Public API مخصص
للبحث والقراءة)، لا Claude ولا OpenAI ولا أي نموذج AI آخر كمصدر —
كل عينة هنا كود بشري حقيقي من مستودعات مفتوحة الترخيص.
"""

import os
import time
import requests

from filters import run_quality_gate, sha256_of, ALLOWED_LICENSES
from sandbox import run_code_in_sandbox
from critic import critic_review
from db import insert_sample, log_event, list_recent_samples

GITHUB_API = "https://api.github.com"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

GITHUB_LICENSE_MAP = {
    "mit": "MIT",
    "apache-2.0": "Apache-2.0",
    "bsd-2-clause": "BSD-2-Clause",
    "bsd-3-clause": "BSD-3-Clause",
    "cc0-1.0": "CC0-1.0",
}


def _headers():
    h = {"Accept": "application/vnd.github+json", "User-Agent": "MarsadCollector"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


def search_repos(language: str, license_key: str, max_results: int = 5) -> list[dict]:
    if license_key not in GITHUB_LICENSE_MAP:
        return []
    query = f"language:{language} license:{license_key}"
    resp = requests.get(
        f"{GITHUB_API}/search/repositories",
        params={"q": query, "sort": "stars", "order": "desc", "per_page": max_results},
        headers=_headers(),
        timeout=15,
    )
    if resp.status_code != 200:
        log_event("collector_errors", {"stage": "search_repos", "status": resp.status_code, "body": resp.text[:300]})
        return []
    return resp.json().get("items", [])


def list_code_files(owner: str, repo: str, extension: str, max_files: int = 3) -> list[dict]:
    repo_resp = requests.get(f"{GITHUB_API}/repos/{owner}/{repo}", headers=_headers(), timeout=15)
    if repo_resp.status_code != 200:
        log_event("collector_errors", {"stage": "get_repo", "repo": f"{owner}/{repo}", "status": repo_resp.status_code})
        return []
    default_branch = repo_resp.json().get("default_branch", "main")

    tree_resp = requests.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{default_branch}",
        params={"recursive": "1"}, headers=_headers(), timeout=15,
    )
    if tree_resp.status_code != 200:
        log_event("collector_errors", {"stage": "get_tree", "repo": f"{owner}/{repo}", "status": tree_resp.status_code})
        return []

    tree = tree_resp.json().get("tree", [])
    matched = [t for t in tree if t.get("type") == "blob" and t.get("path", "").endswith(extension)]
    files = []
    for t in matched[:max_files]:
        files.append({
            "name": t["path"],
            "download_url": f"https://raw.githubusercontent.com/{owner}/{repo}/{default_branch}/{t['path']}",
        })
    return files


def fetch_file_content(download_url: str) -> str | None:
    resp = requests.get(download_url, headers=_headers(), timeout=15)
    if resp.status_code != 200:
        return None
    return resp.text


def collect_batch(language: str = "python", license_key: str = "mit", max_repos: int = 3, max_files_per_repo: int = 2) -> dict:
    ext_map = {"python": ".py", "javascript": ".js", "go": ".go", "rust": ".rs"}
    extension = ext_map.get(language, ".py")

    report = {
        "repos_scanned": 0, "files_fetched": 0,
        "quality_rejected": 0, "sandbox_passed": 0, "sandbox_rejected": 0,
        "stored": 0, "duplicates_skipped": 0, "errors": 0,
    }

    repos = search_repos(language, license_key, max_repos)
    existing_texts = [s["content"] for s in list_recent_samples(300)]

    for repo in repos:
        report["repos_scanned"] += 1
        owner = repo["owner"]["login"]
        name = repo["name"]
        repo_license = (repo.get("license") or {}).get("key")
        internal_license = GITHUB_LICENSE_MAP.get(repo_license)

        if internal_license not in ["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "CC0-1.0"]:
            continue

        files = list_code_files(owner, name, extension, max_files_per_repo)

        for f in files:
            content = fetch_file_content(f.get("download_url", ""))
            if not content:
                report["errors"] += 1
                continue
            report["files_fetched"] += 1

            ok, reason = run_quality_gate(content, internal_license, existing_texts)
            if not ok:
                report["quality_rejected"] += 1
                log_event("collector_rejections", {"repo": f"{owner}/{name}", "file": f["name"], "reason": reason})
                continue

            sandbox_result = run_code_in_sandbox(content, language=language)
            if sandbox_result["status"] != "passed":
                report["sandbox_rejected"] += 1
                log_event("collector_rejections", {
                    "repo": f"{owner}/{name}", "file": f["name"],
                    "reason": sandbox_result["reject_reason"],
                })
                continue

            report["sandbox_passed"] += 1
            verdict = critic_review(content)
            final_status = "approved_for_training" if verdict["approved"] else "rejected"

            inserted = insert_sample(
                sha256_of(content), content,
                source_url=f"https://github.com/{owner}/{name}/blob/main/{f['name']}",
                license_=internal_license, language=language,
                provenance=({"repo": f"{owner}/{name}", "stars": repo.get("stargazers_count"),
                             "sandbox_run_id": sandbox_result["run_id"], "critic": verdict}),
                status=final_status,
                reject_reason=None if verdict["approved"] else verdict["reason"],
            )
            if inserted and verdict["approved"]:
                report["stored"] += 1
                existing_texts.append(content)
            elif inserted:
                report["quality_rejected"] += 1
            else:
                report["duplicates_skipped"] += 1

        time.sleep(1)

    log_event("collector_runs", report)
    return report
