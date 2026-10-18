#!/usr/bin/env python3
"""بوابة المزوّدين: Groq (تدوير حتى 6 مفاتيح) -> OpenRouter -> HF، مع تبريد عند 429 وتبديل تلقائي.
بلا تبعيات خارجية. المفاتيح تبقى في هذه العملية فقط؛ المنقّب لا يراها (يكلّمنا عبر localhost)."""
import json, os, threading, time, urllib.request, urllib.error

PROVIDERS = {
    "groq": ("https://api.groq.com/openai/v1/chat/completions", os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")),
    "openrouter": ("https://openrouter.ai/api/v1/chat/completions", os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")),
    "hf": ("https://router.huggingface.co/v1/chat/completions", os.environ.get("HF_MODEL", "meta-llama/Llama-3.3-70B-Instruct")),
}


def load_keys(env=os.environ):
    keys = []
    g = [k.strip() for k in env.get("GROQ_KEYS", "").split(",") if k.strip()]
    g += [env[f"GROQ_API_KEY_{i}"] for i in range(1, 11) if env.get(f"GROQ_API_KEY_{i}")]
    if env.get("GROQ_API_KEY"):
        g.append(env["GROQ_API_KEY"])
    for k in dict.fromkeys(g):
        keys.append(("groq", k))
    if env.get("OPENROUTER_API_KEY"):
        keys.append(("openrouter", env["OPENROUTER_API_KEY"]))
    if env.get("HF_TOKEN") and env.get("LLM_USE_HF", "0") == "1":
        keys.append(("hf", env["HF_TOKEN"]))
    return keys


class Gateway:
    def __init__(self, keys=None, post=None, now=time.time):
        self.keys = keys if keys is not None else load_keys()
        self.cool = {}                    # index -> وقت انتهاء التبريد
        self.dead = set()                 # مفاتيح رفضها المزوّد (401/403): لا تُجرَّب مجدداً
        self.rr = 0
        self.lock = threading.Lock()
        self.post = post or self._post
        self.now = now
        self.stats = {"ok": 0, "fail": 0, "by": {}, "rate_limited": 0}

    @staticmethod
    def _post(url, key, body, timeout=60):
        req = urllib.request.Request(url, json.dumps(body).encode(), {"Authorization": "Bearer " + key, "Content-Type": "application/json",
                                                                       "User-Agent": "marsad-factory/1"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())

    def available(self):
        return bool(self.keys)

    def _order(self):
        with self.lock:
            n = len(self.keys)
            idx = [(self.rr + i) % n for i in range(n)]
            self.rr = (self.rr + 1) % max(n, 1)
        t = self.now()
        live = [i for i in idx if i not in self.dead and self.cool.get(i, 0) <= t]
        # الأولوية للمزوّد الأرخص/الأسرع: groq ثم openrouter ثم hf، مع بقاء التدوير داخل المزوّد
        rank = {"groq": 0, "openrouter": 1, "hf": 2}
        return sorted(live, key=lambda i: rank[self.keys[i][0]])

    def chat(self, messages, max_tokens=1500, temperature=0.8, json_mode=False):
        last = None
        for i in self._order():
            prov, key = self.keys[i]
            url, model = PROVIDERS[prov]
            body = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
            if json_mode and prov == "groq":
                body["response_format"] = {"type": "json_object"}
            try:
                r = self.post(url, key, body)
                txt = r["choices"][0]["message"]["content"]
                with self.lock:
                    self.stats["ok"] += 1; self.stats["by"][prov] = self.stats["by"].get(prov, 0) + 1
                return txt
            except urllib.error.HTTPError as e:
                last = f"{prov} http {e.code}"
                with self.lock:
                    if e.code == 429:
                        ra = e.headers.get("retry-after") if e.headers else None
                        self.cool[i] = self.now() + min(float(ra) if ra and ra.replace(".", "").isdigit() else 60, 900)
                        self.stats["rate_limited"] += 1
                    elif e.code in (401, 403):
                        self.dead.add(i)
                    else:
                        self.cool[i] = self.now() + 30
            except Exception as e:
                last = f"{prov} {type(e).__name__}"
                with self.lock:
                    self.cool[i] = self.now() + 30
        with self.lock:
            self.stats["fail"] += 1
        raise RuntimeError("all providers failed: " + str(last))
