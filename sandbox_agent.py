"""
CYBERGUARD OS - Sandbox Agent
Executes code in isolated env (Daytona) or local subprocess fallback.
"""
import os
import time
import logging
import subprocess
import tempfile
from typing import Dict, Any

from config import (
    SANDBOX_ENABLED, SANDBOX_DEFAULT_LANGUAGE,
    SANDBOX_MAX_EXECUTION_TIME, SANDBOX_AUTO_STOP_MIN,
)
from db import log_event

logger = logging.getLogger(__name__)


class SandboxAgent:
    def __init__(self):
        self._daytona = None
        self._available = False
        if SANDBOX_ENABLED:
            self._try_init_daytona()

    def _try_init_daytona(self):
        try:
            from daytona_sdk import Daytona, DaytonaConfig
            self._daytona = Daytona(DaytonaConfig())
            self._available = True
            logger.info("[Sandbox] Daytona ready")
        except ImportError:
            logger.warning("[Sandbox] Daytona not installed - using local fallback")
            self._available = False
        except Exception as e:
            logger.warning(f"[Sandbox] Daytona init failed: {e}")
            self._available = False

    def run(self, code: str, language: str = None, timeout: float = None) -> Dict[str, Any]:
        language = language or SANDBOX_DEFAULT_LANGUAGE
        timeout = timeout or SANDBOX_MAX_EXECUTION_TIME
        start = time.time()

        if self._available:
            result = self._run_daytona(code, language, timeout)
        else:
            result = self._run_local(code, language, timeout)

        result["duration_ms"] = (time.time() - start) * 1000.0
        result["language"] = language

        try:
            log_event("sandbox", {
                "status": result.get("status"),
                "language": language,
                "duration_ms": result["duration_ms"],
            })
        except Exception:
            pass

        return result

    def _run_daytona(self, code: str, language: str, timeout: float) -> Dict[str, Any]:
        try:
            sandbox = self._daytona.create()
            try:
                result = sandbox.process.code_run(code, language=language)
                return {
                    "status": "ok" if result.exit_code == 0 else "error",
                    "stdout": getattr(result, "result", "") or "",
                    "stderr": getattr(result, "stderr", "") or "",
                    "exit_code": result.exit_code,
                }
            finally:
                try:
                    self._daytona.remove(sandbox)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"[Sandbox] Daytona run failed: {e}")
            return self._run_local(code, language, timeout)

    def _run_local(self, code: str, language: str, timeout: float) -> Dict[str, Any]:
        ext_map = {
            "python": ".py", "py": ".py",
            "javascript": ".js", "js": ".js", "node": ".js",
            "typescript": ".ts", "ts": ".ts",
            "bash": ".sh", "sh": ".sh",
        }
        ext = ext_map.get(language.lower(), ".txt")

        cmd_map = {
            ".py": ["python3"],
            ".js": ["node"],
            ".ts": ["npx", "ts-node"],
            ".sh": ["bash"],
        }
        cmd = cmd_map.get(ext)

        if not cmd:
            return {"status": "error",
                    "stdout": "", "stderr": f"Unsupported language: {language}",
                    "exit_code": -1, "fallback": True}

        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=ext,
                                             delete=False, encoding="utf-8") as f:
                f.write(code)
                path = f.name

            try:
                proc = subprocess.run(
                    cmd + [path],
                    capture_output=True, text=True,
                    timeout=timeout,
                )
                return {
                    "status": "ok" if proc.returncode == 0 else "error",
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                    "exit_code": proc.returncode,
                    "fallback": True,
                }
            finally:
                try:
                    os.unlink(path)
                except Exception:
                    pass
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "stdout": "",
                    "stderr": f"Exceeded {timeout}s",
                    "exit_code": -1, "fallback": True}
        except Exception as e:
            return {"status": "error", "stdout": "", "stderr": str(e),
                    "exit_code": -1, "fallback": True}


sandbox_agent = SandboxAgent()
