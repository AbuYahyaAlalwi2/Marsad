"""التعافي من الأخطاء: إعادة محاولة أُسّية + قاطع دائرة."""
import asyncio
import time

from .errors import BudgetExceeded, ResourceExhausted, SecurityError

NO_RETRY = (SecurityError, BudgetExceeded, ResourceExhausted, asyncio.CancelledError)


async def retry_async(fn, max_retries=1, base=0.5, sleep=asyncio.sleep):
    attempt = 0
    while True:
        try:
            return await fn()
        except NO_RETRY:
            raise
        except Exception:
            if attempt >= max_retries:
                raise
            await sleep(base * (2 ** attempt))
            attempt += 1


class CircuitBreaker:
    """بعد threshold إخفاقات متتالية يفتح الدائرة مدة cooldown ثانية."""

    def __init__(self, threshold=5, cooldown=30.0, clock=time.monotonic):
        self.threshold, self.cooldown, self.clock = threshold, cooldown, clock
        self.failures = 0
        self.opened_at = None

    def allow(self):
        if self.opened_at is None:
            return True
        if self.clock() - self.opened_at >= self.cooldown:
            self.opened_at, self.failures = None, self.threshold - 1  # نصف مفتوحة
            return True
        return False

    def record(self, ok):
        if ok:
            self.failures, self.opened_at = 0, None
        else:
            self.failures += 1
            if self.failures >= self.threshold:
                self.opened_at = self.clock()
