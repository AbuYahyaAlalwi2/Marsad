"""
sandbox_deployer.py (Local Mode for Termux)
ينشر ProjectArtifact محلياً في مجلد مؤقت، ويشغّل دورة تحقق دفاعية بحتة.
هذا يتجاوز مشكلة E2B SDK مع بيئة Termux (NDK context panic).
المنطق مطابق تماماً لما يفعله E2B: كتابة الملفات -> تشغيل pytest -> استبدال الملفات -> تشغيل pytest.
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

def deploy_project(artifact: ProjectArtifact, language: str, scenario_id: str, timeout_seconds: int = 600) -> SandboxHandle:
    project_root = tempfile.mkdtemp(prefix=f"marsad_sandbox_{scenario_id}_")
    
    # 1. كتابة الكود الأساسي
    for rel_path, content in artifact.base_code.items():
        full_path = os.path.join(project_root, rel_path.lstrip('/'))
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
    # 2. كتابة ملف الاختبار
    test_path = os.path.join(project_root, "test_verification.py")
    with open(test_path, 'w', encoding='utf-8') as f:
        f.write(artifact.verification_test)
        
    # 3. التأكد من تثبيت pytest محلياً
    try:
        subprocess.run(["pip", "install", "pytest", "-q", "--break-system-packages"], capture_output=True)
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

def _run_timed(handle: SandboxHandle, command: str, timeout_seconds: int = 120) -> StepResult:
    start = time.monotonic()
    try:
        result = subprocess.run(
            command, shell=True, cwd=handle.project_root,
            capture_output=True, text=True, timeout=timeout_seconds
        )
        duration = time.monotonic() - start
        return StepResult(
            success=(result.returncode == 0),
            stdout=result.stdout[-1000:], # آخر 1000 حرف لتجنب الإطالة
            stderr=result.stderr[-1000:],
            exit_code=result.returncode,
            duration_seconds=duration,
        )
    except subprocess.TimeoutExpired:
        return StepResult(success=False, stdout="", stderr="Timeout", exit_code=-1, duration_seconds=time.monotonic() - start)

def run_verification_test(handle: SandboxHandle) -> StepResult:
    return _run_timed(handle, "python3 -m pytest test_verification.py -q", timeout_seconds=60)

def apply_patch(handle: SandboxHandle, patched_code: dict[str, str]) -> StepResult:
    start = time.monotonic()
    for rel_path, content in patched_code.items():
        full_path = os.path.join(handle.project_root, rel_path.lstrip('/'))
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
    return StepResult(success=True, stdout="patched", stderr="", exit_code=0, duration_seconds=time.monotonic() - start)

def run_regression(handle: SandboxHandle, test_cmd: str = "python3 -m pytest -q") -> StepResult:
    return _run_timed(handle, test_cmd, timeout_seconds=60)

def teardown(handle: SandboxHandle) -> None:
    shutil.rmtree(handle.project_root, ignore_errors=True)

def run_full_round(handle: SandboxHandle, *, artifact: ProjectArtifact, defect_class: str, max_fix_attempts: int = 1) -> dict:
    round_start = time.monotonic()
    initial = run_verification_test(handle)
    
    # النجاح المتوقَّع هنا هو *فشل* الاختبار (الخطأ المنطقي يُثبَت بفشل pytest)
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
            f"defect_confirmed={defect_confirmed}, fix_verified={fix_verified}, regression_passed={regression_passed}"
        ),
        "defect_confirmed": defect_confirmed,
        "fix_verified": fix_verified,
        "regression_passed": regression_passed,
        "attempt_count": max(attempt_count, 1),
        "time_to_fix_seconds": time.monotonic() - round_start,
        "sandbox_id": handle.sandbox_id,
    }
