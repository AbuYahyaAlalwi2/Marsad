"""وكيل المحادثة: يجمع الشخصية والذاكرة والتوكن والرد المنظَّف."""
from ..core.errors import SecurityError
from .base import Agent


class ChatAgent(Agent):
    name = "assistant"

    def __init__(self, llm, memory, personas, responses, tokens, canary=None, company_context=""):
        self.llm, self.memory, self.personas = llm, memory, personas
        self.responses, self.tokens = responses, tokens
        self.canary, self.company = canary, company_context

    async def handle(self, kind, payload, ctx):
        owner, sid = ctx["owner"], payload.get("session", "")
        sess = self.memory.get_session(sid, owner)          # عزل المالك
        msg = str(payload.get("message", ""))
        persona = self.personas.get(payload.get("persona") or sess["persona"])
        self.tokens.check_before(sid, self.tokens.estimate(msg) + 400)
        emotion = self.personas.detect_emotion(msg)
        system = self.personas.system_prompt(persona, self.canary, self.company,
                                             self.memory.prefs(sid, persona.name), emotion)
        messages = [{"role": "system", "content": system}] + self.memory.context(sid) + \
                   [{"role": "user", "content": msg}]
        out = await self.llm.achat(messages, max_tokens=self.tokens.max_tokens(512))
        reply = self.responses.finalize(out["content"], persona)
        self.memory.add(sid, "user", msg)
        self.memory.add(sid, "assistant", reply["text"])
        u = out["usage"]
        status = self.tokens.charge(sid, owner, u["prompt_tokens"], u["completion_tokens"])
        return {"reply": reply["text"], "flags": reply["flags"], "emotion": emotion,
                "tokens": status, "_tokens_used": u["prompt_tokens"] + u["completion_tokens"]}
