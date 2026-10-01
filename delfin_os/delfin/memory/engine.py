"""محرك الذاكرة (الطبقة 2): جلسات، أولوية، ضغط، تحلل، لقطات. كل جلسة ملك مالكها."""
import hashlib
import json
import re
import sqlite3
import threading
import time
import uuid

from ..core.errors import SecurityError


class MemoryEngine:
    MAX_ITEM = 8000

    def __init__(self, path=":memory:", scanner=None):
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        self.scanner = scanner
        with self._lock:
            self._db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, owner TEXT, persona TEXT, created REAL);
            CREATE TABLE IF NOT EXISTS items(id INTEGER PRIMARY KEY AUTOINCREMENT, session TEXT, role TEXT,
              content TEXT, importance INTEGER, created REAL, accessed REAL);
            CREATE INDEX IF NOT EXISTS ix_items_s ON items(session, id);
            """)
            self._db.commit()

    def _q(self, sql, args=()):
        with self._lock:
            return self._db.execute(sql, args).fetchall()

    def _x(self, sql, args=()):
        with self._lock:
            cur = self._db.execute(sql, args)
            self._db.commit()
            return cur

    # الجلسات
    def create_session(self, owner, persona="assistant"):
        sid = uuid.uuid4().hex[:16]
        self._x("INSERT INTO sessions VALUES(?,?,?,?)", (sid, owner, persona, time.time()))
        return sid

    def get_session(self, sid, owner):
        rows = self._q("SELECT id, owner, persona, created FROM sessions WHERE id=?", (sid,))
        if not rows or rows[0][1] != owner:  # عزل المستأجرين: لا نكشف وجود جلسة غيرك
            raise SecurityError("جلسة غير موجودة")
        return {"id": rows[0][0], "owner": rows[0][1], "persona": rows[0][2]}

    def list_sessions(self, owner):
        return [{"id": r[0], "persona": r[1], "created": r[2]} for r in
                self._q("SELECT id, persona, created FROM sessions WHERE owner=? ORDER BY created DESC", (owner,))]

    def set_persona(self, sid, owner, persona):
        self.get_session(sid, owner)
        self._x("UPDATE sessions SET persona=? WHERE id=?", (persona, sid))

    # العناصر (قاعدة الذاكرة: لا أسرار تُحفظ أبداً، تُحجب قبل التخزين)
    def add(self, sid, role, content, importance=1):
        content = str(content)[: self.MAX_ITEM]
        redacted = False
        if self.scanner and self.scanner.find(content):
            content, redacted = self.scanner.redact(content), True
        now = time.time()
        self._x("INSERT INTO items(session,role,content,importance,created,accessed) VALUES(?,?,?,?,?,?)",
                (sid, role, content, max(1, min(int(importance), 5)), now, now))
        return {"redacted": redacted}

    def context(self, sid, max_chars=6000):
        """الأهم (أولوية>=4) ثم الأحدث ضمن الميزانية، بترتيب زمني."""
        rows = self._q("SELECT id, role, content, importance FROM items WHERE session=? "
                       "AND role IN ('user','assistant','summary') ORDER BY id", (sid,))
        chosen, used = {}, 0
        for r in [x for x in rows if x[3] >= 4] + list(reversed(rows)):
            if r[0] in chosen or used + len(r[2]) > max_chars:
                continue
            chosen[r[0]], used = r, used + len(r[2])
        out = []
        for r in sorted(chosen.values()):
            role = "system" if r[1] == "summary" else r[1]
            text = ("ملخص سابق: " + r[2]) if r[1] == "summary" else r[2]
            out.append({"role": role, "content": text})
        if chosen:
            self._x(f"UPDATE items SET accessed=? WHERE id IN ({','.join('?' * len(chosen))})",
                    (time.time(), *chosen.keys()))
        return out

    def prefs(self, sid, persona):
        rows = self._q("SELECT content FROM items WHERE session=? AND role=? ORDER BY id DESC LIMIT 5",
                       (sid, f"pref:{persona}"))
        return [r[0] for r in rows]

    def search(self, sid, query, limit=5):
        words = [w for w in re.findall(r"\w{3,}", query or "")][:6]
        if not words:
            return []
        cond = " OR ".join(["content LIKE ?"] * len(words))
        rows = self._q(f"SELECT role, content FROM items WHERE session=? AND ({cond}) ORDER BY id DESC LIMIT ?",
                       (sid, *[f"%{w}%" for w in words], max(1, min(limit, 20))))
        return [{"role": r[0], "content": r[1]} for r in rows]

    def compress(self, sid, keep_last=10, summarizer=None):
        rows = self._q("SELECT id, role, content FROM items WHERE session=? AND role IN ('user','assistant') "
                       "AND importance<4 ORDER BY id", (sid,))
        old = rows[:-keep_last] if keep_last else rows
        if len(old) < 2:
            return 0
        text = "\n".join(f"{r[1]}: {r[2][:200]}" for r in old)
        summary = (summarizer(text) if summarizer else text)[:1500]
        self._x(f"DELETE FROM items WHERE id IN ({','.join('?' * len(old))})", tuple(r[0] for r in old))
        self.add(sid, "summary", summary, importance=3)
        return len(old)

    def decay(self, older_than_days=30, now=None):
        cutoff = (now or time.time()) - older_than_days * 86400
        cur = self._x("DELETE FROM items WHERE importance<=2 AND accessed<?", (cutoff,))
        return cur.rowcount

    def snapshot(self, sid, owner, path):
        self.get_session(sid, owner)
        rows = self._q("SELECT role, content, importance, created FROM items WHERE session=? ORDER BY id", (sid,))
        data = json.dumps({"session": sid, "items": rows}, ensure_ascii=False)
        with open(path, "w", encoding="utf-8") as f:
            f.write(data)
        return hashlib.sha256(data.encode()).hexdigest()
