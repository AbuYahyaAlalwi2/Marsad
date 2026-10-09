// providers.ts — ترجمة مباشرة لمزوّدي deepseek_adapter.py الخمسة (بعد إضافة
// Groq)، بنفس الترتيب وبنفس منطق المحاولات (محاولتان لكل مزوّد قبل الانتقال
// للتالي). كل مزوّد هنا لا يعتمد على أي شيء خاص ببايثون — fetch فقط.

import type { Env } from "./types";

export interface BuildProvider {
  name: string;
  available(env: Env): boolean;
  generateProject(env: Env, systemPrompt: string, userPrompt: string): Promise<string>;
}

const TIMEOUT_MS = 120_000;

async function fetchWithTimeout(url: string, init: RequestInit, timeoutMs = TIMEOUT_MS): Promise<Response> {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(id);
  }
}

export const DeepSeekProvider: BuildProvider = {
  name: "deepseek",
  available: (env) => !!env.DEEPSEEK_API_KEY,
  async generateProject(env, systemPrompt, userPrompt) {
    const resp = await fetchWithTimeout("https://api.deepseek.com/chat/completions", {
      method: "POST",
      headers: { Authorization: `Bearer ${env.DEEPSEEK_API_KEY}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "deepseek-coder",
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: userPrompt },
        ],
        temperature: 0.3,
        max_tokens: 8192,
        response_format: { type: "json_object" },
      }),
    });
    if (!resp.ok) throw new Error(`deepseek HTTP ${resp.status}: ${await resp.text()}`);
    const data: any = await resp.json();
    return data.choices[0].message.content as string;
  },
};

export const GroqProvider: BuildProvider = {
  name: "groq",
  available: (env) => !!env.GROQ_API_KEY,
  async generateProject(env, systemPrompt, userPrompt) {
    const resp = await fetchWithTimeout("https://api.groq.com/openai/v1/chat/completions", {
      method: "POST",
      headers: { Authorization: `Bearer ${env.GROQ_API_KEY}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "llama-3.3-70b-versatile",
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: userPrompt },
        ],
        temperature: 0.3,
        max_tokens: 8192,
      }),
    });
    if (!resp.ok) throw new Error(`groq HTTP ${resp.status}: ${await resp.text()}`);
    const data: any = await resp.json();
    return data.choices[0].message.content as string;
  },
};

export const OpenRouterProvider: BuildProvider = {
  name: "openrouter",
  available: (env) => !!env.OPENROUTER_API_KEY,
  async generateProject(env, systemPrompt, userPrompt) {
    const resp = await fetchWithTimeout("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: { Authorization: `Bearer ${env.OPENROUTER_API_KEY}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "qwen/qwen-2.5-coder-32b-instruct",
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: userPrompt },
        ],
        temperature: 0.3,
        max_tokens: 8192,
      }),
    });
    if (!resp.ok) throw new Error(`openrouter HTTP ${resp.status}: ${await resp.text()}`);
    const data: any = await resp.json();
    return data.choices[0].message.content as string;
  },
};

export const GeminiProvider: BuildProvider = {
  name: "gemini",
  available: (env) => !!env.GOOGLE_API_KEY,
  async generateProject(env, systemPrompt, userPrompt) {
    const resp = await fetchWithTimeout(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key=${env.GOOGLE_API_KEY}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          contents: [{ parts: [{ text: `${systemPrompt}\n\n${userPrompt}` }] }],
          generationConfig: { temperature: 0.3, maxOutputTokens: 8192 },
        }),
      }
    );
    if (!resp.ok) throw new Error(`gemini HTTP ${resp.status}: ${await resp.text()}`);
    const data: any = await resp.json();
    return data.candidates[0].content.parts[0].text as string;
  },
};

export const HFInferenceProvider: BuildProvider = {
  name: "huggingface",
  available: (env) => !!env.HF_API_KEY,
  async generateProject(env, systemPrompt, userPrompt) {
    const resp = await fetchWithTimeout(
      "https://api-inference.huggingface.co/models/Qwen/Qwen2.5-Coder-32B-Instruct",
      {
        method: "POST",
        headers: { Authorization: `Bearer ${env.HF_API_KEY}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          inputs: `${systemPrompt}\n\n${userPrompt}`,
          parameters: { temperature: 0.3, max_new_tokens: 8192 },
        }),
      },
      180_000
    );
    if (!resp.ok) throw new Error(`huggingface HTTP ${resp.status}: ${await resp.text()}`);
    const data: any = await resp.json();
    return Array.isArray(data) ? data[0].generated_text : data.generated_text ?? "";
  },
};

// نفس ترتيب المحاولة في marsad_combined.py بعد إضافة Groq
export const DEFAULT_PROVIDERS: BuildProvider[] = [
  DeepSeekProvider,
  GroqProvider,
  OpenRouterProvider,
  GeminiProvider,
  HFInferenceProvider,
];
