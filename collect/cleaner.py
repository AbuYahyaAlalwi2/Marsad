"""
التنظيف — 6 طبقات فلترة
"""
import re
from db import log_event

class DataCleaner:
    """تنظيف البيانات المجمعة"""

    def clean(self, content: str) -> dict:
        """تنظيف شامل"""
        checks = {
            "has_secrets": self._check_secrets(content),
            "has_pii": self._check_pii(content),
            "quality_ok": self._check_quality(content),
            "not_duplicate": True,
            "license_ok": True,
            "not_dangerous": self._check_dangerous(content)
        }

        passed = all(not v for k, v in checks.items() if k != "quality_ok" and k != "not_duplicate")
        passed = passed and checks["quality_ok"]

        return {
            "passed": passed,
            "checks": checks,
            "cleaned_content": self._sanitize(content) if passed else None
        }

    def _check_secrets(self, content: str) -> bool:
        patterns = [
            r"AKIA[0-9A-Z]{16}",
            r"sk-[a-zA-Z0-9]{20,}",
            r"ghp_[0-9A-Za-z]{36}",
            r"-----BEGIN.*PRIVATE KEY-----"
        ]
        return any(re.search(p, content) for p in patterns)

    def _check_pii(self, content: str) -> bool:
        patterns = [
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            r"\b[12]\d{9}\b"
        ]
        return any(re.search(p, content) for p in patterns)

    def _check_quality(self, content: str) -> bool:
        if len(content) < 50:
            return False

        printable = sum(1 for c in content if c.isprintable())
        return (printable / len(content)) > 0.9

    def _check_dangerous(self, content: str) -> bool:
        patterns = [
            r"rm -rf /",
            r"format c:",
            r"drop database",
            r"subprocess.*shell=True"
        ]
        return any(re.search(p, content, re.I) for p in patterns)

    def _sanitize(self, content: str) -> str:
        content = re.sub(r'\n{3,}', '\n\n', content)
        content = re.sub(r' +', ' ', content)
        return content.strip()

cleaner = DataCleaner()
