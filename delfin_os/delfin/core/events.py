"""ناقل الأحداث: Events (أطلق وانسَ)، Signals (طلب/رد)، Hooks (معترِضات)."""
import asyncio
from collections import defaultdict, deque


class EventBus:
    def __init__(self):
        self._subs = defaultdict(list)
        self._hooks = []
        self._signals = {}
        self.dead_letters = deque(maxlen=200)
        self.log = deque(maxlen=500)

    def subscribe(self, topic, handler):
        self._subs[topic].append(handler)

    def hook(self, fn):
        """fn(topic, payload) -> payload معدَّل، أو None لإسقاط الحدث."""
        self._hooks.append(fn)

    def register_signal(self, name, handler):
        self._signals[name] = handler

    async def publish(self, topic, payload):
        for h in self._hooks:
            payload = h(topic, payload)
            if payload is None:
                self.log.append((topic, "dropped"))
                return False
        self.log.append((topic, "ok"))
        for handler in list(self._subs.get(topic, [])) + list(self._subs.get("*", [])):
            try:
                r = handler(topic, payload)
                if asyncio.iscoroutine(r):
                    await r
            except Exception as e:  # معالج معطوب لا يوقف الناقل
                self.dead_letters.append({"topic": topic, "error": str(e)[:200]})
        return True

    async def request(self, name, payload, timeout=10):
        if name not in self._signals:
            raise KeyError(f"إشارة غير معروفة: {name}")
        r = self._signals[name](payload)
        if asyncio.iscoroutine(r):
            r = await asyncio.wait_for(r, timeout)
        return r
