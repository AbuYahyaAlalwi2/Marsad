"""ذكاء التوكن (الطبقة 3): عدّاد، ميزانية، تنبيهات، توقع تكلفة، تحسين.
العدّ تقديري؛ عند توفر usage الحقيقي من الخادم نعتمده."""
import re
import sqlite3
import threading
import time

from ..core.errors import BudgetExceeded


class TokenIntelligence:
    def __init__(self, path=":memory:", session_limit=50000, warn=0.8, prices=None):
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        self.limit, self.warn = session_limit, warn
        self.prices = prices or {}  # {"model": (سعر_مدخل_لكل_مليون, سعر_مخرج_لكل_مليون)}
        self.efficiency = False
        with self._lock:
            self._db.execute("CREATE TABLE IF NOT EXISTS usage(session TEXT, owner TEXT, t_in INTEGER, "
                             "t_out INTEGER, ts REAL)")
            self._db.commit()

    @staticmethod
    def estimate(text):
        return max(1, int(len(text or "") / 3.2))

    def used(self, session):
        with self._lock:
            r = self._db.execute("SELECT COALESCE(SUM(t_in+t_out),0) FROM usage WHERE session=?", (session,)).fetchone()
        return int(r[0])

    def check_before(self, session, est_tokens):
        if self.used(session) + est_tokens > self.limit:
            raise BudgetExceeded("تجاوزت ميزانية التوكن لهذه الجلسة")

    def charge(self, session, owner, t_in, t_out):
        with self._lock:
            self._db.execute("INSERT INTO usage VALUES(?,?,?,?,?)", (session, owner, int(t_in), int(t_out), time.time()))
            self._db.commit()
        return self.status(session)

    def status(self, session):
        u = self.used(session)
        state = "exceeded" if u >= self.limit else "warn" if u >= self.limit * self.warn else "ok"
        return {"used": u, "limit": self.limit, "state": state}

    def predict_cost(self, model, t_in, t_out):
        pi, po = self.prices.get(model, (0.0, 0.0))
        return (t_in * pi + t_out * po) / 1_000_000

    def optimize(self, text):
        """تقليص آمن: مسافات زائدة وأسطر مكررة متتالية، دون تغيير المعنى."""
        out, prev = [], None
        for line in (text or "").splitlines():
            line = re.sub(r"[ \t]+", " ", line).strip()
            if line and line == prev:
                continue
            out.append(line)
            prev = line
        return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()

    def max_tokens(self, wanted=512):
        return max(64, wanted // 2) if self.efficiency else wanted

    def report(self, owner):
        with self._lock:
            r = self._db.execute("SELECT COALESCE(SUM(t_in),0), COALESCE(SUM(t_out),0), COUNT(*) FROM usage "
                                 "WHERE owner=?", (owner,)).fetchone()
        return {"tokens_in": r[0], "tokens_out": r[1], "requests": r[2]}
