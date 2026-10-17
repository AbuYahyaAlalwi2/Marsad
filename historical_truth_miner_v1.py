#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
historical_truth_miner_v1.py — منقّب الحقيقة التاريخية (مرصد)

يعمل تلقائياً بالكامل ويُستأنف من حيث توقف:
  OSV (سجلات ثغرات حقيقية فيها commit الإصلاح)  ->  GitHub (diff الإصلاح)
  ->  أزواج (كود ضعيف قبل الإصلاح، كود مُرقَّع بعده، تفسير سببي من نصوص المصدر نفسها)

لا يولّد أي exploit ولا يستخدم أي نموذج. كل عيّنة لها ترقيع حقيقي ومصدر قابل للتتبع.
الاعتماديات: مكتبة بايثون القياسية فقط.

التشغيل التلقائي (يُنصح بتعيين GITHUB_TOKEN اختيارياً لرفع حد الطلبات):
    python3 historical_truth_miner_v1.py --auto --out ~/Marsad/data/truth

المخرجات:
    <out>/samples_<runid>_<n>.jsonl.gz   (ملفات جديدة بأسماء فريدة، لا استبدال ولا محو)
    <out>/state.sqlite                   (حالة الاستئناف + أرشيف أسباب الرفض)
    <out>/STATUS.json                    (نبض حيّ لأي مُنسّق يراقب)
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import signal
import sqlite3
import sys
import time
import urllib.error
import urllib.request
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator, Optional

# ───────────────────────── ثوابت ─────────────────────────

OSV_ZIP_URL = "https://osv-vulnerabilities.storage.googleapis.com/{eco}/all.zip"

# ترتيب الأولوية: C/C++ ثم PHP ثم JS ثم Java ثم Python ثم Go
DEFAULT_ECOSYSTEMS = ["OSS-Fuzz", "Packagist", "npm", "Maven", "PyPI", "Go"]

ALLOWED_LICENSES = {
    "mit", "apache-2.0", "bsd-2-clause", "bsd-3-clause", "isc",
    "unlicense", "cc0-1.0", "zlib", "bsl-1.0", "0bsd", "mpl-2.0",
}

LANG_BY_EXT = {
    ".c": "c", ".h": "c",
    ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".hh": "cpp",
    ".php": "php",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".jsx": "javascript", ".ts": "typescript", ".tsx": "typescript",
    ".java": "java", ".py": "python", ".go": "go", ".rs": "rust",
    ".rb": "ruby", ".cs": "csharp",
}

COMMENT_PREFIX = {
    "python": ("#",), "ruby": ("#",), "php": ("//", "#", "/*", "*"),
}
DEFAULT_COMMENT_PREFIX = ("//", "/*", "*")

SKIP_PATH_RE = re.compile(
    r"(^|/)(tests?|spec|__tests__|testing|testdata|fuzz(er|ers)?|examples?|docs?|"
    r"vendor|third_party|node_modules|dist|build)(/|$)"
    r"|\.min\.js$|(_test\.(go|c|cc|cpp|py)$)|(^|/)test_[^/]*$|\.test\.(js|ts)$",
    re.I,
)

SECRET_RES = [
    re.compile(p) for p in (
        r"hf_[A-Za-z0-9]{20,}", r"ghp_[A-Za-z0-9]{20,}", r"github_pat_[A-Za-z0-9_]{20,}",
        r"AKIA[0-9A-Z]{16}", r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
        r"sk-[A-Za-z0-9]{20,}", r"xox[baprs]-[A-Za-z0-9-]{10,}",
    )
]

CWE_KEYWORDS = [
    (r"heap[- ]buffer[- ]overflow", "CWE-122"),
    (r"stack[- ]buffer[- ]overflow", "CWE-121"),
    (r"global[- ]buffer[- ]overflow", "CWE-787"),
    (r"buffer[- ]overflow", "CWE-120"),
    (r"use[- ]after[- ]free", "CWE-416"),
    (r"double[- ]free", "CWE-415"),
    (r"null[- ](pointer|dereference)|nullptr", "CWE-476"),
    (r"uninitialized|use-of-uninitialized", "CWE-457"),
    (r"integer[- ]overflow|signed-integer-overflow", "CWE-190"),
    (r"out[- ]of[- ]bounds write|oob write|write out of bounds", "CWE-787"),
    (r"out[- ]of[- ]bounds read|oob read|read out of bounds", "CWE-125"),
    (r"path traversal|directory traversal", "CWE-22"),
    (r"sql injection", "CWE-89"),
    (r"cross-site scripting|\bxss\b", "CWE-79"),
    (r"bad[- ]cast|type confusion", "CWE-843"),
    (r"deserializ", "CWE-502"),
]


class NotFound(Exception):
    pass


class FetchFailed(Exception):
    pass


class RateLimited(FetchFailed):
    """حصة GitHub نفدت؛ reset_at وقت (epoch) إعادة ضبطها."""

    def __init__(self, url: str, reset_at: float):
        super().__init__(f"{url} -> rate limit (يُعاد ضبطها بعد ~{max(0, int(reset_at - time.time()))}ث)")
        self.reset_at = reset_at


# ───────────────────────── الشبكة ─────────────────────────

class Http:
    """HTTP قياسي مع إعادة محاولة ذكية. التوكن يُرسَل فقط إلى api.github.com ولا يُسجَّل أبداً."""

    def __init__(self, token: Optional[str] = None, max_retries: int = 5,
                 sleep: Callable[[float], None] = time.sleep, opener=None,
                 now: Callable[[], float] = time.time):
        self.token = token
        self.max_retries = max_retries
        self.sleep = sleep
        self.now = now
        self.limited_until = 0.0
        self.opener = opener or urllib.request.urlopen

    def _open(self, url: str, accept: Optional[str]):
        headers = {"User-Agent": "marsad-truth-miner/1"}
        if accept:
            headers["Accept"] = accept
        if self.token and url.startswith("https://api.github.com/"):
            headers["Authorization"] = f"Bearer {self.token}"
        is_api = url.startswith("https://api.github.com/")
        if is_api and self.now() < self.limited_until:   # لا نطرق الباب أثناء الحظر
            raise RateLimited(url, self.limited_until)
        last = None
        for attempt in range(self.max_retries):
            try:
                return self.opener(urllib.request.Request(url, headers=headers), timeout=60)
            except urllib.error.HTTPError as e:
                if e.code in (404, 410, 451):
                    raise NotFound(url)
                if e.code in (403, 429) and e.headers and e.headers.get("X-RateLimit-Remaining") == "0":
                    try:
                        reset = float(e.headers.get("X-RateLimit-Reset")) + 5
                    except (TypeError, ValueError):
                        reset = self.now() + 3600
                    if is_api:
                        self.limited_until = reset
                    raise RateLimited(url, reset)
                if e.code in (403, 429) or e.code >= 500:
                    ra = e.headers.get("Retry-After") if e.headers else None
                    wait = float(ra) if ra and ra.isdigit() else min(5 * (2 ** attempt), 300)
                    last = e
                    self.sleep(min(wait, 900))
                    continue
                raise FetchFailed(f"{url} -> HTTP {e.code}")
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                last = e
                self.sleep(min(5 * (2 ** attempt), 120))
        raise FetchFailed(f"{url} -> {last!r}")

    def get_bytes(self, url: str, accept: Optional[str] = None, max_bytes: int = 5_000_000) -> bytes:
        with self._open(url, accept) as r:
            data = r.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise NotFound(f"{url} (too large)")
        return data

    def get_text(self, url: str, accept: Optional[str] = None) -> str:
        return self.get_bytes(url, accept).decode("utf-8", errors="replace")

    def download(self, url: str, dest: Path) -> None:
        tmp = dest.with_suffix(dest.suffix + ".part")
        with self._open(url, None) as r, open(tmp, "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
        os.replace(tmp, dest)


# ───────────────────────── تحليل OSV ─────────────────────────

_SHA = re.compile(r"[0-9a-f]{7,40}")
GH_COMMIT_URL = re.compile(
    r"https?://github\.com/([^/\s]+)/([^/\s]+?)(?:\.git)?/commit/([0-9a-f]{7,40})", re.I)
GH_REPO_URL = re.compile(r"https?://github\.com/([^/\s]+)/([^/\s#?]+?)(?:\.git)?/?$", re.I)


def extract_fix_commits(rec: dict) -> list[tuple[str, str, str]]:
    """commits الإصلاح الموثّقة فقط: أحداث fixed في نطاقات GIT، أو مراجع من نوع FIX."""
    out: list[tuple[str, str, str]] = []
    for aff in rec.get("affected") or []:
        for rng in aff.get("ranges") or []:
            if rng.get("type") != "GIT":
                continue
            m = GH_REPO_URL.match((rng.get("repo") or "").strip())
            if not m:
                continue
            for ev in rng.get("events") or []:
                sha = ev.get("fixed")
                if sha and _SHA.fullmatch(sha):
                    out.append((m.group(1), m.group(2), sha))
    for ref in rec.get("references") or []:
        if ref.get("type") == "FIX":
            m = GH_COMMIT_URL.search(ref.get("url") or "")
            if m:
                out.append((m.group(1), m.group(2), m.group(3).lower()))
    seen, uniq = set(), []
    for o, r, s in out:
        k = (o.lower(), r.lower(), s[:7])
        if k not in seen:
            seen.add(k)
            uniq.append((o, r, s))
    return uniq


def fix_diagnosis(rec: dict) -> str:
    ranges = [r for a in rec.get("affected") or [] for r in a.get("ranges") or [] if r.get("type") == "GIT"]
    if not ranges:
        return "no_fix_commit"
    if any(ev.get("fixed") for r in ranges for ev in r.get("events") or []):
        return "no_fix_commit_non_github"       # يوجد fixed لكن المستودع ليس على GitHub
    return "no_fix_commit_no_fixed_event"


LICENSE_FILES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "LICENCE", "LICENSE-MIT")


def detect_license_from_text(text: str) -> Optional[str]:
    """كشف متحفّظ: أي أثر لترخيص copyleft يعني رفضاً؛ المسموح لا يُقبل إلا ببصمة نصية صريحة."""
    t = re.sub(r"\s+", " ", text[:30000]).lower()
    t = t.replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    if "affero general public license" in t:
        return "agpl"
    if "gnu lesser general public license" in t:
        return "lgpl"
    if "gnu general public license" in t:
        return "gpl"
    if "apache license" in t and "version 2.0" in t:
        return "apache-2.0"
    if "mozilla public license" in t:
        return "mpl-2.0" if "2.0" in t else "mpl"
    if "free and unencumbered software released into the public domain" in t:
        return "unlicense"
    if "permission is hereby granted, free of charge, to any person obtaining a copy" in t:
        return "mit"
    if "redistribution and use in source and binary forms" in t:
        if "advertising materials" in t:
            return "bsd-4-clause"
        return "bsd-3-clause" if ("neither the name" in t or "endorse or promote" in t) else "bsd-2-clause"
    if "permission to use, copy, modify, and" in t and "this software for any purpose with or without fee" in t:
        return "isc"
    if "altered source versions must be plainly marked" in t:
        return "zlib"
    return None


def extract_cwes(rec: dict) -> tuple[list[str], str]:
    ds = rec.get("database_specific")
    stated = list(ds.get("cwe_ids") or []) if isinstance(ds, dict) else []
    text = f"{rec.get('summary', '')}\n{rec.get('details', '')}"
    stated += [c.upper() for c in re.findall(r"CWE-\d+", text, re.I)]
    if stated:
        return sorted(set(stated)), "stated"
    # القائمة مرتبة من الأدق إلى الأعم؛ أول تطابق يفوز، والعنوان أصدق من النص الطويل
    for label, source in (("inferred_from_summary", rec.get("summary", "")),
                          ("inferred_from_details", rec.get("details", ""))):
        for pat, cwe in CWE_KEYWORDS:
            if re.search(pat, source, re.I):
                return [cwe], label
    return [], "none"


# ───────────────────────── تحليل الـ patch ─────────────────────────

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@ ?(.*)$")


@dataclass
class Hunk:
    path: str
    context: str
    before: list
    after: list
    removed: list
    added: list


def _commit_message(head: str) -> str:
    lines = head.split("\n")
    for idx, l in enumerate(lines):
        if l.startswith("Subject:"):
            subj = l[len("Subject:"):].strip()
            j = idx + 1
            while j < len(lines) and lines[j].startswith((" ", "\t")):
                subj += " " + lines[j].strip()
                j += 1
            subj = re.sub(r"^\[PATCH[^\]]*\]\s*", "", subj)
            body = []
            for bl in lines[j:]:
                if bl.strip() == "---":
                    break
                body.append(bl)
            return (subj + "\n" + "\n".join(body)).strip()
    return ""


def parse_patch(text: str) -> tuple[str, list[Hunk]]:
    head, sep, rest = text.partition("\ndiff --git ")
    message = _commit_message(head)
    if not sep:
        return message, []
    lines = ("diff --git " + rest).split("\n")
    hunks: list[Hunk] = []
    path, i = None, 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("diff --git "):
            m = re.match(r"diff --git a/(.+?) b/(.+)$", ln)
            path = m.group(2) if m else None
            i += 1
            continue
        m = HUNK_RE.match(ln)
        if m and path:
            old_n = 1 if m.group(2) is None else int(m.group(2))
            new_n = 1 if m.group(4) is None else int(m.group(4))
            ctx = m.group(5).strip()
            i += 1
            before, after, rem, add = [], [], [], []
            while i < len(lines) and (old_n > 0 or new_n > 0):
                l = lines[i]
                if l.startswith("\\"):
                    i += 1
                    continue
                tag, content = l[:1], l[1:]
                if tag == " " or l == "":
                    before.append(content)
                    after.append(content)
                    old_n -= 1
                    new_n -= 1
                elif tag == "-":
                    before.append(content)
                    rem.append(content)
                    old_n -= 1
                elif tag == "+":
                    after.append(content)
                    add.append(content)
                    new_n -= 1
                else:
                    break
                i += 1
            hunks.append(Hunk(path, ctx, before, after, rem, add))
            continue
        i += 1
    return message, hunks


def detect_language(path: str) -> Optional[str]:
    return LANG_BY_EXT.get(os.path.splitext(path)[1].lower())


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s)


def _only_comments(lines: list[str], lang: str) -> bool:
    prefixes = COMMENT_PREFIX.get(lang, DEFAULT_COMMENT_PREFIX)
    changed = [l.strip() for l in lines if l.strip()]
    return bool(changed) and all(l.startswith(prefixes) for l in changed)


# ───────────────────────── البوابات ─────────────────────────

def split_of(key: str, eval_pct: int = 15) -> str:
    """حجز ثابت بالهاش، مفتاحه commit كامل فتبقى كل عيّنات الـ commit في جهة واحدة."""
    h = int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)
    return "eval" if (h % 100) < eval_pct else "train"


def gate_license(meta: Optional[dict], allowed: set, min_stars: int) -> Optional[str]:
    if not meta or meta.get("gone"):
        return "repo_gone"
    if meta.get("archived"):
        return "repo_archived"
    lic = (meta.get("license") or "").lower()
    if not lic or lic in ("noassertion", "other"):
        return "license_missing"
    if lic not in allowed:
        return f"license_not_allowed:{lic}"
    if int(meta.get("stars") or 0) < min_stars:
        return "repo_low_confidence"
    return None


def has_secret(text: str) -> bool:
    return any(p.search(text) for p in SECRET_RES)


def gate_sample(s: dict) -> Optional[str]:
    if not s["patched_code"].strip():
        return "no_patch"
    if _norm(s["vulnerable_code"]) == _norm(s["patched_code"]):
        return "no_semantic_change"
    if has_secret(s["vulnerable_code"] + s["patched_code"]):
        return "secret_detected"
    if len(s["causal_explanation"].strip()) < 30:
        return "no_causal_explanation"
    return None


# ───────────────────────── الحالة والكتابة ─────────────────────────

class Store:
    def __init__(self, path: Path):
        self.db = sqlite3.connect(str(path))
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS vuln(id TEXT PRIMARY KEY, status TEXT, reason TEXT, ts REAL);
            CREATE TABLE IF NOT EXISTS hashes(h TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS repo_meta(repo TEXT PRIMARY KEY, j TEXT, ts REAL);
        """)
        self.db.commit()

    def is_done(self, vid: str) -> bool:
        return self.db.execute("SELECT 1 FROM vuln WHERE id=?", (vid,)).fetchone() is not None

    def mark(self, vid: str, status: str, reason: str = "") -> None:
        self.db.execute("INSERT OR REPLACE INTO vuln VALUES(?,?,?,?)", (vid, status, reason, time.time()))
        self.db.commit()

    def add_hash(self, h: str) -> bool:
        """True إذا كانت جديدة."""
        cur = self.db.execute("INSERT OR IGNORE INTO hashes VALUES(?)", (h,))
        self.db.commit()
        return cur.rowcount == 1

    def get_repo(self, key: str) -> Optional[dict]:
        row = self.db.execute("SELECT j FROM repo_meta WHERE repo=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def put_repo(self, key: str, meta: dict) -> None:
        self.db.execute("INSERT OR REPLACE INTO repo_meta VALUES(?,?,?)", (key, json.dumps(meta), time.time()))
        self.db.commit()

    def reset_rejected(self, reasons: list) -> int:
        """يعيد فتح سجلات رُفضت بأسباب معيّنة (مثلاً بعد تحسين البوابة)."""
        if not reasons:
            return 0
        q = ",".join("?" * len(reasons))
        cur = self.db.execute(f"DELETE FROM vuln WHERE status='rejected' AND reason IN ({q})", reasons)
        self.db.commit()
        return cur.rowcount

    def stats(self) -> dict:
        by_status = dict(self.db.execute("SELECT status, COUNT(*) FROM vuln GROUP BY status"))
        reasons = dict(self.db.execute(
            "SELECT reason, COUNT(*) FROM vuln WHERE status='rejected' GROUP BY reason ORDER BY 2 DESC"))
        samples = self.db.execute("SELECT COUNT(*) FROM hashes").fetchone()[0]
        return {"vulns": by_status, "reject_reasons": reasons, "unique_samples": samples}


class ShardWriter:
    """يكتب دائماً في ملفات جديدة بأسماء فريدة (لا استبدال ولا محو لما سبق)."""

    def __init__(self, out_dir: Path, shard_size: int = 2000):
        self.dir, self.size = out_dir, shard_size
        self.run_id = time.strftime("%Y%m%dT%H%M%S")
        self.n, self.in_shard, self.total = 0, 0, 0
        self.files: list[str] = []

    def write(self, sample: dict) -> None:
        if self.in_shard == 0 or self.in_shard >= self.size:
            self.n += 1
            self.in_shard = 0
        path = self.dir / f"samples_{self.run_id}_{self.n:05d}.jsonl.gz"
        if path.name not in self.files:
            self.files.append(path.name)
        with gzip.open(path, "at", encoding="utf-8") as f:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")
        self.in_shard += 1
        self.total += 1


# ───────────────────────── المنقّب ─────────────────────────

@dataclass
class Config:
    out_dir: Path
    languages: Optional[set] = None
    allowed_licenses: set = field(default_factory=lambda: set(ALLOWED_LICENSES))
    min_stars: int = 10
    eval_pct: int = 15
    max_files_per_commit: int = 10
    max_hunks_per_commit: int = 12
    max_fixes_per_vuln: int = 3
    shard_size: int = 2000
    request_delay: float = 1.0


class Miner:
    def __init__(self, store: Store, http: Http, writer: ShardWriter, cfg: Config,
                 sleep: Callable[[float], None] = time.sleep):
        self.store, self.http, self.writer, self.cfg, self.sleep = store, http, writer, cfg, sleep
        self.counts: Counter = Counter()
        self.last_error: str = ""
        self.consec_deferred: int = 0
        self.rate_wait_until: float = 0.0

    # ── إدارة النتائج
    def _reject(self, vid: str, reason: str) -> str:
        self.store.mark(vid, "rejected", reason)
        return f"rejected:{reason}"

    # ── GitHub
    def _license_from_files(self, owner: str, repo: str) -> Optional[str]:
        for name in LICENSE_FILES:
            self.sleep(self.cfg.request_delay)
            try:
                txt = self.http.get_text(f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{name}")
            except NotFound:
                continue
            lic = detect_license_from_text(txt)
            if lic:
                return lic
        return None

    def repo_meta(self, owner: str, repo: str) -> dict:
        key = f"{owner}/{repo}".lower()
        meta = self.store.get_repo(key)
        if meta is None:
            self.sleep(self.cfg.request_delay)
            try:
                d = json.loads(self.http.get_bytes(f"https://api.github.com/repos/{owner}/{repo}",
                                                   accept="application/vnd.github+json"))
                lic = d.get("license")
                meta = {"license": lic.get("spdx_id") if isinstance(lic, dict) else None,
                        "archived": bool(d.get("archived")), "stars": d.get("stargazers_count", 0)}
            except NotFound:
                meta = {"gone": True}
            self.store.put_repo(key, meta)
        if meta.get("gone") or meta.get("archived") or meta.get("lf_checked"):
            return meta
        if (meta.get("license") or "").lower() not in ("", "noassertion", "other"):
            return meta
        # واجهة GitHub لم تتعرف على الترخيص: اقرأ ملف الترخيص نفسه (لا يستهلك حصة الـ API)
        found = self._license_from_files(owner, repo)
        meta = {**meta, "lf_checked": True}
        if found:
            meta["license"], meta["license_source"] = found, "license_file"
        self.store.put_repo(key, meta)
        return meta

    # ── المعالجة
    def process_vuln(self, rec: dict) -> str:
        vid = rec.get("id") or ""
        if not vid:
            return "invalid"
        if self.store.is_done(vid):
            return "skipped_done"
        if vid.startswith("MAL-") or rec.get("withdrawn"):
            return self._reject(vid, "malware_or_withdrawn")
        fixes = extract_fix_commits(rec)[: self.cfg.max_fixes_per_vuln]
        if not fixes:
            return self._reject(vid, fix_diagnosis(rec))

        cwes, cwe_src = extract_cwes(rec)
        reasons: Counter = Counter()
        accepted = 0
        for owner, repo, sha in fixes:
            try:
                meta = self.repo_meta(owner, repo)
                bad = gate_license(meta, self.cfg.allowed_licenses, self.cfg.min_stars)
                if bad:
                    reasons[bad] += 1
                    continue
                self.sleep(self.cfg.request_delay)
                patch = self.http.get_text(f"https://github.com/{owner}/{repo}/commit/{sha}.patch")
            except NotFound:
                reasons["commit_not_found"] += 1
                continue
            except FetchFailed as e:
                msg = str(e)[:200]
                if msg != self.last_error:          # اطبع كل سبب جديد مرة واحدة
                    print(f"[تأجيل] {vid}: {msg}", file=sys.stderr)
                self.last_error = msg
                if isinstance(e, RateLimited):
                    self.rate_wait_until = e.reset_at
                return "deferred"  # لا يُسجَّل: يُعاد لاحقاً

            message, hunks = parse_patch(patch)
            code = [h for h in hunks if detect_language(h.path)
                    and not SKIP_PATH_RE.search(h.path)]
            if self.cfg.languages:
                code = [h for h in code if detect_language(h.path) in self.cfg.languages]
            if not code:
                reasons["no_code_hunks"] += 1
                continue
            if len({h.path for h in code}) > self.cfg.max_files_per_commit or \
                    len(code) > self.cfg.max_hunks_per_commit:
                reasons["commit_too_broad"] += 1
                continue

            full_sha = sha.lower()
            split = split_of(f"{owner}/{repo}@{full_sha[:7]}".lower(), self.cfg.eval_pct)
            explanation = (f"{rec.get('summary', '').strip()}\n\n{rec.get('details', '').strip()[:1200]}"
                           f"\n\nFix commit message:\n{message[:600]}").strip()
            for idx, h in enumerate(code):
                lang = detect_language(h.path)
                n_changed = len(h.removed) + len(h.added)
                if not (1 <= n_changed <= 80 and 3 <= len(h.before) <= 150 and len(h.after) <= 200):
                    reasons["hunk_size"] += 1
                    continue
                if _only_comments(h.removed + h.added, lang):
                    reasons["comment_only_change"] += 1
                    continue
                s = {
                    "id": hashlib.sha1(f"{vid}|{owner}/{repo}|{sha}|{h.path}|{idx}".encode()).hexdigest()[:16],
                    "source": "osv", "osv_id": vid, "aliases": rec.get("aliases") or [],
                    "cwe": cwes, "cwe_source": cwe_src, "language": lang,
                    "repo": f"{owner}/{repo}", "commit": sha, "file": h.path,
                    "function_context": h.context,
                    "vulnerable_code": "\n".join(h.before), "patched_code": "\n".join(h.after),
                    "causal_explanation": explanation,
                    "license": meta.get("license"),
                    "verification_level": "pattern_only",  # تُرقّى لاحقاً بالتنفيذ/الترجمة داخل الصندوق
                    "split": split,
                }
                bad = gate_sample(s)
                if bad:
                    reasons[bad] += 1
                    continue
                digest = hashlib.sha256((_norm(s["vulnerable_code"]) + "||" + _norm(s["patched_code"])).encode()).hexdigest()
                if not self.store.add_hash(digest):
                    reasons["duplicate"] += 1
                    continue
                self.writer.write(s)
                accepted += 1

        if accepted:
            self.store.mark(vid, "accepted", str(accepted))
            return f"accepted:{accepted}"
        return self._reject(vid, reasons.most_common(1)[0][0] if reasons else "no_samples")


# ───────────────────────── التشغيل ─────────────────────────

def iter_osv_zip(path: Path) -> Iterator[dict]:
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if name.endswith(".json"):
                try:
                    yield json.loads(z.read(name))
                except (ValueError, KeyError):
                    continue


_TOKEN_KEY = re.compile(r"^(GITHUB_TOKEN|GH_TOKEN)(?:_(\d+))?$")


def load_env_tokens(path: str) -> list:
    """يقرأ مفاتيح GitHub فقط (GITHUB_TOKEN / GH_TOKEN / GITHUB_TOKEN_N) بالترتيب.
    يتجاهل كل مفتاح آخر في الملف (Groq, HF, Cloudflare...) ولا يطبع أي قيمة."""
    try:
        text = Path(path).expanduser().read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    found = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, sep, val = line.partition("=")
        m_ = _TOKEN_KEY.match(key.strip()) if sep else None
        val = val.strip().strip("\"'").strip()
        if m_ and val:
            found.append((int(m_.group(2)) if m_.group(2) else 0, len(found), val))
    return [v for _, _, v in sorted(found)]


def load_env_token(path: str) -> Optional[str]:
    toks = load_env_tokens(path)
    return toks[0] if toks else None


def probe_github(http: Http) -> tuple:
    """يتحقق من التوكن/الاتصال بـ GitHub قبل البدء. يعيد (معلومات_الحصة, رسالة_خطأ)."""
    try:
        d = json.loads(http.get_bytes("https://api.github.com/rate_limit"))
        core = (d.get("resources") or {}).get("core") or {}
        return {"limit": core.get("limit"), "remaining": core.get("remaining")}, None
    except (FetchFailed, NotFound, ValueError) as e:
        return None, str(e)[:200]


def ensure_zip(http: Http, eco: str, cache: Path, max_age_h: float = 24) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    dest = cache / f"{eco.replace('/', '_')}.zip"
    if not dest.exists() or (time.time() - dest.stat().st_mtime) > max_age_h * 3600:
        http.download(OSV_ZIP_URL.format(eco=eco), dest)
    return dest


def write_status(cfg: Config, miner: Miner, eco: str, state: str) -> None:
    data = {"state": state, "ecosystem": eco, "ts": time.time(),
            "run_counts": dict(miner.counts), "last_error": miner.last_error,
            "samples_written_this_run": miner.writer.total,
            "shards": miner.writer.files, **miner.store.stats()}
    tmp = cfg.out_dir / "STATUS.json.tmp"
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, cfg.out_dir / "STATUS.json")


def run_ecosystem(miner: Miner, zip_path: Path, eco: str, should_stop: Callable[[], bool],
                  status_every: int = 25) -> None:
    for i, rec in enumerate(iter_osv_zip(zip_path), 1):
        if should_stop():
            break
        try:
            status = miner.process_vuln(rec)
        except Exception as e:  # سجل واحد معطوب لا يوقف التشغيل المستمر
            miner.counts["error"] += 1
            print(f"[خطأ] {rec.get('id')}: {e!r}", file=sys.stderr)
            continue
        miner.counts[status.split(":")[0]] += 1
        if status == "deferred" and miner.rate_wait_until > time.time():
            wait = min(miner.rate_wait_until - time.time(), 3700)
            print(f"[انتظار] حصة GitHub نفدت؛ أنتظر ~{int(wait / 60) + 1} دقيقة دون أي طلب.", file=sys.stderr)
            write_status(miner.cfg, miner, eco, "waiting_rate_limit")
            waited = 0.0
            while waited < wait and not should_stop():
                miner.sleep(5)
                waited += 5
            miner.rate_wait_until = 0.0
            miner.consec_deferred = 0
            continue
        if status == "deferred":
            miner.consec_deferred += 1
            if miner.consec_deferred >= 20:     # فشل منهجي (حظر/توكن/شبكة): لا تطحن السجلات
                print(f"[توقف مؤقت 60ث] 20 تأجيلاً متتالياً. آخر سبب: {miner.last_error}", file=sys.stderr)
                miner.sleep(60)
                miner.consec_deferred = 0
        else:
            miner.consec_deferred = 0
        if i % status_every == 0:
            write_status(miner.cfg, miner, eco, "running")


def run_loop(miner: Miner, http: Http, ecosystems: list, out: Path, should_stop: Callable[[], bool],
             forever: bool, idle_seconds: float = 1800, sleep: Callable[[float], None] = time.sleep,
             max_passes: Optional[int] = None) -> int:
    """يمرّ على كل الأنظمة البيئية؛ في الوضع المستمر يكرر للأبد: يجلب سجلات OSV الجديدة
    (تُحدَّث الملفات المخزّنة كل 24 ساعة) ويعيد المؤجَّل، وينام قليلاً حين لا يوجد جديد."""
    passes = 0
    while not should_stop():
        passes += 1
        before = miner.writer.total
        for eco in ecosystems:
            if should_stop():
                break
            write_status(miner.cfg, miner, eco, "downloading")
            try:
                zp = ensure_zip(http, eco, out / "cache")
            except (FetchFailed, NotFound) as e:
                print(f"[تخطي] {eco}: {e}", file=sys.stderr)
                continue
            run_ecosystem(miner, zp, eco, should_stop)
            write_status(miner.cfg, miner, eco, "ecosystem_done")
        if not forever or (max_passes and passes >= max_passes):
            break
        # لا جديد؟ نم على شرائح قصيرة لنبقى قابلين للإيقاف
        idle = idle_seconds if miner.writer.total == before else 60
        write_status(miner.cfg, miner, "-", f"idle_{int(idle)}s")
        waited = 0.0
        while waited < idle and not should_stop():
            sleep(min(5, idle - waited))
            waited += 5
    return passes


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="منقّب الحقيقة التاريخية — مرصد")
    ap.add_argument("--auto", action="store_true", help="تشغيل مستمر بلا نهاية مع استئناف (الافتراضي)")
    ap.add_argument("--once", action="store_true", help="مرور واحد فقط ثم الخروج")
    ap.add_argument("--idle-minutes", type=float, default=30, help="انتظار حين لا يوجد جديد (الوضع المستمر)")
    ap.add_argument("--out", default=os.path.expanduser("~/Marsad/data/truth"))
    ap.add_argument("--env-file", default="", help="ملف KEY=VALUE يُقرأ منه GITHUB_TOKEN فقط (يتفوق على متغير البيئة)")
    ap.add_argument("--ecosystems", default=",".join(DEFAULT_ECOSYSTEMS))
    ap.add_argument("--languages", default="", help="مثال: c,cpp,php (فارغ = الكل)")
    ap.add_argument("--budget-minutes", type=float, default=0, help="0 = بلا حد")
    ap.add_argument("--retry-rejected", default="",
                    help="أسباب رفض تُعاد معالجتها (مفصولة بفواصل)، مثل: license_missing,no_fix_commit")
    ap.add_argument("--min-stars", type=int, default=10)
    ap.add_argument("--licenses", default="", help="يستبدل القائمة المسموحة (مفصولة بفواصل)")
    a = ap.parse_args(argv)

    out = Path(a.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    cfg = Config(out_dir=out, min_stars=a.min_stars,
                 languages=set(filter(None, a.languages.split(","))) or None)
    if a.licenses:
        cfg.allowed_licenses = {x.strip().lower() for x in a.licenses.split(",") if x.strip()}
    if a.env_file:
        candidates = load_env_tokens(a.env_file)
        if not candidates:
            print(f"[تحذير] لا يوجد مفتاح GitHub في {a.env_file} (أو الملف غير موجود). أعمل بدون توكن.",
                  file=sys.stderr)
    else:
        t0 = (os.environ.get("GITHUB_TOKEN") or "").strip()
        candidates = [t0] if t0 else []
    http = Http(token=None)
    token = None
    for i, cand in enumerate(candidates, 1):     # احتياط للصلاحية: أول مفتاح صالح فقط (لا تدوير)
        http.token = cand
        info, err = probe_github(http)
        if err and "401" in err:
            print(f"[تحذير] مفتاح GitHub رقم {i} مرفوض (401). أجرّب التالي.", file=sys.stderr)
            continue
        token = cand
        if err:
            print(f"[تحذير] تعذّر التحقق من GitHub الآن ({err}); سأستخدم المفتاح رقم {i}.", file=sys.stderr)
        else:
            print(f"[GitHub] المفتاح رقم {i} صالح. الحصة المتبقية: {info['remaining']}/{info['limit']}",
                  file=sys.stderr)
        break
    http.token = token
    if candidates and not token:
        print("[تحذير] كل مفاتيح GitHub مرفوضة. أعمل بدون توكن.", file=sys.stderr)
    cfg.request_delay = 0.2 if token else 1.0
    store = Store(out / "state.sqlite")
    reopened = store.reset_rejected([r.strip() for r in a.retry_rejected.split(",") if r.strip()])
    if reopened:
        print(f"[إعادة فتح] {reopened} سجلاً مرفوضاً سيُعاد تقييمه.", file=sys.stderr)
    miner = Miner(store, http, ShardWriter(out, cfg.shard_size), cfg)

    stop = {"flag": False}
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.update(flag=True))
    deadline = time.time() + a.budget_minutes * 60 if a.budget_minutes else None
    should_stop = lambda: stop["flag"] or (deadline is not None and time.time() > deadline)

    ecosystems = [e.strip() for e in a.ecosystems.split(",") if e.strip()]
    run_loop(miner, http, ecosystems, out, should_stop, forever=not a.once,
             idle_seconds=a.idle_minutes * 60)

    write_status(cfg, miner, "-", "stopped" if should_stop() else "finished")
    print(json.dumps(miner.store.stats(), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
