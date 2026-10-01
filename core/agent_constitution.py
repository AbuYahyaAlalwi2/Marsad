"""
دستور الوكلاء — البوابة القانونية والجودة
==========================================
يُنفَّذ قبل كل جولة Self-Play. يرفض أي مهمة مخالفة.

4 أقسام:
  1. LegalShieldGate — robots.txt + ToS + تراخيص
  2. DataQualityFilter — استبعاد الأكواد المصابة
  3. ExploitTriple — هيكل [قبل/استغلال/بعد]
  4. AuditLogger — سجل تدقيق
"""
from __future__ import annotations
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

AUDIT_LOG = Path.home() / "Marsad" / "logs" / "constitution_audit.jsonl"
AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class Decision:
    allowed: bool
    reason: str = ""
    article: str = ""  # اسم القسم المخالف


# ═══════════════════════════════════════════════════════
# القسم 1 — Legal Shield Gate
# ═══════════════════════════════════════════════════════
class LegalShieldGate:
    """يتحقق أن المصدر قانوني قبل السحب."""

    ALLOWED_LICENSES = {
        "MIT", "Apache-2.0", "Apache 2.0", "BSD", "BSD-3-Clause",
        "BSD-2-Clause", "ISC", "MPL-2.0", "CC0-1.0", "Unlicense",
        "GPL-3.0", "GPL-2.0", "LGPL-3.0",
    }
    FORBIDDEN_LICENSES = {
        "Proprietary", "All-Rights-Reserved", "Commercial-Only",
        "Research-Only", "Academic-Only",
    }
    # مستويات الحماية
    BLOCKED_DOMAINS = {
        "linkedin.com", "facebook.com", "twitter.com",
        "paywalled-research.com",  # أمثلة
    }

    @staticmethod
    def check_robots_txt(url: str) -> Decision:
        """يفحص robots.txt — إن كان محظوراً، يرفض."""
        try:
            from urllib.parse import urlparse
            from urllib.robotparser import RobotFileParser
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            rp = RobotFileParser()
            rp.set_url(robots_url)
            rp.read()
            allowed = rp.can_fetch("*", url)
            if not allowed:
                return Decision(False, f"robots.txt يحظر: {url}", "LegalShield/robots")
            return Decision(True, "", "LegalShield/robots")
        except Exception as e:
            # إذا فشل الفحص → نرفض (safety first)
            return Decision(False, f"تعذّر فحص robots: {e}", "LegalShield/robots")

    @staticmethod
    def check_license(license_name: str) -> Decision:
        """يتحقق أن الترخيص مسموح."""
        if not license_name:
            return Decision(False, "لا يوجد ترخيص", "LegalShield/license")
        name = license_name.strip()
        for forbidden in LegalShieldGate.FORBIDDEN_LICENSES:
            if forbidden.lower() in name.lower():
                return Decision(False, f"ترخيص محظور: {name}", "LegalShield/license")
        for allowed in LegalShieldGate.ALLOWED_LICENSES:
            if allowed.lower() in name.lower():
                return Decision(True, "", "LegalShield/license")
        # ترخيص غير معروف → نرفض
        return Decision(False, f"ترخيص غير معروف: {name}", "LegalShield/license")

    @staticmethod
    def check_domain(url: str) -> Decision:
        """يفحص النطاق — إن كان محظوراً، يرفض."""
        from urllib.parse import urlparse
        host = urlparse(url).netloc.lower()
        for blocked in LegalShieldGate.BLOCKED_DOMAINS:
            if blocked in host:
                return Decision(False, f"نطاق محظور: {host}", "LegalShield/domain")
        return Decision(True, "", "LegalShield/domain")


# ═══════════════════════════════════════════════════════
# القسم 2 — Data Quality Filter
# ═══════════════════════════════════════════════════════
class DataQualityFilter:
    """يفلتر جودة الأكواد المجمّعة."""

    # أنماط تشير لكود مصاب — نرفض
    INSECURE_PATTERNS = [
        (r"eval\s*\(", "استخدام eval"),
        (r"exec\s*\(", "استخدام exec"),
        (r"os\.system\s*\(", "os.system"),
        (r"subprocess\.call\s*\([^,]*shell\s*=\s*True", "shell=True"),
        (r"pickle\.loads?\s*\(", "pickle غير آمن"),
        (r"yaml\.load\s*\([^,)]*\)", "yaml.load بدون SafeLoader"),
        (r"md5\s*\(", "MD5 ضعيف"),
        (r"random\.random\s*\(", "random غير آمن"),
        (r"password\s*=\s*['\"][^'\"]+['\"]", "كلمة مرور صريحة"),
        (r"api[_-]?key\s*=\s*['\"][^'\"]+['\"]", "API key صريح"),
        (r"secret\s*=\s*['\"][^'\"]+['\"]", "secret صريح"),
        (r"aws_access_key", "AWS key"),
        (r"BEGIN RSA PRIVATE KEY", "مفتاح RSA"),
        (r"SELECT .* \+ .* FROM", "SQL injection محتمل"),
        (r"cursor\.execute\s*\([^,]*%\s*\(", "تنسيق SQL غير آمن"),
        (r"innerHTML\s*=", "XSS محتمل"),
        (r"document\.write\s*\(", "document.write"),
    ]

    @staticmethod
    def check_code(code: str) -> Decision:
        """يفحص الكود بحثاً عن ثغرات تعليمية."""
        if not code or len(code) < 20:
            return Decision(False, "كود قصير جداً", "Quality/empty")

        for pattern, desc in DataQualityFilter.INSECURE_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                return Decision(False, f"كود غير آمن: {desc}", "Quality/insecure")

        return Decision(True, "", "Quality/ok")

    @staticmethod
    def check_documentation(code: str, threshold: float = 0.02) -> Decision:
        """يتحقق أن الكود يحتوي تعليقات كافية."""
        lines = code.split("\n")
        if len(lines) < 5:
            return Decision(True, "", "Quality/docs")
        comments = [l for l in lines if l.strip().startswith("#") or '"""' in l]
        ratio = len(comments) / max(len(lines), 1)
        if ratio < threshold:
            return Decision(False, f"تعليقات قليلة: {ratio:.2%}", "Quality/docs")
        return Decision(True, "", "Quality/docs")

    @staticmethod
    def sanitize(code: str) -> str:
        """يستبدل البيانات الحقيقية بقيم وهمية."""
        # IPs
        code = re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
                      "127.0.0.1", code)
        # domains شائعة
        for real in ["google.com", "facebook.com", "microsoft.com"]:
            code = code.replace(real, "example.com")
        # emails
        code = re.sub(r"[\w\.-]+@[\w\.-]+\.\w+", "user@example.com", code)
        return code


# ═══════════════════════════════════════════════════════
# القسم 3 — Exploit Triple Structure
# ═══════════════════════════════════════════════════════
@dataclass
class ExploitTriple:
    """الهيكل الثلاثي الإلزامي لكل مهمة."""
    cve: str
    vulnerable_code: str     # [أ] قبل الإصلاح
    exploit_code: str        # [ب] استغلال مصنوع
    patch_code: str          # [ج] إصلاح

    def validate(self) -> Decision:
        """يتحقق أن الحقول الثلاثة كاملة."""
        if not self.cve:
            return Decision(False, "لا يوجد CVE", "ExploitTriple/cve")
        if not self.vulnerable_code or len(self.vulnerable_code) < 20:
            return Decision(False, "vulnerable_code ناقص", "ExploitTriple/before")
        if not self.patch_code or len(self.patch_code) < 10:
            return Decision(False, "patch_code ناقص", "ExploitTriple/patch")
        # exploit_code قد يكون اختيارياً في المرحلة الأولى
        return Decision(True, "", "ExploitTriple/ok")


# ═══════════════════════════════════════════════════════
# القسم 4 — Audit Logger
# ═══════════════════════════════════════════════════════
class AuditLogger:
    @staticmethod
    def log(decision: Decision, context: str = ""):
        entry = {
            "ts": time.time(),
            "allowed": decision.allowed,
            "reason": decision.reason,
            "article": decision.article,
            "context": context[:200],
        }
        with AUDIT_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ═══════════════════════════════════════════════════════
# الواجهة الموحّدة
# ═══════════════════════════════════════════════════════
class AgentConstitution:
    """البوابة الشاملة — تُستدعى قبل كل مهمة."""

    @staticmethod
    def check_task(task: dict) -> Decision:
        """يفحص مهمة كاملة قبل Self-Play."""
        # 1. فحص الكود
        before = task.get("before", "")
        d = DataQualityFilter.check_code(before)
        if not d.allowed:
            AuditLogger.log(d, f"task={task.get('cve', '')}")
            return d

        # 2. فحص التوثيق
        d = DataQualityFilter.check_documentation(before)
        if not d.allowed:
            AuditLogger.log(d, f"task={task.get('cve', '')}")
            return d

        # 3. فحص الهيكل الثلاثي
        triple = ExploitTriple(
            cve=task.get("cve", ""),
            vulnerable_code=before,
            exploit_code=task.get("exploit", ""),
            patch_code=task.get("after", ""),
        )
        d = triple.validate()
        if not d.allowed:
            AuditLogger.log(d, f"task={task.get('cve', '')}")
            return d

        # 4. تطهير المعطيات
        task["before"] = DataQualityFilter.sanitize(task.get("before", ""))
        task["after"] = DataQualityFilter.sanitize(task.get("after", ""))

        allowed = Decision(True, "", "AgentConstitution/ok")
        AuditLogger.log(allowed, f"task={task.get('cve', '')}")
        return allowed

    @staticmethod
    def check_source(url: str, license_name: str = "") -> Decision:
        """يفحص مصدر خارجي."""
        d = LegalShieldGate.check_domain(url)
        if not d.allowed:
            AuditLogger.log(d, url)
            return d
        if license_name:
            d = LegalShieldGate.check_license(license_name)
            if not d.allowed:
                AuditLogger.log(d, url)
                return d
        return Decision(True, "", "AgentConstitution/source_ok")


# ═══════════════════════════════════════════════════════
# اختبار
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=== اختبار الدستور ===\n")

    # 1. ترخيص MIT
    d = LegalShieldGate.check_license("MIT")
    print(f"MIT: {'✓' if d.allowed else '✗'} {d.reason}")

    # 2. ترخيص proprietary
    d = LegalShieldGate.check_license("Proprietary")
    print(f"Proprietary: {'✓' if d.allowed else '✗'} {d.reason}")

    # 3. كود آمن
    d = DataQualityFilter.check_code("def add(a, b):\n    return a + b")
    print(f"Safe code: {'✓' if d.allowed else '✗'} {d.reason}")

    # 4. كود به eval
    d = DataQualityFilter.check_code("result = eval(user_input)")
    print(f"Code with eval: {'✓' if d.allowed else '✗'} {d.reason}")

    # 5. مهمة كاملة
    task = {
        "cve": "CVE-2021-44228",
        "before": "def lookup(user_input):\n    # ثغرة JNDI\n    return jndi.lookup(user_input)\n",
        "after": "def lookup(user_input):\n    # تحقق أولاً\n    if is_allowed(user_input):\n        return jndi.lookup(user_input)\n",
        "exploit": "",
    }
    d = AgentConstitution.check_task(task)
    print(f"Full task: {'✓' if d.allowed else '✗'} {d.article} {d.reason}")
