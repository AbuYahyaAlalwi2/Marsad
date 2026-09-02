"""
منفّذ Sandbox — يطبّق حرفياً الإعدادات المتفق عليها في دستور النظام:
  network=none | memory=256m | cpus=0.5 | pids-limit=64 |
  cap-drop=ALL | no-new-privileges | rootfs للقراءة فقط | timeout=10s
يعمل عبر Docker CLI مباشرة (يحتاج Docker متاح في بيئة التشغيل —
على Render/Railway هذا مدعوم بعكس Cloudflare Workers).
"""

import subprocess
import tempfile
import os
import re
import uuid

TIMEOUT_SECONDS = 10
MEMORY_LIMIT = "256m"
CPU_LIMIT = "0.5"
PIDS_LIMIT = "64"
SANDBOX_IMAGE = os.environ.get("MARSAD_SANDBOX_IMAGE", "python:3.11-slim")

_SAFE_FILENAME_RE = re.compile(r"^[a-zA-Z0-9._\-]+$")


def sanitize_arg(value: str) -> str | None:
    """بند 4 من ملف تحصين sandbox: رفض كامل بدل تعديل جزئي لأي مدخل غير آمن."""
    if not value or not _SAFE_FILENAME_RE.match(value):
        return None
    return value


def run_code_in_sandbox(code: str, language: str = "python") -> dict:
    """
    ينفّذ كوداً داخل حاوية Docker معزولة تماماً ويُرجع نتيجة التحقق.
    لا يُعيد استخدام نفس معرّف الحاوية لمهام مختلفة (بند 5 من ملف التحصين).
    """
    run_id = f"marsad-sandbox-{uuid.uuid4().hex[:12]}"

    with tempfile.TemporaryDirectory() as tmpdir:
        entry_file = os.path.join(tmpdir, "sample.py" if language == "python" else "sample.txt")
        with open(entry_file, "w", encoding="utf-8") as f:
            f.write(code)

        docker_cmd = [
            "docker", "run",
            "--name", run_id,
            "--rm",
            "--network", "none",
            "--memory", MEMORY_LIMIT,
            "--memory-swap", MEMORY_LIMIT,   # يمنع استخدام swap إضافي
            "--cpus", CPU_LIMIT,
            "--pids-limit", PIDS_LIMIT,
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--read-only",
            "--tmpfs", "/tmp:size=32m",
            "--user", "1000:1000",           # مستخدم غير root
            "-v", f"{entry_file}:/sandbox/sample.py:ro",
            SANDBOX_IMAGE,
            "python", "/sandbox/sample.py",
        ]

        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
            )
            passed = result.returncode == 0
            return {
                "run_id": run_id,
                "status": "passed" if passed else "rejected",
                "reject_reason": None if passed else f"nonzero_exit_{result.returncode}",
                "stdout": result.stdout[-2000:],
                "stderr": result.stderr[-2000:],
            }
        except subprocess.TimeoutExpired:
            # قتل الحاوية فوراً — لا grace period (مطابق للاتفاق)
            subprocess.run(["docker", "kill", run_id], capture_output=True)
            return {
                "run_id": run_id,
                "status": "rejected",
                "reject_reason": "timeout_10s",
                "stdout": "",
                "stderr": "",
            }
        except FileNotFoundError:
            # Docker غير متاح في بيئة التشغيل — رفض آمن بدل ادّعاء نجاح (بند 5 من الدستور)
            return {
                "run_id": run_id,
                "status": "rejected",
                "reject_reason": "docker_runtime_unavailable",
                "stdout": "",
                "stderr": "",
            }
