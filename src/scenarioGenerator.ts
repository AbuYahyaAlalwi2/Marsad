// scenarioGenerator.ts — ترجمة مباشرة لـ ScenarioGenerator._brief من
// scenario_generator.py، بنفس القواعد والنص بالضبط.

import {
  DefectClass,
  FORBIDDEN_PATTERNS,
  LOGIC_DEFECT_CLASSES,
  ScenarioBlueprint,
  TECH_STACKS,
  TIER_MIN_DEPS,
  TIER_MIN_FILES,
  tierRequiresAuthLayer,
  tierRequiresMultiStepDefect,
} from "./types";
import { currentTier } from "./escalator";
import type { Env } from "./types";

function pick<T>(arr: readonly T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

async function sha256Hex12(input: string): Promise<string> {
  const data = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest("SHA-256", data);
  const hex = [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
  return hex.slice(0, 12);
}

function brief(tier: number, defectClass: DefectClass, stack: [string, string, string]): string {
  const [lang, framework, datastore] = stack;
  let base =
    `اكتب برنامجاً صغيراً وحقيقياً بلغة ${lang} (إطار ${framework}، تخزين ${datastore} إن لزم)، ` +
    `يحتوي خطأً منطقياً واحداً من فئة '${defectClass}' — خطأ في التدفق البرمجي ` +
    `(مثال نمطي: غياب التحقق من دور المستخدم قبل تنفيذ دالة حساسة)، وليس أي كود هجوم أو payload. ` +
    `ممنوع منعاً باتاً أي exploit code أو payload ضار أو محاولة اختراق فعلية — المطلوب فقط خطأ ` +
    `منطقي في شرط أو تحقق ناقص.\n\n` +
    `أرجع بالضبط ثلاثة مكونات:\n` +
    `1) الكود الأساسي (base_code) الذي يحتوي الخطأ.\n` +
    `2) اختبار تحقق (verification_test) بصيغة pytest/assert بسيطة، يجب أن يفشل ` +
    `(AssertionError) عند تشغيله ضد الكود الأساسي — هذا ما يثبت وجود الخطأ منطقياً.\n` +
    `3) الكود المُصحَّح (patched_code): نفس الكود الأساسي بعد إضافة الفحص/الشرط الناقص فقط، ` +
    `بحيث ينجح نفس اختبار التحقق عند تشغيله ضده.\n`;

  if (tierRequiresAuthLayer(tier)) {
    base += "يجب أن يملك البرنامج طبقة مصادقة/أدوار حقيقية بسيطة بين نوعين من المستخدمين على الأقل.\n";
  }
  if (tierRequiresMultiStepDefect(tier)) {
    base +=
      "الخطأ يجب ألا يظهر إلا عند اجتماع أكثر من شرط منطقي معاً (مثال: الدور صحيح لكن حالة " +
      "الكائن قديمة)، لا خطأ مباشر في سطر واحد معزول.\n";
  }
  return base;
}

export async function generateScenario(env: Env, agentId: string): Promise<ScenarioBlueprint> {
  const tier = await currentTier(env, agentId);
  const defectClass = pick(LOGIC_DEFECT_CLASSES);
  const stack = pick(TECH_STACKS);

  const scenarioId = await sha256Hex12(`${agentId}:${tier}:${defectClass}:${new Date().toISOString()}`);

  const blueprint: ScenarioBlueprint = {
    scenarioId,
    tier,
    defectClass,
    stack,
    minFiles: TIER_MIN_FILES[tier],
    minRealDependencies: TIER_MIN_DEPS[tier],
    requiresAuthLayer: tierRequiresAuthLayer(tier),
    requiresMultiStepDefect: tierRequiresMultiStepDefect(tier),
    narrativeBrief: brief(tier, defectClass, stack),
    forbiddenPatterns: [...FORBIDDEN_PATTERNS],
  };

  return blueprint;
}
