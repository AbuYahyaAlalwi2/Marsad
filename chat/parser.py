"""
محلل الأوامر — فهم نية المستخدم
"""
import re
from db import log_event

class CommandParser:
    """تحليل أوامر المستخدم"""

    def __init__(self):
        self.patterns = {
            "collect": r"(اجمع|collect|gather|fetch)",
            "analyze": r"(حلل|analyze|analysis|فحص)",
            "generate": r"(ولد|generate|create|أنشئ)",
            "merge": r"(اصهر|merge|combine|ادمج)",
            "deploy": r"(انشر|deploy|publish|ارفع)",
            "attack": r"(هاجم|attack|exploit|اخترق)",
            "defend": r"(دافع|defend|protect|احمي)",
            "train": r"(درّب|train|teach|علّم)",
        }

        log_event("parser", {"status": "initialized"})

    def parse(self, command: str) -> dict:
        """تحليل أمر"""
        command_lower = command.lower()

        command_type = "unknown"
        for ctype, pattern in self.patterns.items():
            if re.search(pattern, command_lower):
                command_type = ctype
                break

        language = "arabic" if any('\u0600' <= c <= '\u06FF' for c in command) else "english"

        params = self._extract_params(command)

        return {
            "type": command_type,
            "language": language,
            "params": params,
            "raw": command
        }

    def _extract_params(self, command: str) -> dict:
        """استخراج المعاملات"""
        params = {}

        numbers = re.findall(r'\d+', command)
        if numbers:
            params["count"] = int(numbers[0])

        platforms = ["github", "gitlab", "bitbucket", "huggingface", "stackoverflow"]
        for platform in platforms:
            if platform in command.lower():
                params["platform"] = platform
                break

        return params

parser = CommandParser()
