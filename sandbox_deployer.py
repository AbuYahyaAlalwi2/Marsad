"""
sandbox_deployer.py (Local Mode for Termux)
ينشر ProjectArtifact محلياً في مجلد مؤقت، ويشغّل دورة تحقق دفاعية بحتة.
"""
from __future__ import annotations
import os, time, tempfile, subprocess, shutil
from dataclasses import dataclass
from typing import Optional
from deepseek_adapter import ProjectArtifact

@dataclass
class SandboxHandle:
    sandbox_id: str
    project_root: str
    scenario_id: str
    language: str

INSTALL_CMD_BY_LANG = {
    "python": "pip install pytest --quiet --break-system-packages || true",
    "node": "npm install --silent || true",
    "go": "go mod tidy || true",
}

def _write_files_local(project_root: str, files: dict[str, str]) -> None:
    for rel_path, content in files.items():
        full_path = os.path.join(project_root, rel_path.lstrip('/'))
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)

def deploy_project(artifact: ProjectArtifact, language: str, scenario_id: str,
                   timeout_seconds: int = 600) -> SandboxHandle:
    project_root = tempfile.mkdtemp(prefix=f"marsad_sandbox_{scenario_id}_")
    _write_files_local(project_root, artifact.base_code)
    test_path = os.path.join(project_root, "test_verification.py")
    with open(test_path, 'w', encoding='utf-8') as f:
        f.write(artifact.verification_test)
    install_cmd = INSTALL_CMD_BY_LANG.get(language)
    if install_cmd and language == "python":
        try:
            subprocess.run(["pip", "install", "pytest", "-q", "--break-system-packages"],
                          capture_output=True, timeout=60)
        except Exception:
            pass
    return SandboxHandle(
        sandbox_id="local_termux_sandbox",
        project_root=project_root,
        scenario_id=scenario_id,
        language=language,
    )

@dataclass
class StepResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_seconds: float

def _run_timed_local(handle: SandboxHandle, command: str, timeout_seconds: int = 120) -> StepResult:
    start = time.monotonic()
    try:
        result = subprocess.run(command, shell=True, cwd=handle.project_root,
                               capture_output=True, text=True, timeout=timeout_seconds)
        duration = time.monotonic() - start
        return StepResult(
            success=(result.returncode == 0),
            stdout=result.stdout[-1000:],
            stderr=result.stderr[-1000:],
            exit_code=result.returncode,
            duration_seconds=duration,
        )
    except subprocess.TimeoutExpired:
        return StepResult(success=False, stdout="", stderr="Timeout",
                         exit_code=-1, duration_seconds=time.monotonic() - start)

def run_verification_test(handle: SandboxHandle) -> StepResult:
    return _run_timed_local(handle, "python3 -m pytest test_verification.py -q", timeout_seconds=60)

def apply_patch(handle: SandboxHandle, patched_code: dict[str, str]) -> StepResult:
    start = time.monotonic()
    _write_files_local(handle.project_root, patched_code)
    duration = time.monotonic() - start
    return StepResult(success=True, stdout="patched", stderr="", exit_code=0, duration_seconds=duration)

def run_regression(handle: SandboxHandle, test_cmd: str = "python3 -m pytest -q") -> StepResult:
    return _run_timed_local(handle, test_cmd, timeout_seconds=60)

def teardown(handle: SandboxHandle) -> None:
    shutil.rmtree(handle.project_root, ignore_errors=True)

def run_full_round(handle: SandboxHandle, *, artifact: ProjectArtifact, defect_class: str,
                   max_fix_attempts: int = 1) -> dict:
    round_start = time.monotonic()
    initial = run_verification_test(handle)
    defect_confirmed = not initial.success
    fix_verified = False
    regression_passed = True
    attempt_count = 0
    if defect_confirmed:
        for attempt_count in range(1, max_fix_attempts + 1):
            apply_patch(handle, artifact.patched_code)
            retry = run_verification_test(handle)
            if retry.success:
                fix_verified = True
                break
        else:
            attempt_count = max_fix_attempts
        regression = run_regression(handle)
        regression_passed = regression.success
    return {
        "source": "e2b_agent",
        "defect_class": defect_class,
        "base_code": artifact.base_code,
        "verification_test": artifact.verification_test,
        "patched_code": artifact.patched_code if fix_verified else None,
        "execution_log": (
            f"--- initial test (expect failure) ---\n{initial.stdout}\n{initial.stderr}\n"
            f"--- fix verification (attempts={attempt_count}) ---\n"
            f"defect_confirmed={defect_confirmed}, fix_verified={fix_verified}, "
            f"regression_passed={regression_passed}"
        ),
        "defect_confirmed": defect_confirmed,
        "fix_verified": fix_verified,
        "regression_passed": regression_passed,
        "attempt_count": max(attempt_count, 1),
        "time_to_fix_seconds": time.monotonic() - round_start,
        "sandbox_id": handle.sandbox_id,
    }
