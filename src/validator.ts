// validator.ts — ترجمة حرفية لـ BlueprintValidator من deepseek_adapter.py.
// نفس الفحوصات بالضبط: مكوّنات مفقودة، مسارات غير متطابقة، غياب علامات
// اختبار حقيقية، كلمات هجومية ممنوعة، أنماط ممنوعة حسب المستوى، طبقة
// أدوار مطلوبة، تبعيات حقيقية كافية.

import type { ProjectArtifact, ScenarioBlueprint } from "./types";

const ATTACK_TOKENS = [
  "exploit", "payload", "reverse shell", "reverse_shell", "nc -e",
  "shell_injection", 'os.system("curl', "drop table", "' or '1'='1",
  "metasploit", "rm -rf /", "base64 decode malicious",
];

export function validateArtifact(artifact: ProjectArtifact, blueprint: ScenarioBlueprint): string[] {
  const errors: string[] = [];

  if (!artifact.baseCode || Object.keys(artifact.baseCode).length === 0) errors.push("base_code فارغ");
  if (!artifact.verificationTest || !artifact.verificationTest.trim()) errors.push("verification_test فارغ");
  if (!artifact.patchedCode || Object.keys(artifact.patchedCode).length === 0) errors.push("patched_code فارغ");

  if (Object.keys(artifact.baseCode).length < blueprint.minFiles) {
    errors.push(`عدد ملفات base_code ${Object.keys(artifact.baseCode).length} أقل من ${blueprint.minFiles}`);
  }

  const baseKeys = new Set(Object.keys(artifact.baseCode));
  const patchedKeys = new Set(Object.keys(artifact.patchedCode));
  if (baseKeys.size !== patchedKeys.size || [...baseKeys].some((k) => !patchedKeys.has(k))) {
    errors.push("مسارات patched_code لا تطابق مسارات base_code — يجب إصلاح نفس الملفات بالضبط");
  }

  const testMarkers = ["assert ", "pytest", "def test_"];
  if (!testMarkers.some((m) => artifact.verificationTest.includes(m))) {
    errors.push("verification_test لا يحتوي علامات اختبار حقيقية (assert/pytest)");
  }

  const joinedAll = [
    ...Object.values(artifact.baseCode),
    artifact.verificationTest,
    ...Object.values(artifact.patchedCode),
  ]
    .join("\n")
    .toLowerCase();

  for (const token of ATTACK_TOKENS) {
    if (joinedAll.includes(token)) errors.push(`محتوى هجومي ممنوع مكتشف: '${token}' — هذا مولّد دفاعي فقط`);
  }

  for (const pattern of blueprint.forbiddenPatterns) {
    const needle = pattern.replace(/_/g, " ");
    if (joinedAll.includes(needle) || joinedAll.includes(pattern)) {
      errors.push(`نمط ممنوع مكتشف: ${pattern}`);
    }
  }

  if (blueprint.requiresAuthLayer) {
    const authMarkers = ["role", "permission", "authorize", "is_admin", "current_user"];
    if (!authMarkers.some((m) => joinedAll.includes(m))) {
      errors.push("المستوى يتطلب طبقة أدوار/صلاحيات ولم تُعثر عليها");
    }
  }

  const minRealFilesWithDeps = Object.values(artifact.baseCode).filter((content) =>
    ["import ", "require(", "from "].some((kw) => content.includes(kw))
  ).length;
  if (minRealFilesWithDeps < blueprint.minRealDependencies) {
    errors.push(`تبعيات حقيقية غير كافية: ${minRealFilesWithDeps} < ${blueprint.minRealDependencies}`);
  }

  return errors;
}

export function extractJson(raw: string): any {
  const match = raw.match(/\{[\s\S]*\}/);
  if (!match) throw new Error("لم يُعثر على JSON صالح في مخرج المزوّد");
  return JSON.parse(match[0]);
}
