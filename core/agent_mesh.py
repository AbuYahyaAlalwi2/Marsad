"""agent_mesh.py — شبكة وكلاء مستقلة (لا تعتمد على Kaggle)."""
from __future__ import annotations
import os, json, time, sqlite3, threading, logging, traceback
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)
DB = Path(os.environ.get("CG_DB_PATH", str(__import__("pathlib").Path.home() / "marsad_mesh.db")))


@dataclass
class Task:
    id: int; kind: str; payload: dict
    attempts: int = 0; max_attempts: int = 5


class MeshDB:
    def __init__(self, path: Path = DB):
        self.path = path; self._init()

    def _conn(self):
        c = sqlite3.connect(str(self.path), timeout=30)
        c.row_factory = sqlite3.Row; return c

    def _init(self):
        with self._conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS tasks (
              id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, payload TEXT,
              status TEXT DEFAULT 'pending', attempts INTEGER DEFAULT 0,
              max_attempts INTEGER DEFAULT 5, result TEXT, error TEXT,
              created_at REAL, updated_at REAL)""")
            c.execute("CREATE INDEX IF NOT EXISTS idx_ks ON tasks(kind,status)")

    def push(self, kind, payload, max_attempts=5):
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO tasks(kind,payload,max_attempts,created_at,updated_at) VALUES(?,?,?,?,?)",
                (kind, json.dumps(payload), max_attempts, time.time(), time.time()))
            return cur.lastrowid

    def claim(self, kind):
        with self._conn() as c:
            row = c.execute("SELECT * FROM tasks WHERE kind=? AND status='pending' ORDER BY id LIMIT 1",
                            (kind,)).fetchone()
            if not row: return None
            c.execute("UPDATE tasks SET status='running',updated_at=? WHERE id=?",
                      (time.time(), row["id"]))
            return Task(row["id"], row["kind"], json.loads(row["payload"]),
                        row["attempts"], row["max_attempts"])

    def finish(self, tid, ok, result="", error=""):
        with self._conn() as c:
            r = c.execute("SELECT attempts,max_attempts FROM tasks WHERE id=?", (tid,)).fetchone()
            if not r: return
            att = r["attempts"] + 1
            if ok:
                c.execute("UPDATE tasks SET status='done',attempts=?,result=?,updated_at=? WHERE id=?",
                          (att, result, time.time(), tid))
            elif att >= r["max_attempts"]:
                c.execute("UPDATE tasks SET status='failed',attempts=?,error=?,updated_at=? WHERE id=?",
                          (att, error, time.time(), tid))
            else:
                c.execute("UPDATE tasks SET status='pending',attempts=?,error=?,updated_at=? WHERE id=?",
                          (att, error, time.time(), tid))

    def stats(self):
        with self._conn() as c:
            rows = c.execute("SELECT kind,status,COUNT(*) n FROM tasks GROUP BY kind,status").fetchall()
            out = {}
            for r in rows:
                out.setdefault(r["kind"], {})[r["status"]] = r["n"]
            return out

    def requeue_stuck(self, older_than=600):
        with self._conn() as c:
            c.execute("UPDATE tasks SET status='pending' WHERE status='running' AND updated_at < ?",
                      (time.time() - older_than,))


class Worker(threading.Thread):
    def __init__(self, name, kind, handler, db, stop, sleep_sec=2.0):
        super().__init__(daemon=True, name=name)
        self.kind=kind; self.handler=handler; self.db=db; self.stop=stop
        self.sleep_sec=sleep_sec; self.processed=0; self.errors=0

    def run(self):
        while not self.stop.is_set():
            try:
                t = self.db.claim(self.kind)
                if not t:
                    time.sleep(self.sleep_sec); continue
                try:
                    res = self.handler(t.payload)
                    self.db.finish(t.id, True, result=str(res)[:500])
                    self.processed += 1
                except Exception as e:
                    self.db.finish(t.id, False, error=f"{e} | {traceback.format_exc()[:400]}")
                    self.errors += 1
            except Exception:
                logger.exception("[mesh %s]", self.kind); time.sleep(2)


class AgentMesh:
    _inst = None
    def __new__(cls):
        if cls._inst is None:
            cls._inst = super().__new__(cls); cls._inst._init()
        return cls._inst

    def _init(self):
        self.db = MeshDB(); self._stop = threading.Event(); self._workers = []

    def register(self, kind, handler, count=4):
        for i in range(count):
            self._workers.append(Worker(f"{kind}-{i}", kind, handler, self.db, self._stop))

    def start(self):
        for w in self._workers:
            if not w.is_alive(): w.start()
        logger.info("[mesh] started %d workers", len(self._workers))

    def stop(self):
        self._stop.set()

    def submit(self, kind, payload, max_attempts=5):
        return self.db.push(kind, payload, max_attempts)

    def status(self):
        return {"workers": [{"name": w.name, "processed": w.processed,
                             "errors": w.errors, "alive": w.is_alive()}
                            for w in self._workers],
                "tasks": self.db.stats()}


mesh = AgentMesh()
