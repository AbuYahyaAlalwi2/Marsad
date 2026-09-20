"""Explicit executor.

This module does not pretend that arbitrary natural-language text was executed.
Only registered, implemented handlers may perform work.
"""
import time
from db import log_event


class Executor:
    def __init__(self):
        self.execution_count = 0
        self.failed_count = 0
        log_event("executor", {"status": "initialized", "mode": "explicit_handlers_only"})

    def execute(self, command: str, context: dict = None) -> dict:
        self.execution_count += 1
        if not isinstance(command, str) or not command.strip():
            self.failed_count += 1
            return {"status": "error", "reason": "command_must_be_text"}
        self.failed_count += 1
        log_event("executor", {"mode": "not_implemented", "command_preview": command[:100]})
        return {
            "status": "not_configured",
            "mode": "no_handler",
            "command": command,
            "message": "لا يوجد منفذ حقيقي مسجل لهذا الأمر؛ لم يتم ادعاء التنفيذ.",
            "timestamp": time.time(),
        }

    def get_stats(self):
        return {
            "total_executions": self.execution_count,
            "completed_executions": 0,
            "failed_or_unconfigured": self.failed_count,
        }


executor = Executor()
