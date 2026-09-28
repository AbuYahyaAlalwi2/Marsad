"""account_pool.py — يوزّع 12+ حساب على الوكلاء مع failover."""
from __future__ import annotations
import os, itertools, threading, time, logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Account:
    platform: str
    idx: int
    creds: Dict[str, str] = field(default_factory=dict)
    cooldown_until: float = 0.0
    fail_count: int = 0
    use_count: int = 0

    def ok(self) -> bool:
        return time.time() >= self.cooldown_until

    def name(self) -> str:
        return f"{self.platform}_{self.idx}"


def _discover() -> List[Account]:
    accounts: List[Account] = []
    for i in range(1, 11):
        acc = os.environ.get(f"CF_ACCOUNT_{i}")
        tok = os.environ.get(f"CF_TOKEN_{i}")
        if acc and tok:
            accounts.append(Account("cloudflare", i,
                                    {"account": acc, "token": tok}))
    for i in range(1, 11):
        u = os.environ.get(f"KAGGLE_USERNAME_{i}")
        k = os.environ.get(f"KAGGLE_KEY_{i}")
        if u and k:
            accounts.append(Account("kaggle", i, {"username": u, "key": k}))
    for i in range(1, 11):
        k = os.environ.get(f"SATURN_API_KEY_{i}")
        if k:
            accounts.append(Account("saturn", i, {"key": k}))
    hf = os.environ.get("HF_TOKEN")
    if hf:
        accounts.append(Account("huggingface", 1, {"token": hf}))
    # Fly.io: FLY_API_TOKEN_N
    for i in range(1, 6):
        t = os.environ.get(f"FLY_API_TOKEN_{i}") or (os.environ.get("FLY_API_TOKEN") if i == 1 else None)
        if t:
            accounts.append(Account("fly", i, {"token": t}))
    # Railway: RAILWAY_TOKEN_N
    for i in range(1, 6):
        t = os.environ.get(f"RAILWAY_TOKEN_{i}") or (os.environ.get("RAILWAY_TOKEN") if i == 1 else None)
        if t:
            accounts.append(Account("railway", i, {"token": t}))
    # Koyeb: KOYEB_TOKEN_N
    for i in range(1, 6):
        t = os.environ.get(f"KOYEB_TOKEN_{i}") or (os.environ.get("KOYEB_TOKEN") if i == 1 else None)
        if t:
            accounts.append(Account("koyeb", i, {"token": t}))
    # Render: RENDER_API_KEY_N
    for i in range(1, 6):
        t = os.environ.get(f"RENDER_API_KEY_{i}") or (os.environ.get("RENDER_API_KEY") if i == 1 else None)
        if t:
            accounts.append(Account("render", i, {"token": t}))

    return accounts

class AccountPool:
    _inst = None

    def __new__(cls):
        if cls._inst is None:
            cls._inst = super().__new__(cls); cls._inst._init()
        return cls._inst

    def _init(self):
        self.accounts = _discover()
        self._lock = threading.Lock()
        self._cycle = {}
        self._rebuild_cycles()

    def _rebuild_cycles(self):
        by_plat = {}
        for a in self.accounts:
            by_plat.setdefault(a.platform, []).append(a)
        for plat, lst in by_plat.items():
            self._cycle[plat] = itertools.cycle(lst)

    def next_for(self, platform):
        with self._lock:
            cyc = self._cycle.get(platform)
            if not cyc: return None
            total = len([a for a in self.accounts if a.platform == platform])
            for _ in range(total):
                a = next(cyc)
                if a.ok():
                    a.use_count += 1
                    return a
            return None

    def mark_failed(self, acc, cooldown: int = 120):
        with self._lock:
            acc.fail_count += 1
            acc.cooldown_until = time.time() + cooldown

    def mark_ok(self, acc):
        with self._lock:
            acc.fail_count = max(0, acc.fail_count - 1)

    def stats(self):
        out = {}
        for a in self.accounts:
            out.setdefault(a.platform, {"count": 0, "active": 0, "uses": 0, "fails": 0})
            out[a.platform]["count"] += 1
            if a.ok(): out[a.platform]["active"] += 1
            out[a.platform]["uses"] += a.use_count
            out[a.platform]["fails"] += a.fail_count
        return out


account_pool = AccountPool()


def with_account(platform: str):
    def deco(fn):
        def wrapper(payload):
            acc = account_pool.next_for(platform)
            if not acc:
                raise RuntimeError(f"لا حساب {platform} متاح")
            try:
                result = fn(payload, acc)
                account_pool.mark_ok(acc)
                result["_account"] = acc.name()
                return result
            except Exception:
                account_pool.mark_failed(acc)
                raise
        wrapper.__name__ = fn.__name__
        return wrapper
    return deco
