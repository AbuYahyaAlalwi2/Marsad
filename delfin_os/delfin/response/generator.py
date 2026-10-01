"""مولّد الردود (الطبقة 5): تنظيف مخرجات النموذج قبل أن يراها العميل."""
import re

_THINK = re.compile(r"<think>.*?</think>", re.S)


def strip_think(text):
    """يحذف وسم التفكير الداخلي، ويعالج حالة النماذج التي تُغلق الوسم دون فتحه أو لا تغلقه."""
    text = text or ""
    text = _THINK.sub("", text)
    if "</think>" in text and "<think>" not in text:
        text = text.rsplit("</think>", 1)[1]
    if "<think>" in text:
        text = text.split("<think>", 1)[0]
    return text.strip()


class ResponseGenerator:
    def __init__(self, scanner, canary=None):
        self.scanner, self.canary = scanner, canary

    def compress(self, text, max_chars):
        if len(text) <= max_chars:
            return text
        cut = text[:max_chars]
        m = max(cut.rfind("."), cut.rfind("؟"), cut.rfind("!"), cut.rfind("\n"))
        return (cut[: m + 1] if m > max_chars // 2 else cut).strip() + " …"

    def render(self, text, mode="text"):
        if mode == "bullets":
            parts = [s.strip() for s in re.split(r"[.\n]+", text) if s.strip()]
            return "\n".join(f"• {p}" for p in parts)
        if mode == "code":
            return f"```\n{text}\n```"
        return text

    def finalize(self, raw, persona, mode="text", max_chars=3500):
        """يعيد {'text', 'flags'}. أي تسريب للرمز السري يستبدل الرد كله برفض."""
        flags = []
        text = strip_think(raw)
        if self.canary and self.canary in text:
            return {"text": persona.refusal, "flags": ["canary_leak"]}
        if self.scanner.find(text):
            text, flags = self.scanner.redact(text), flags + ["secret_redacted"]
        if any(f in text for f in persona.forbidden):
            return {"text": persona.refusal, "flags": flags + ["persona_violation"]}
        if not text:
            return {"text": persona.refusal, "flags": flags + ["empty"]}
        return {"text": self.render(self.compress(text, max_chars), mode), "flags": flags}
