"""وكيل التخطيط: يحوّل هدفاً إلى خطوات محدودة من أنواع مسموحة فقط (لا github أبداً)."""
import json

from ..response.generator import strip_think
from .base import Agent

ALLOWED = {"code", "files", "memory", "browse"}
PROMPT = """حوّل الهدف إلى خطوات تنفيذ. أجب بـ JSON فقط بالشكل:
{"steps":[{"kind":"code|files|memory|browse","payload":{...}}]}
- code: payload {"task": "وصف"}    - files: payload {"op":"read|write|list|search","path":"..."}
- browse: payload {"url":"..."}     - memory: payload {"op":"search","query":"..."}
لا تزد عن 6 خطوات ولا تكتب أي نص خارج JSON."""


def parse_steps(text, max_steps=8):
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        return []
    try:
        data = json.loads(text[a:b + 1])
    except ValueError:
        return []
    out = []
    for s in data.get("steps", []) if isinstance(data, dict) else []:
        if isinstance(s, dict) and s.get("kind") in ALLOWED and isinstance(s.get("payload", {}), dict):
            out.append({"kind": s["kind"], "payload": s.get("payload", {})})
    return out[:max_steps]


class PlannerAgent(Agent):
    name = "planner"

    def __init__(self, llm, max_steps=8):
        self.llm, self.max_steps = llm, max_steps

    async def handle(self, kind, payload, ctx):
        goal = str(payload.get("goal", ""))[:2000]
        out = await self.llm.achat([{"role": "system", "content": PROMPT},
                                    {"role": "user", "content": goal}], max_tokens=600, temperature=0.2)
        steps = parse_steps(strip_think(out["content"]), self.max_steps)
        return {"steps": steps, "note": "" if steps else "لم يُنتج خطة صالحة"}
