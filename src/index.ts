// index.ts — نقطة الدخول. Cron Trigger يستدعي scheduled() كل دقيقة (راجع
// wrangler.toml)، وكل استدعاء = دورة واحدة بالضبط (توليد -> بناء -> نشر E2B
// -> اختبار قبل/بعد -> إرسال Railway) — نفس منطق run_one_cycle في
// e2b_agent_runner.py، لكن بلا أي حلقة while داخلية: الجدولة الخارجية
// (Cron) هي ما يحقق "الاستمرارية"، لا عملية واحدة طويلة العمر. هذا بالضبط
// ما يجعلها متوافقة مع طريقة عمل Cloudflare Workers ولا يخالف أي سياسة
// استخدام، بعكس تشغيل حلقة بلا نهاية على Kaggle.

import { generateScenario } from "./scenarioGenerator";
import { BuildRejected, buildArtifact } from "./buildAgent";
import { deployProject, runFullRound, teardown } from "./sandbox";
import { recordOutcome } from "./escalator";
import { sendToRailway } from "./railway";
import type { Env } from "./types";

const AGENT_ID = "marsad_main_agent";

function step(label: string) {
  console.log(`[${new Date().toISOString()}] ${label}`);
}

async function runOneCycle(env: Env): Promise<void> {
  step("بدء: توليد السيناريو");
  const blueprint = await generateScenario(env, AGENT_ID);
  step(`تم توليد السيناريو ${blueprint.scenarioId} (tier=${blueprint.tier}) — بدء البناء`);

  let artifact;
  try {
    artifact = await buildArtifact(env, blueprint, step);
  } catch (e) {
    if (e instanceof BuildRejected) {
      step(`رُفض البناء: ${e.message.slice(0, 300)}`);
      return;
    }
    throw e;
  }

  step(`تم البناء عبر ${artifact.providerUsed} — بدء نشر E2B sandbox`);
  const handle = await deployProject(env, artifact, blueprint.scenarioId);
  step(`sandbox جاهز (${handle.sandboxId}) — بدء الاختبار قبل/بعد الإصلاح`);

  let roundData;
  try {
    roundData = await runFullRound(handle, artifact, blueprint.defectClass);
  } finally {
    await teardown(handle);
  }
  step(`انتهى الاختبار — defect_confirmed=${roundData.defect_confirmed} fix_verified=${roundData.fix_verified}`);

  await recordOutcome(env, AGENT_ID, roundData.defect_confirmed, roundData.fix_verified);

  step("بدء الإرسال لـ Railway");
  const railwayResponse = await sendToRailway(env, AGENT_ID, roundData);
  step(`انتهى: railway=${JSON.stringify(railwayResponse)}`);
}

export default {
  // تشغيل يدوي اختياري عبر GET (للتجربة أثناء wrangler dev أو فحص يدوي سريع)
  async fetch(_req: Request, env: Env): Promise<Response> {
    try {
      await runOneCycle(env);
      return new Response("تم تنفيذ دورة واحدة — راجع wrangler tail للتفاصيل\n", { status: 200 });
    } catch (e: any) {
      return new Response(`خطأ غير متوقع: ${e?.message ?? e}\n`, { status: 500 });
    }
  },

  // الاستدعاء الحقيقي الدائم — Cron Trigger (كل دقيقة حسب wrangler.toml)
  async scheduled(_event: ScheduledEvent, env: Env, ctx: ExecutionContext): Promise<void> {
    ctx.waitUntil(
      runOneCycle(env).catch((e) => {
        console.error(`خطأ غير متوقع في الدورة: ${e?.message ?? e}`);
      })
    );
  },
};
