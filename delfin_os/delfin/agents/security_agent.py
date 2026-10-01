"""وكيل المراجعة: يفحص نصاً/رابطاً بحثاً عن أسرار وحقن وروابط داخلية."""
from ..core.errors import SecurityError
from .base import Agent


class SecurityAgent(Agent):
    name = "security"

    def __init__(self, security):
        self.sec = security

    async def handle(self, kind, payload, ctx):
        report = {"secrets": [], "suspicious": [], "link": None}
        text = str(payload.get("text", ""))[:20000]
        if text:
            report["secrets"] = self.sec.scanner.find(text)
            ok, sus = self.sec.validator.check(text)
            report["suspicious"] = sus if ok else ["مرفوض: " + "، ".join(sus)]
        if payload.get("url"):
            try:
                self.sec.links.check(payload["url"])
                report["link"] = "آمن"
            except SecurityError as e:
                report["link"] = f"محجوب: {e}"
        return report
