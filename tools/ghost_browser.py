"""
Marsad Ghost Browser v2 — متصفح مُفكَّك لحل reCAPTCHA v2 على Termux.
الرام الذروة: ~40MB. لا Chromium. لا Playwright.
"""
from __future__ import annotations
import re, time, json
from pathlib import Path
from typing import Optional, Dict, Any

import httpx

try:
    from lxml import html as lxml_html
    _HAS_LXML = True
except ImportError:
    _HAS_LXML = False

try:
    from vosk import Model, KaldiRecognizer
    import wave
    _HAS_VOSK = True
except ImportError:
    _HAS_VOSK = False


RECAPTCHA_VERSION = "kemdRjWFxNjgsGdhRslyEPwU"
VOSK_MODEL_PATH = Path.home() / ".marsad" / "vosk-model-small-en-us"
CF_WORKER_FILE = Path.home() / ".marsad" / "cf_worker_url"

_UA = ("Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")


class AnchorProvider:
    def __init__(self, sitekey, page_url):
        self.sitekey = sitekey
        self.page_url = page_url

    def get(self):
        if CF_WORKER_FILE.exists():
            try:
                worker = CF_WORKER_FILE.read_text().strip()
                r = httpx.post(f"{worker}/anchor",
                               json={"sitekey": self.sitekey,
                                     "page_url": self.page_url},
                               timeout=8)
                if r.status_code == 200:
                    d = r.json()
                    if d.get("token"):
                        return {"token": d["token"],
                                "session_id": d.get("session_id", ""),
                                "source": "cf_worker"}
            except Exception:
                pass
        try:
            r = httpx.post(
                "https://www.google.com/recaptcha/api2/anchor",
                data={"k": self.sitekey, "hl": "en",
                      "v": RECAPTCHA_VERSION, "t": "1"},
                headers={"User-Agent": _UA}, timeout=10,
            )
            sid = self._extract_session(r.text)
            if sid:
                return {"token": "", "session_id": sid, "source": "http"}
        except Exception:
            pass
        return {"token": "", "session_id": "", "source": "none"}

    @staticmethod
    def _extract_session(html):
        m = re.search(r'"session_id"\s*:\s*"([^"]+)"', html)
        return m.group(1) if m else None


def extract_audio_url(html):
    if _HAS_LXML:
        try:
            tree = lxml_html.fromstring(html)
            nodes = tree.xpath('//*[@id="audio-source"]')
            if nodes and nodes[0].get("src"):
                return nodes[0].get("src")
        except Exception:
            pass
    for p in [r'id="audio-source"[^>]*src="([^"]+)"',
              r'src="([^"]*payload[^"]*)"',
              r'"(https://www\.google\.com/recaptcha/api2/payload[^"]+)"']:
        m = re.search(p, html)
        if m:
            return m.group(1).replace("&amp;", "&")
    return None


def extract_challenge_id(html):
    for p in [r'[?&]c=([A-Za-z0-9_-]+)', r'"c"\s*:\s*"([^"]+)"']:
        m = re.search(p, html)
        if m:
            return m.group(1)
    return None


class VoskTranscriber:
    _model = None

    def __init__(self, model_path=None):
        self.model_path = model_path or VOSK_MODEL_PATH

    def _load(self):
        if VoskTranscriber._model is None:
            if not self.model_path.exists():
                raise FileNotFoundError(f"Vosk model missing: {self.model_path}")
            VoskTranscriber._model = Model(str(self.model_path))
        return VoskTranscriber._model

    def transcribe(self, audio_bytes):
        if not _HAS_VOSK:
            raise RuntimeError("pip install vosk")
        tmp = Path("/tmp/ghost_audio.raw")
        tmp.write_bytes(audio_bytes)
        try:
            wav_path = self._to_wav(tmp)
            with wave.open(str(wav_path), "rb") as wf:
                rec = KaldiRecognizer(self._load(), wf.getframerate())
                out = []
                while True:
                    data = wf.readframes(4000)
                    if not data:
                        break
                    if rec.AcceptWaveform(data):
                        r = json.loads(rec.Result())
                        if r.get("text"):
                            out.append(r["text"])
                final = json.loads(rec.FinalResult())
                if final.get("text"):
                    out.append(final["text"])
            return " ".join(out).strip()
        finally:
            tmp.unlink(missing_ok=True)

    @staticmethod
    def _to_wav(src):
        if src.suffix == ".wav":
            return src
        dst = src.with_suffix(".wav")
        import subprocess
        try:
            subprocess.run(["ffmpeg", "-y", "-i", str(src),
                            "-ar", "16000", "-ac", "1", "-f", "wav", str(dst)],
                           check=True, capture_output=True, timeout=20)
            return dst
        except Exception:
            return src


class GhostBrowser:
    def __init__(self, sitekey, page_url, vosk_model=None):
        self.sitekey = sitekey
        self.page_url = page_url
        self.session = httpx.Client(
            headers={"User-Agent": _UA,
                     "Accept-Language": "en-US,en;q=0.9",
                     "Accept": "*/*", "Referer": page_url},
            timeout=25.0, follow_redirects=True)
        self.anchor = AnchorProvider(sitekey, page_url)
        self.transcriber = VoskTranscriber(vosk_model)

    def open_challenge(self, session_id):
        r = self.session.get(
            "https://www.google.com/recaptcha/api2/bframe",
            params={"k": self.sitekey, "hl": "en",
                    "v": RECAPTCHA_VERSION, "t": ""})
        audio_url = extract_audio_url(r.text)
        cid = extract_challenge_id(r.text)
        if not audio_url:
            raise RuntimeError("no audio url")
        return {"audio_url": audio_url, "challenge_id": cid or "",
                "html": r.text}

    def fetch_audio(self, audio_url):
        r = self.session.get(audio_url, timeout=15)
        r.raise_for_status()
        return r.content

    def submit(self, answer, anchor_token, challenge_id=""):
        payload = {"k": self.sitekey, "response": answer,
                   "v": RECAPTCHA_VERSION, "t": anchor_token or ""}
        if challenge_id:
            payload["c"] = challenge_id
        r = self.session.post(
            "https://www.google.com/recaptcha/api2/userverify",
            data=payload)
        txt = r.text.lower()
        return {"ok": '"true"' in txt or 'true' in txt[:200],
                "status": r.status_code, "body": r.text[:300]}

    def solve(self, max_attempts=3, on_step=None):
        def _log(msg):
            if on_step:
                on_step(msg)
            else:
                print(f"[ghost] {msg}")

        for attempt in range(1, max_attempts + 1):
            try:
                _log(f"attempt {attempt}: anchor")
                a = self.anchor.get()
                _log(f"source: {a['source']}")
                ch = self.open_challenge(a["session_id"])
                _log(f"challenge: {ch['challenge_id'][:12]}")
                audio = self.fetch_audio(ch["audio_url"])
                _log(f"audio: {len(audio)}b")
                answer = self.transcriber.transcribe(audio)
                _log(f"answer: {answer!r}")
                if not answer:
                    continue
                res = self.submit(answer, a["token"], ch["challenge_id"])
                _log(f"submit: {res}")
                if res["ok"]:
                    return answer
            except Exception as e:
                _log(f"error: {e}")
            time.sleep(2)
        return None


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("usage: ghost_browser.py <sitekey> <page_url>")
        sys.exit(1)
    gb = GhostBrowser(sys.argv[1], sys.argv[2])
    print(json.dumps({"answer": gb.solve()}))
