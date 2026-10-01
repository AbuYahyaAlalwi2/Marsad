"""عميل النموذج (متوافق مع واجهة OpenAI). لا يرسل أسراراً ولا يطبع المفتاح."""
import asyncio
import json
import urllib.error
import urllib.request

from ..core.errors import SecurityError


class LLMClient:
    def __init__(self, base_url, api_key="", model="v2", timeout=120, scanner=None):
        ok = base_url.startswith(("https://", "http://127.0.0.1", "http://localhost"))
        if not ok:
            raise SecurityError("رابط النموذج يجب أن يكون https أو محلياً")
        self.base, self.key, self.model = base_url.rstrip("/"), api_key, model
        self.timeout, self.scanner = timeout, scanner

    def chat(self, messages, max_tokens=512, temperature=0.4):
        if self.scanner:
            for m in messages:
                if self.scanner.find(m.get("content", "")):
                    raise SecurityError("الطلب الصادر يحتوي سراً")
        body = json.dumps({"model": self.model, "messages": messages,
                           "max_tokens": int(max_tokens), "temperature": temperature}).encode()
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = f"Bearer {self.key}"
        req = urllib.request.Request(self.base + "/chat/completions", data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                d = json.loads(r.read(2_000_000))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"فشل خادم النموذج: {e.code}") from None
        except Exception as e:
            raise RuntimeError(f"تعذر الاتصال بالنموذج: {type(e).__name__}") from None
        msg = d["choices"][0]["message"]["content"]
        u = d.get("usage", {})
        return {"content": msg, "usage": {"prompt_tokens": u.get("prompt_tokens", 0),
                                          "completion_tokens": u.get("completion_tokens", 0)}}

    async def achat(self, *a, **k):
        return await asyncio.to_thread(self.chat, *a, **k)


class FakeLLM:
    """نموذج وهمي للاختبارات."""

    def __init__(self, replies):
        self.replies, self.calls = replies, []

    def chat(self, messages, **kw):
        self.calls.append(messages)
        r = self.replies(messages) if callable(self.replies) else self.replies.pop(0)
        return {"content": r, "usage": {"prompt_tokens": 10, "completion_tokens": 5}}

    async def achat(self, *a, **k):
        return await asyncio.to_thread(self.chat, *a, **k)
