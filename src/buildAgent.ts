// buildAgent.ts — ترجمة AutoBuildAgent من deepseek_adapter.py: يجرّب كل
// مزوّد متاح بالترتيب، محاولتان لكل واحد، يرفض عبر BuildRejected لو فشل الجميع.

import { DEFAULT_PROVIDERS } from "./providers";
import { extractJson, validateArtifact } from "./validator";
import type { Env, ProjectArtifact, ScenarioBlueprint } from "./types";

export class BuildRejected extends Error {}

function systemPrompt(bp: ScenarioBlueprint): string {
  return (
    "أنت مولّد بيانات تدريبية دفاعية لصحّة البرمجيات (software correctness). هذا ليس أمن هجومي " +
    "ولا تدريب اختراق — المطلوب فقط توضيح خطأ منطقي برمجي شائع عبر اختبار يفشل ثم ينجح بعد الإصلاح. " +
    "ممنوع منعاً باتاً أي exploit code أو payload أو محاولة اختراق فعلية أو أي نص يصف تنفيذ هجوم.\n\n" +
    `- عدد ملفات base_code: ${bp.minFiles} ملفاً حقيقياً على الأقل.\n` +
    `- عدد التبعيات الحقيقية (import/require فعلي): ${bp.minRealDependencies} على الأقل.\n` +
    `- طبقة أدوار/صلاحيات حقيقية مطلوبة: ${bp.requiresAuthLayer ? "نعم" : "لا"}.\n` +
    `- الخطأ يتطلب اجتماع أكثر من شرط منطقي: ${bp.requiresMultiStepDefect ? "نعم" : "لا"}.\n` +
    `- الأنماط الممنوعة تماماً: ${bp.forbiddenPatterns.join(", ")}.\n\n` +
    "أرجع الناتج **فقط** كـ JSON خالص بهذا الشكل بالضبط، بلا أي نص خارج الـ JSON:\n" +
    "{\n" +
    '  "base_code": {"path/to/file.py": "...محتوى يحتوي الخطأ المنطقي..."},\n' +
    '  "verification_test": "...محتوى ملف pytest واحد، يجب أن يفشل ضد base_code...",\n' +
    '  "patched_code": {"path/to/file.py": "...نفس المسار بعد إصلاح الخطأ فقط..."}\n' +
    "}"
  );
}

export async function buildArtifact(env: Env, blueprint: ScenarioBlueprint, step: (m: string) => void): Promise<ProjectArtifact> {
  const userPrompt = blueprint.narrativeBrief;
  const sys = systemPrompt(blueprint);
  const failures: string[] = [];

  for (const provider of DEFAULT_PROVIDERS) {
    if (!provider.available(env)) continue;

    for (let attempt = 1; attempt <= 2; attempt++) {
      try {
        step(`استدعاء ${provider.name} (محاولة ${attempt})`);
        const raw = await provider.generateProject(env, sys, userPrompt);
        const parsed = extractJson(raw);
        if (typeof parsed !== "object" || parsed === null) throw new Error("الناتج ليس كائن JSON");

        const artifact: ProjectArtifact = {
          scenarioId: blueprint.scenarioId,
          providerUsed: provider.name,
          baseCode: parsed.base_code ?? {},
          verificationTest: parsed.verification_test ?? "",
          patchedCode: parsed.patched_code ?? {},
          rawResponseChars: raw.length,
        };

        const errors = validateArtifact(artifact, blueprint);
        if (errors.length === 0) return artifact;

        failures.push(`${provider.name} (محاولة ${attempt}): ${errors.join("; ")}`);
      } catch (exc: any) {
        failures.push(`${provider.name} (محاولة ${attempt}): خطأ تقني — ${exc?.message ?? exc}`);
      }
    }
  }

  throw new BuildRejected(
    `فشل بناء سيناريو ${blueprint.scenarioId} عبر كل المزودين المتاحين:\n${failures.join("\n")}`
  );
}
