"""
نظام الخطافات — مرونة كاملة
"""
import time
from db import log_event

class HookSystem:
    """
    نظام خطافات في كل نقطة:
    - pre_collect, post_collect
    - pre_clean, post_clean
    - pre_merge, post_merge
    - pre_execute, post_execute
    """

    def __init__(self):
        self.hooks = {}

        self.register("pre_execute", self._default_pre_execute)
        self.register("post_execute", self._default_post_execute)

        log_event("hooks", {"status": "initialized"})

    def register(self, event: str, callback):
        """تسجيل خطاف"""
        if event not in self.hooks:
            self.hooks[event] = []
        self.hooks[event].append(callback)

        log_event("hooks", {"registered": event, "callback": callback.__name__})

    def trigger(self, event: str, data: dict) -> dict:
        """تفعيل الخطافات"""
        if event not in self.hooks:
            return data

        for callback in self.hooks[event]:
            result = callback(data)

            if result is None:
                log_event("hooks", {"event": event, "action": "stopped"})
                return None

            if isinstance(result, dict):
                data = result

        return data

    def _default_pre_execute(self, data: dict) -> dict:
        data["pre_execute_timestamp"] = time.time()
        return data

    def _default_post_execute(self, data: dict) -> dict:
        data["post_execute_timestamp"] = time.time()
        return data

hooks = HookSystem()
