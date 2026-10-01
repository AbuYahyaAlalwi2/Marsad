"""متحكم الموارد: حد معدل لكل وكيل، عدّاد توكن، وضع الأمان عند الاقتراب من الحد."""
import time
from collections import defaultdict, deque

from .errors import ResourceExhausted


class ResourceController:
    def __init__(self, per_agent_per_minute=30, token_ceiling=None, clock=time.monotonic):
        self.limit, self.ceiling, self.clock = per_agent_per_minute, token_ceiling, clock
        self._hits = defaultdict(deque)
        self.tokens_used = 0
        self.api_calls = 0

    @property
    def failsafe(self):
        return bool(self.ceiling) and self.tokens_used / self.ceiling >= 0.9

    def check(self, agent, priority=3):
        now = self.clock()
        q = self._hits[agent]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= self.limit:
            raise ResourceExhausted(f"تجاوز الوكيل {agent} حد المعدل")
        if self.failsafe and priority > 3:
            raise ResourceExhausted("وضع الأمان: تُقبل المهام العاجلة فقط")
        q.append(now)
        self.api_calls += 1

    def add_tokens(self, n):
        self.tokens_used += int(n)

    def snapshot(self):
        return {"tokens_used": self.tokens_used, "api_calls": self.api_calls, "failsafe": self.failsafe}
