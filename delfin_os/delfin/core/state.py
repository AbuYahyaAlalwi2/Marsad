"""مدير الحالة: حالة النظام والوكلاء والمهام (SQLite)."""
import json
import sqlite3
import threading
import time
import uuid

TASK_STATES = ("pending", "running", "done", "failed", "timeout", "rejected")
SYSTEM_STATES = ("running", "idle", "error", "maintenance")


class StateManager:
    def __init__(self, path=":memory:", redactor=lambda s: s):
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        self._redact = redactor
        with self._lock:
            self._db.executescript("""
            CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, kind TEXT, owner TEXT,
              payload TEXT, status TEXT, result TEXT, error TEXT, created REAL, updated REAL);
            CREATE TABLE IF NOT EXISTS agents(name TEXT PRIMARY KEY, status TEXT, version TEXT, updated REAL);
            CREATE TABLE IF NOT EXISTS system(k TEXT PRIMARY KEY, v TEXT);
            """)
            self._db.commit()
        self.set_system("state", "idle")

    def _exec(self, sql, args=()):
        with self._lock:
            self._db.execute(sql, args)
            self._db.commit()

    def _q(self, sql, args=()):
        with self._lock:
            return self._db.execute(sql, args).fetchall()

    def set_system(self, k, v):
        if k == "state" and v not in SYSTEM_STATES:
            raise ValueError("حالة نظام غير صالحة")
        self._exec("INSERT INTO system(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, str(v)))

    def get_system(self, k, default=None):
        rows = self._q("SELECT v FROM system WHERE k=?", (k,))
        return rows[0][0] if rows else default

    def upsert_agent(self, name, status, version=""):
        self._exec("INSERT INTO agents(name,status,version,updated) VALUES(?,?,?,?) "
                   "ON CONFLICT(name) DO UPDATE SET status=excluded.status, version=excluded.version, updated=excluded.updated",
                   (name, status, version, time.time()))

    def agents(self):
        return [{"name": r[0], "status": r[1], "version": r[2], "updated": r[3]}
                for r in self._q("SELECT name,status,version,updated FROM agents ORDER BY name")]

    def create_task(self, kind, owner, payload):
        tid = uuid.uuid4().hex[:12]
        body = self._redact(json.dumps(payload, ensure_ascii=False, default=str))[:4000]
        now = time.time()
        self._exec("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?)",
                   (tid, kind, owner, body, "pending", None, None, now, now))
        return tid

    def update_task(self, tid, status, result=None, error=None):
        if status not in TASK_STATES:
            raise ValueError("حالة مهمة غير صالحة")
        res = None if result is None else self._redact(json.dumps(result, ensure_ascii=False, default=str))[:8000]
        err = None if error is None else self._redact(str(error))[:500]
        self._exec("UPDATE tasks SET status=?, result=?, error=?, updated=? WHERE id=?",
                   (status, res, err, time.time(), tid))

    @staticmethod
    def _row(r):
        return {"id": r[0], "kind": r[1], "owner": r[2], "status": r[4], "error": r[6],
                "created": r[7], "updated": r[8]}

    def get_task(self, tid, owner=None):
        rows = self._q("SELECT * FROM tasks WHERE id=?", (tid,))
        if not rows or (owner is not None and rows[0][2] != owner):
            return None
        d = self._row(rows[0])
        d["result"] = rows[0][5]
        return d

    def list_tasks(self, limit=50, owner=None):
        limit = max(1, min(int(limit), 200))
        if owner is None:
            rows = self._q("SELECT * FROM tasks ORDER BY created DESC LIMIT ?", (limit,))
        else:
            rows = self._q("SELECT * FROM tasks WHERE owner=? ORDER BY created DESC LIMIT ?", (owner, limit))
        return [self._row(r) for r in rows]

    def counts(self):
        return dict(self._q("SELECT status, COUNT(*) FROM tasks GROUP BY status"))
