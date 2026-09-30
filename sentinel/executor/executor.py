"""
executor.py — Gate 0 Executor.
Backend: Railway Sandbox (Deno + Pyodide).
لا شبكة، لا كتابة، لا أسرار — Deno permission model.
"""
from __future__ import annotations
import os, json, time, hashlib, logging
from dataclasses import dataclass, asdict
from typing import Optional
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

SANDBOX_URL = os.environ.get(
    "MARSAD_SANDBOX_URL",
    "https://marsad-sandbox-production.up.railway.app"
)
SANDBOX_TOKEN = os.environ.get("MARSAD_SANDBOX_TOKEN", "")
DEFAULT_TIMEOUT = 10


def _load_token() -> str:
    tok = SANDBOX_TOKEN
    if tok:
        return tok
    f = Path.home() / ".marsad_secrets" / "sandbox_token.txt"
    if f.exists():
        return f.read_text().strip()
    return ""


@dataclass
class RunResult:
    status: str
    backend: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    code_hash: str
    run_id: str
    ts: float


UNSAFE_PATTERNS = [
    "import socket", "import requests", "import urllib",
    "import httpx", "import subprocess", "os.system",
    "eval(", "exec(", "__import__",
    "rm -rf", "shutil.rmtree",
]


def _detect_unsafe(code: str) -> Optional[str]:
    for pat in UNSAFE_PATTERNS:
        if pat in code:
            return pat
    return None


def _h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:12]


def run_python(code: str, timeout: int = DEFAULT_TIMEOUT) -> RunResult:
    run_id = _h(code) + "-" + str(int(time.time() * 1000))[-6:]
    code_hash = _h(code)
    t0 = time.time()

    unsafe = _detect_unsafe(code)
    if unsafe:
        return RunResult("unsafe", "sandbox", -1, "", f"blocked: {unsafe}",
                         0, code_hash, run_id, t0)

    token = _load_token()
    if not token:
        return RunResult("error", "sandbox", -1, "", "no SANDBOX_TOKEN",
                         0, code_hash, run_id, t0)

    try:
        with httpx.Client(timeout=timeout + 30) as client:
            r = client.post(
                f"{SANDBOX_URL}/run",
                headers={"Authorization": f"Bearer {token}",
                         "Content-Type": "application/json"},
                json={"language": "python", "code": code,
                      "timeoutMs": timeout * 1000},
            )
            if r.status_code != 200:
                return RunResult("error", "sandbox", -1, "",
                                 f"HTTP {r.status_code}: {r.text[:200]}",
                                 int((time.time() - t0) * 1000),
                                 code_hash, run_id, t0)
            b = r.json()
            stdout = b.get("stdout", "")
            stderr = b.get("stderr", "")
            exit_code = b.get("exitCode", 1)
            if b.get("timedOut"):
                status = "timeout"
            elif b.get("ok") and exit_code == 0:
                status = "pass"
            else:
                status = "fail"
            return RunResult(status, "sandbox", exit_code,
                             stdout[:2000], stderr[:2000],
                             int((time.time() - t0) * 1000),
                             code_hash, run_id, t0)
    except Exception as e:
        return RunResult("error", "sandbox", -1, "",
                         f"{type(e).__name__}: {e}"[:300],
                         int((time.time() - t0) * 1000),
                         code_hash, run_id, t0)


def determinism_test(code: str, n: int = 20) -> dict:
    results = []
    for i in range(n):
        r = run_python(code)
        results.append(r)
        print(f"  run {i+1:02d}/{n}: {r.status} ({r.duration_ms}ms)")

    statuses = [r.status for r in results]
    unique = set(statuses)
    valid = {"pass", "fail", "timeout", "unsafe"}
    has_valid = bool(unique & valid)
    deterministic = len(unique) == 1 and has_valid

    return {
        "runs": n,
        "backend": results[0].backend,
        "unique_statuses": list(unique),
        "deterministic": deterministic,
        "has_valid_result": has_valid,
        "statuses": statuses,
        "results": [asdict(r) for r in results],
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("usage: executor.py '<code>'")
        sys.exit(1)
    print("◈ Gate 0 — determinism test (20 runs)")
    report = determinism_test(sys.argv[1], n=20)
    print()
    print(f"backend: {report['backend']}")
    print(f"deterministic: {report['deterministic']}")
    print(f"has_valid_result: {report['has_valid_result']}")
    print(f"unique: {report['unique_statuses']}")
    out = Path.home() / "marsad_reports" / "gate0_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"saved: {out}")
