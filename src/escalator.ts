// escalator.ts — ترجمة ComplexityEscalator من scenario_generator.py.
// الفرق الوحيد عن النسخة البايثونية: Workers عديمة الحالة بين كل استدعاء Cron،
// لذا نخزّن AgentProgress في Cloudflare KV بدل قاموس في الذاكرة.

import { AgentProgress, Env, MAX_TIER } from "./types";

const PROMOTE_AFTER = 2;
const KV_KEY_PREFIX = "progress:";

function defaultProgress(agentId: string): AgentProgress {
  return { agentId, tier: 1, consecutiveSuccesses: 0, consecutiveFailures: 0, totalRounds: 0 };
}

export async function currentTier(env: Env, agentId: string): Promise<number> {
  const p = await loadProgress(env, agentId);
  return p.tier;
}

export async function loadProgress(env: Env, agentId: string): Promise<AgentProgress> {
  const raw = await env.MARSAD_KV.get(KV_KEY_PREFIX + agentId);
  if (!raw) return defaultProgress(agentId);
  try {
    return JSON.parse(raw) as AgentProgress;
  } catch {
    return defaultProgress(agentId);
  }
}

export async function recordOutcome(
  env: Env,
  agentId: string,
  defectConfirmed: boolean,
  fixVerified: boolean
): Promise<AgentProgress> {
  const p = await loadProgress(env, agentId);
  p.totalRounds += 1;

  const fullSuccess = defectConfirmed && fixVerified;
  if (fullSuccess) {
    p.consecutiveSuccesses += 1;
    p.consecutiveFailures = 0;
    if (p.consecutiveSuccesses >= PROMOTE_AFTER && p.tier < MAX_TIER) {
      p.tier += 1;
      p.consecutiveSuccesses = 0;
    }
  } else {
    p.consecutiveFailures += 1;
    p.consecutiveSuccesses = 0;
  }

  await env.MARSAD_KV.put(KV_KEY_PREFIX + agentId, JSON.stringify(p));
  return p;
}
