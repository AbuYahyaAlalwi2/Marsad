"""mesh_workers.py — 4 عمال شبكة (جمع/تصحيح/فلترة/إنشاء)."""
from __future__ import annotations
import os, re, json, time, hashlib, logging
from typing import Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from core.account_pool import with_account, account_pool
except ImportError:
    account_pool = None
    def with_account(p):
        return lambda f: f

OUT = Path(os.environ.get("CG_DATA_DIR", str(__import__("pathlib").Path.home() / "marsad_data")))
OUT.mkdir(parents=True, exist_ok=True)


# ─── 1. الجمع (Collect) ─────────────────────────────────────
@with_account('cloudflare')
def worker_collect(payload: Dict[str, Any], _acc=None) -> Dict[str, Any]:
    """يجمع مقتطفات من قائمة مصادر (لا يحتاج Kaggle)."""
    import httpx
    sources = payload.get("sources", [])
    query = payload.get("query", "")
    saved = 0; errors = []
    client = httpx.Client(timeout=20, follow_redirects=True,
                          headers={"User-Agent": "MarsadCollector/1.0"})
    for url in sources:
        try:
            r = client.get(url)
            if r.status_code == 200 and len(r.text) > 200:
                fp = OUT / f"collected_{hashlib.md5(url.encode()).hexdigest()[:12]}.txt"
                fp.write_text(r.text[:500000], encoding="utf-8", errors="ignore")
                saved += 1
        except Exception as e:
            errors.append(f"{url}: {e}")
    client.close()
    return {"saved": saved, "errors": len(errors), "query": query}


# ─── 2. التصحيح (Fix) ───────────────────────────────────────
def worker_fix(payload: Dict[str, Any]) -> Dict[str, Any]:
    """يصلح أخطاء شائعة في الملفات النصية."""
    path = Path(payload.get("path", ""))
    if not path.exists():
        return {"status": "missing", "path": str(path)}
    txt = path.read_text(encoding="utf-8", errors="ignore")
    original_len = len(txt)
    txt = re.sub(r"[ \t]+$", "", txt, flags=re.MULTILINE)      # trailing spaces
    txt = re.sub(r"\n{4,}", "\n\n\n", txt)                     # extra blank lines
    txt = txt.replace("\r\n", "\n").replace("\r", "\n")        # CRLF → LF
    fixed = OUT / f"fixed_{path.name}"
    fixed.write_text(txt, encoding="utf-8")
    return {"status": "fixed", "path": str(fixed),
            "delta": len(txt) - original_len}


# ─── 3. الفلترة (Filter) ────────────────────────────────────
BAD_PATTERNS = [
    r"<script[^>]*>.*?</script>",
    r"<style[^>]*>.*?</style>",
    r"&nbsp;", r"&amp;", r"&lt;", r"&gt;",
]
BAD_WORDS = {"cookie", "subscribe", "newsletter", "advertisement"}


def worker_filter(payload: Dict[str, Any]) -> Dict[str, Any]:
    """يفلتر HTML/noise من ملف."""
    path = Path(payload.get("path", ""))
    if not path.exists():
        return {"status": "missing"}
    txt = path.read_text(encoding="utf-8", errors="ignore")
    original = len(txt)
    for pat in BAD_PATTERNS:
        txt = re.sub(pat, "", txt, flags=re.DOTALL | re.IGNORECASE)
    txt = re.sub(r"<[^>]+>", "", txt)                          # strip tags
    lines = [l for l in txt.split("\n")
             if len(l.strip()) > 20
             and not any(w in l.lower() for w in BAD_WORDS)]
    cleaned = "\n".join(lines)
    out = OUT / f"clean_{path.name}"
    out.write_text(cleaned, encoding="utf-8")
    return {"status": "filtered", "kept_lines": len(lines),
            "delta_bytes": original - len(cleaned)}


# ─── 4. الإنشاء (Generate) ──────────────────────────────────
def worker_generate(payload: Dict[str, Any]) -> Dict[str, Any]:
    """يولّد زوج (instruction, response) بصيغة تدريب."""
    source = Path(payload.get("path", ""))
    if not source.exists():
        return {"status": "missing"}
    txt = source.read_text(encoding="utf-8", errors="ignore")
    chunks = [c.strip() for c in re.split(r"\n{3,}", txt) if len(c.strip()) > 100]
    samples = []
    for i, chunk in enumerate(chunks[:200]):
        samples.append({
            "instruction": f"حلّل المقتطف التقني التالي:\n{chunk[:200]}...",
            "response": chunk,
            "source": source.name,
            "idx": i,
        })
    out = OUT / f"dataset_{source.stem}.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    return {"status": "generated", "samples": len(samples),
            "path": str(out)}


# ─── التسجيل في الشبكة ─────────────────────────────────────
def register_all_workers(mesh, workers_per_kind: int = 3):
    """يسجّل 12 عاملاً (4 أنواع × 3) في الشبكة."""
    mesh.register("collect",  worker_collect,  count=workers_per_kind)
    mesh.register("fix",      worker_fix,      count=workers_per_kind)
    mesh.register("filter",   worker_filter,   count=workers_per_kind)
    mesh.register("generate", worker_generate, count=workers_per_kind)
    logger.info("[mesh_workers] registered %d workers", workers_per_kind * 4)
    if account_pool:
        logger.info("[mesh_workers] accounts: %s", account_pool.stats())


if __name__ == "__main__":
    print("Workers ready. Call register_all_workers(mesh) to attach.")
