// railway.ts — ترجمة _send_to_railway من e2b_agent_runner.py

import type { Env } from "./types";

const DEFAULT_URL = "https://marsad-sandbox-production.up.railway.app/api/ingest";

export async function sendToRailway(env: Env, agentId: string, payload: unknown): Promise<any> {
  const url = env.RAILWAY_INGEST_URL || DEFAULT_URL;
  try {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ agent_id: agentId, payload }),
    });
    try {
      return await resp.json();
    } catch {
      const text = await resp.text();
      return { status: "error", message: `استجابة غير JSON (${resp.status}): ${text.slice(0, 200)}` };
    }
  } catch (e: any) {
    return { status: "error", message: `تعذّر الاتصال بـ Railway: ${e?.message ?? e}` };
  }
}
