"""وكيل الذاكرة: واجهة المهام إلى محرك الذاكرة (مع عزل المالك)."""
from ..core.errors import SecurityError
from .base import Agent


class MemoryAgent(Agent):
    name = "memory"

    def __init__(self, memory):
        self.memory = memory

    async def handle(self, kind, payload, ctx):
        sid, op = payload.get("session", ""), payload.get("op")
        self.memory.get_session(sid, ctx["owner"])
        if op == "add":
            return self.memory.add(sid, "note", payload.get("content", ""), payload.get("importance", 3))
        if op == "search":
            return {"results": self.memory.search(sid, payload.get("query", ""))}
        if op == "context":
            return {"context": self.memory.context(sid)}
        if op == "compress":
            return {"compressed": self.memory.compress(sid)}
        raise SecurityError("عملية ذاكرة غير معروفة")
