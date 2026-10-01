"""عزل التنفيذ (الطبقة 1.4).

تحذير أمني مهم: LocalSandbox ليس عزلاً حقيقياً. العملية الفرعية ترى كل ملفات
المستخدم (ومنها ~/.marsad_secrets في Termux). لذلك هو مقفل افتراضياً ولا يعمل
إلا بـ dev_mode=True للتجارب. التنفيذ الحقيقي يكون عبر RemoteSandbox أو حاوية."""
import json
import os
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import urllib.request

_ENV = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1"}


def _probe_netns():
    u = shutil.which("unshare")
    if not u:
        return False
    try:
        return subprocess.run([u, "-rn", "true"], capture_output=True, timeout=5).returncode == 0
    except Exception:
        return False


def _setrlimit(kind, value):
    try:
        resource.setrlimit(kind, (value, value))
    except (ValueError, OSError):
        pass


def _rss(pid):
    """الذاكرة الفعلية للعملية بالبايت، أو None إن لم يتوفر /proc."""
    try:
        with open(f"/proc/{pid}/statm") as f:
            return int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
    except (OSError, ValueError, IndexError):
        return None


def _probe_mem_limit(python, mem):
    """أي نوع حد ذاكرة يعمل فعلاً هنا؟ على Android يُجهض RLIMIT_AS حتى عند 2GB (مخصّص الذاكرة يحجز عناوين ضخمة).
    نجرّب النوع: هل يقلع بايثون به؟ وهل يمنع فعلاً تخصيص ضعف الحد؟"""
    for name, kind in (("AS", resource.RLIMIT_AS), ("DATA", resource.RLIMIT_DATA)):
        pre = lambda k=kind: resource.setrlimit(k, (mem, mem))
        try:
            ok = subprocess.run([python, "-I", "-B", "-c", "print(1)"], capture_output=True, timeout=20, preexec_fn=pre)
            if ok.returncode != 0 or ok.stdout.strip() != b"1":
                continue
            big = subprocess.run([python, "-I", "-B", "-c", f"x = bytearray({mem * 2}); print('NOLIMIT')"],
                                 capture_output=True, timeout=30, preexec_fn=pre)
            if b"NOLIMIT" not in big.stdout:
                return name
        except Exception:
            continue
    return None


class LocalSandbox:
    def __init__(self, dev_mode=False, require_network_isolation=True, mem_mb=256, cpu_s=10,
                 max_out=20000, python=None, use_rlimit_mem=True, require_mem_limit=True):
        self.dev_mode, self.require_net = dev_mode, require_network_isolation
        self.mem_mb, self.cpu_s, self.max_out = mem_mb, cpu_s, max_out
        self.python = python or sys.executable
        self.use_rlimit_mem, self.require_mem = use_rlimit_mem, require_mem_limit
        self.netns = _probe_netns()
        self._limit_kind = "unprobed"

    @property
    def limit_kind(self):
        if self._limit_kind == "unprobed":
            self._limit_kind = _probe_mem_limit(self.python, self.mem_mb * 1024 * 1024) if self.use_rlimit_mem else None
        return self._limit_kind

    def run_python(self, code, timeout=10):
        if not self.dev_mode:
            return {"status": "refused", "stdout": "", "stderr":
                    "العزل المحلي غير آمن ومقفل. استخدم RemoteSandbox أو حاوية.", "isolated": False}
        if self.require_net and not self.netns:
            return {"status": "refused", "stdout": "", "stderr":
                    "لا يتوفر عزل الشبكة (unshare) على هذا الجهاز.", "isolated": False}
        mem = self.mem_mb * 1024 * 1024
        kind = self.limit_kind
        watchdog = _rss(os.getpid()) is not None
        mem_mode = "+".join(m for m in (("rlimit-" + kind.lower()) if kind else "", "watchdog" if watchdog else "") if m)
        if self.require_mem and not mem_mode:
            return {"status": "refused", "stdout": "", "stderr": "لا يتوفر أي حد للذاكرة على هذا الجهاز.",
                    "isolated": False}
        rkind = {"AS": resource.RLIMIT_AS, "DATA": resource.RLIMIT_DATA}.get(kind)

        def limits():
            if rkind is not None:
                _setrlimit(rkind, mem)
            _setrlimit(resource.RLIMIT_CPU, self.cpu_s)
            _setrlimit(resource.RLIMIT_FSIZE, 5_000_000)
            _setrlimit(resource.RLIMIT_CORE, 0)

        with tempfile.TemporaryDirectory(prefix="dlf_sbx_") as d:
            script = os.path.join(d, "main.py")
            with open(script, "w", encoding="utf-8") as f:
                f.write(code)
            cmd = [self.python, "-I", "-B", script]
            if self.netns:
                cmd = [shutil.which("unshare"), "-rn"] + cmd
            p = subprocess.Popen(cmd, cwd=d, env=dict(_ENV), stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 preexec_fn=limits, start_new_session=True)
            done, killed = threading.Event(), [False]

            def kill_group():
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass

            def watch():                       # يقيس الذاكرة الفعلية ويقتل عند التجاوز
                while not done.is_set() and p.poll() is None:
                    r = _rss(p.pid)
                    if r is not None and r > mem:
                        killed[0] = True
                        kill_group()
                        return
                    done.wait(0.02)

            t = threading.Thread(target=watch, daemon=True)
            if watchdog:
                t.start()
            status = "ok"
            try:
                out, err = p.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                kill_group()
                out, err = p.communicate()
                status = "timeout"
            done.set()
            if watchdog:
                t.join(1)
            if killed[0]:
                status = "memory"
            elif status == "ok" and p.returncode != 0:
                status = "error"
        return {"status": status, "exit": p.returncode, "mem_mode": mem_mode,
                "stdout": out.decode("utf-8", "replace")[: self.max_out],
                "stderr": err.decode("utf-8", "replace")[: self.max_out], "isolated": self.netns}


class RemoteSandbox:
    """عميل لصندوق بعيد (مثل Deno على Railway).
    غير مُتحقَّق منه: مسار الطلب وشكل الرد افتراضان يجب مطابقتهما مع main.ts الفعلي."""

    def __init__(self, url, token, path="/run", timeout=30):
        if not url.startswith("https://"):
            raise ValueError("يجب أن يكون الرابط https")
        self.url, self.token, self.path, self.timeout = url.rstrip("/"), token, path, timeout

    def run_python(self, code, timeout=10):
        req = urllib.request.Request(
            self.url + self.path, method="POST",
            data=json.dumps({"code": code, "timeout_ms": int(timeout * 1000)}).encode(),
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                d = json.loads(r.read(200_000))
        except Exception as e:
            return {"status": "error", "stdout": "", "stderr": f"فشل الاتصال: {type(e).__name__}", "isolated": True}
        return {"status": d.get("status", "ok"), "stdout": str(d.get("stdout", ""))[:20000],
                "stderr": str(d.get("stderr", ""))[:20000], "isolated": True}
