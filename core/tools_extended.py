"""أدوات إضافية لـ Marsad — 7 أدوات."""
from __future__ import annotations
import hashlib
import json
import re
import socket
from pathlib import Path
from typing import Dict, Any

# استيراد متسامح
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.tool_calling import registry


def _scan_port(host: str, port: int = 80, timeout: float = 3.0) -> Dict:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return {"host": host, "port": int(port), "open": True}
    except Exception as e:
        return {"host": host, "port": int(port), "open": False, "error": str(e)[:100]}


def _dns_lookup(domain: str) -> Dict:
    try:
        return {"domain": domain, "ipv4": socket.gethostbyname(domain),
                "fqdn": socket.getfqdn(domain)}
    except Exception as e:
        return {"domain": domain, "error": str(e)[:100]}


def _whois_lookup(domain: str) -> Dict:
    import httpx
    try:
        r = httpx.get(f"https://rdap.org/domain/{domain}",
                      timeout=15, follow_redirects=True)
        if r.status_code != 200:
            return {"domain": domain, "error": f"HTTP {r.status_code}"}
        d = r.json()
        return {
            "domain": domain,
            "handle": d.get("handle", ""),
            "status": d.get("status", []),
            "events": [{"action": e.get("eventAction"),
                        "date": e.get("eventDate")}
                       for e in d.get("events", [])],
        }
    except Exception as e:
        return {"domain": domain, "error": str(e)[:150]}


def _hash_file(path: str, algorithm: str = "sha256") -> Dict:
    p = Path(path).expanduser()
    if not p.exists():
        return {"path": path, "error": "file not found"}
    try:
        h = hashlib.new(algorithm)
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return {"path": str(p), "algorithm": algorithm,
                "hash": h.hexdigest(), "size": p.stat().st_size}
    except Exception as e:
        return {"path": path, "error": str(e)[:100]}


def _parse_json(text: str, query: str = "") -> Dict:
    try:
        data = json.loads(text)
    except Exception as e:
        return {"error": f"invalid JSON: {e}"}
    if not query:
        if isinstance(data, dict):
            return {"keys": list(data.keys())[:20]}
        if isinstance(data, list):
            return {"length": len(data), "first": data[0] if data else None}
        return {"value": data}
    cur = data
    for part in query.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except Exception:
                return {"error": f"bad index: {part}"}
        else:
            return {"error": f"cannot descend into: {type(cur).__name__}"}
    return {"query": query, "value": cur}


def _diff_files(path_a: str, path_b: str) -> Dict:
    import difflib
    a, b = Path(path_a).expanduser(), Path(path_b).expanduser()
    if not a.exists() or not b.exists():
        return {"error": "file not found"}
    try:
        ta = a.read_text(errors="ignore").splitlines()
        tb = b.read_text(errors="ignore").splitlines()
        diff = list(difflib.unified_diff(ta, tb, str(a), str(b), lineterm=""))
        return {
            "additions": sum(1 for l in diff if l.startswith("+") and not l.startswith("+++")),
            "deletions": sum(1 for l in diff if l.startswith("-") and not l.startswith("---")),
            "diff_preview": "\n".join(diff[:100])[:2000],
        }
    except Exception as e:
        return {"error": str(e)[:100]}


def _regex_extract(text: str, pattern: str, group: int = 0) -> Dict:
    try:
        matches = re.findall(pattern, text)
        if matches and isinstance(matches[0], tuple):
            matches = [m[group] for m in matches if len(m) > group]
        return {"pattern": pattern, "count": len(matches), "matches": matches[:50]}
    except Exception as e:
        return {"pattern": pattern, "error": str(e)[:100]}


def register_extended_tools() -> int:
    """يضيف الأدوات السبع إلى registry."""
    tools = [
        ("scan_port", "يفحص منفذ TCP على مضيف",
         {"host": "string", "port": "int", "timeout": "float"}, _scan_port),
        ("dns_lookup", "يحل اسم النطاق إلى IP",
         {"domain": "string"}, _dns_lookup),
        ("whois_lookup", "يجلب معلومات WHOIS (RDAP)",
         {"domain": "string"}, _whois_lookup),
        ("hash_file", "يحسب hash لملف (sha256 افتراضياً)",
         {"path": "string", "algorithm": "string"}, _hash_file),
        ("parse_json", "يحلل JSON ويستخرج مساراً (dot notation)",
         {"text": "string", "query": "string"}, _parse_json),
        ("diff_files", "يقارن ملفين نصيًا",
         {"path_a": "string", "path_b": "string"}, _diff_files),
        ("regex_extract", "يستخرج أنماط regex من نص",
         {"text": "string", "pattern": "string", "group": "int"}, _regex_extract),
    ]
    n = 0
    for name, desc, params, fn in tools:
        if name in registry._tools:
            continue
        try:
            registry.register(name, {"description": desc, "params": params}, fn)
            n += 1
        except Exception as e:
            print(f"warn {name}: {e}")
    return n


_registered = register_extended_tools()


if __name__ == "__main__":
    print("=== Extended Tools ===")
    for name in ["scan_port", "dns_lookup", "whois_lookup", "hash_file",
                 "parse_json", "diff_files", "regex_extract"]:
        print(f"  {name}: {'✓' if name in registry._tools else '✗'}")

    print("\n=== اختبارات ===")
    print("scan_port:", _scan_port("1.1.1.1", 53))
    print("dns_lookup:", _dns_lookup("example.com"))
    print("parse_json:", _parse_json('{"a": {"b": [10, 20, 30]}}', "a.b.1"))
    print("regex:", _regex_extract("a@b.com c@d.com", r"[\w\.-]+@[\w\.-]+"))
