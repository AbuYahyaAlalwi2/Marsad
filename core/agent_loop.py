"""
agent_loop.py — حلقة الوكيل الكاملة.
- يتصل بنموذج (llama.cpp / OpenAI-compatible)
- يستخدم tool_calling لتنفيذ الأدوات
- متعدد الجولات (multi-turn)
- جاهز للربط بتليجرام
"""
from __future__ import annotations
import os, json, time, logging
from typing import List, Dict, Any, Optional
from pathlib import Path

import httpx

from core.tool_calling import registry, parse_and_execute

try:
    from core.instincts import to_prompt_block as _instincts_block
except Exception:
    _instincts_block = None

try:
    from core.skill_loader import loader as skill_loader
except Exception:
    skill_loader = None

try:
    from core.memory_vault import MemoryVault
except Exception:
    MemoryVault = None


logger = logging.getLogger(__name__)

# ─── إعداد النموذج (OpenAI-compatible) ──────────────────────
BASE_URL = os.environ.get("MARSAD_LLM_URL", "http://localhost:8080/v1")
MODEL = os.environ.get("MARSAD_LLM_MODEL", "deepseek-marsad-v2")
API_KEY = os.environ.get("MARSAD_LLM_KEY", "not-needed")

MAX_TURNS = int(os.environ.get("MARSAD_AGENT_TURNS", "8"))

SYSTEM = """أنت Marsad Agent. نفّذ ولا تشرح.

عندما تحتاج أداة، اخرج فقط بهذا الشكل (بدون ```):
<tool_call>{"name":"اسم_الأداة","arguments":{"مفتاح":"قيمة"}}</tool_call>

قواعد صارمة:
1. لا تستخدم ```python``` أبداً
2. لا تشرح خطواتك
3. لا تكتب "سأستخدم" أو "دعنا"
4. بعد نتيجة الأداة، إن انتهت المهمة اكتب إجابتك النهائية فقط (بدون أدوات)
5. الأدوات المتاحة: run_python, run_shell, read_file, write_file, cve_lookup, threat_summary, generate_pdf_report, http_get
"""


class AgentLoop:
    def __init__(self, base_url: str = BASE_URL, model: str = MODEL,
                 api_key: str = API_KEY, max_turns: int = MAX_TURNS):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.max_turns = max_turns

    # ─── استدعاء النموذج ─────────────────────────────────
    def _chat(self, messages):
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key and self.api_key != "not-needed":
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 1024,
            "stream": False,
        }
        try:
            r = httpx.post(url, json=payload, headers=headers, timeout=180)
            r.raise_for_status()
            return r.json()["choices"][0]["message"].get("content", "") or ""
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"LLM HTTP {e.response.status_code}: {e.response.text[:200]}")
        except httpx.RequestError as e:
            raise RuntimeError(f"LLM unreachable: {e}")

    # ─── الحلقة الرئيسية ─────────────────────────────────
    def run(self, user_request: str,
            on_step=None) -> Dict[str, Any]:
        """ينفذ الطلب عبر multi-turn tool-calling."""

        def _log(msg):
            logger.info(msg)
            if on_step: on_step(msg)
            else: print(msg)

        # حقن المهارات المطابقة
        skill_ctx = ""
        if skill_loader:
            try:
                skill_ctx = skill_loader.load_context_for(user_request)
            except Exception:
                pass

        system_msg = SYSTEM

        # حقن القواعد الدائمة
        if _instincts_block:
            try:
                system_msg += f"\n\n{_instincts_block()}"
            except Exception:
                pass

        if skill_ctx:
            system_msg += f"\n\n{skill_ctx}"

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_request},
        ]

        history = []
        final_text = ""

        for turn in range(1, self.max_turns + 1):
            _log(f"◬ turn {turn}/{self.max_turns}")
            try:
                response = self._chat(messages)
            except Exception as e:
                return {"status": "llm_error", "error": str(e), "history": history}

            messages.append({"role": "assistant", "content": response})
            _log(f"⊞ نموذج: {response[:150]}")

            # نفّذ tool_calls
            results = parse_and_execute(response)
            if results:
                for r in results:
                    tool_result = json.dumps(r.get("result", r), ensure_ascii=False)[:1500]
                    messages.append({
                        "role": "user",
                        "content": f"نتيجة الأداة:\n{tool_result}"
                    })
                    history.append({"turn": turn, **r})
                continue

            # إجابة نهائية
            final_text = response
            break

        return {
            "status": "completed",
            "final": final_text,
            "turns": len(history),
            "history": history,
        }


# ─── Helper ─────────────────────────────────────────────────
_default_agent = None

def get_agent() -> AgentLoop:
    global _default_agent
    if _default_agent is None:
        _default_agent = AgentLoop()
    return _default_agent


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 2:
        print("usage: agent_loop.py '<طلب>'")
        sys.exit(1)
    agent = get_agent()
    result = agent.run(" ".join(sys.argv[1:]))
    print()
    print("=" * 50)
    print("النتيجة:", result["status"])
    print("الجولات:", result.get("turns"))
    print("الإجابة:", result.get("final", result.get("error"))[:500])
