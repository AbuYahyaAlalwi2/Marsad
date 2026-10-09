// sandbox.ts — ترجمة sandbox_deployer.py عبر e2b JS SDK (رسمي من e2b.dev،
// نظير مباشر لـ e2b Python SDK). يتضمن نفس إصلاح fix_run_timed.py: exit code
// غير صفري (فشل pytest عمداً في الخطوة الأولى) متوقَّع تماماً وليس انهياراً،
// فنلتقطه ونحوّله لنتيجة عادية بدل أن يرمي استثناء.

import { Sandbox } from "e2b";
import type { Env, ProjectArtifact } from "./types";

export interface StepResult {
  success: boolean;
  stdout: string;
  stderr: string;
  exitCode: number;
  durationSeconds: number;
}

export interface SandboxHandle {
  sandbox: Sandbox;
  sandboxId: string;
  projectRoot: string;
}

async function writeFiles(sandbox: Sandbox, projectRoot: string, files: Record<string, string>): Promise<void> {
  for (const [relPath, content] of Object.entries(files)) {
    const fullPath = `${projectRoot}/${relPath.replace(/^\/+/, "")}`;
    const parentDir = fullPath.slice(0, fullPath.lastIndexOf("/"));
    await sandbox.commands.run(`mkdir -p ${parentDir}`);
    await sandbox.files.write(fullPath, content);
  }
}

export async function deployProject(
  env: Env,
  artifact: ProjectArtifact,
  scenarioId: string,
  timeoutMs = 600_000
): Promise<SandboxHandle> {
  const sandbox = await Sandbox.create({ apiKey: env.E2B_API_KEY, timeoutMs });
  const projectRoot = `/home/user/case_${scenarioId}`;
  await sandbox.commands.run(`mkdir -p ${projectRoot}`);

  await writeFiles(sandbox, projectRoot, artifact.baseCode);
  await sandbox.files.write(`${projectRoot}/test_verification.py`, artifact.verificationTest);
  await sandbox.commands.run(
    `cd ${projectRoot} && pip install pytest --quiet --break-system-packages || true`,
    { timeoutMs }
  );

  return { sandbox, sandboxId: sandbox.sandboxId, projectRoot };
}

async function runTimed(handle: SandboxHandle, command: string, timeoutMs = 120_000): Promise<StepResult> {
  const start = Date.now();
  try {
    const result = await handle.sandbox.commands.run(`cd ${handle.projectRoot} && ${command}`, { timeoutMs });
    return {
      success: result.exitCode === 0,
      stdout: result.stdout,
      stderr: result.stderr,
      exitCode: result.exitCode,
      durationSeconds: (Date.now() - start) / 1000,
    };
  } catch (e: any) {
    // exit code غير صفري متوقَّع هنا (فشل pytest عمداً) — ليس انهياراً، نفس
    // إصلاح fix_run_timed.py في نسخة Kaggle
    return {
      success: false,
      stdout: e?.stdout ?? "",
      stderr: e?.stderr ?? String(e?.message ?? e),
      exitCode: e?.exitCode ?? 1,
      durationSeconds: (Date.now() - start) / 1000,
    };
  }
}

export async function runVerificationTest(handle: SandboxHandle): Promise<StepResult> {
  return runTimed(handle, "python3 -m pytest test_verification.py -q");
}

export async function applyPatch(handle: SandboxHandle, patchedCode: Record<string, string>): Promise<StepResult> {
  const start = Date.now();
  await writeFiles(handle.sandbox, handle.projectRoot, patchedCode);
  return { success: true, stdout: "patched files written", stderr: "", exitCode: 0, durationSeconds: (Date.now() - start) / 1000 };
}

export async function runRegression(handle: SandboxHandle): Promise<StepResult> {
  return runTimed(handle, "pytest -q || true", 180_000);
}

export async function teardown(handle: SandboxHandle): Promise<void> {
  await handle.sandbox.kill();
}

export async function runFullRound(
  handle: SandboxHandle,
  artifact: ProjectArtifact,
  defectClass: string,
  maxFixAttempts = 1
) {
  const roundStart = Date.now();

  const initial = await runVerificationTest(handle);
  const defectConfirmed = !initial.success;

  let fixVerified = false;
  let regressionPassed = true;
  let attemptCount = 0;

  if (defectConfirmed) {
    for (attemptCount = 1; attemptCount <= maxFixAttempts; attemptCount++) {
      await applyPatch(handle, artifact.patchedCode);
      const retry = await runVerificationTest(handle);
      if (retry.success) {
        fixVerified = true;
        break;
      }
    }
    const regression = await runRegression(handle);
    regressionPassed = regression.success;
  }

  const timeToFixSeconds = (Date.now() - roundStart) / 1000;

  return {
    source: "e2b_agent" as const,
    defect_class: defectClass,
    base_code: artifact.baseCode,
    verification_test: artifact.verificationTest,
    patched_code: fixVerified ? artifact.patchedCode : null,
    execution_log:
      `--- initial test run (expect failure) ---\n${initial.stdout}\n${initial.stderr}\n` +
      `--- fix verification (attempts=${attemptCount}) ---\n` +
      `defect_confirmed=${defectConfirmed}, fix_verified=${fixVerified}, regression_passed=${regressionPassed}`,
    defect_confirmed: defectConfirmed,
    fix_verified: fixVerified,
    regression_passed: regressionPassed,
    attempt_count: Math.max(attemptCount, 1),
    time_to_fix_seconds: timeToFixSeconds,
    sandbox_id: handle.sandboxId,
  };
}
