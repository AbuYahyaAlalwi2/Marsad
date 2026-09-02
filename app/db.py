"""
طبقة التخزين الدائم لمرصد (Marsad).
تستبدل الاعتماد على st.session_state بقاعدة SQLite دائمة على القرص،
حتى لا تُفقد البيانات عند إعادة تشغيل التطبيق (نقطة الضعف الأولى
التي حُدّدت في تصميم النظام السابق).
"""

import sqlite3
import json
import os
import time
from contextlib import contextmanager

DB_PATH = os.environ.get("MARSAD_DB_PATH", "data/marsad.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL,      -- Research / Engineering / Governance / Learning / Reliability / Custom
    agent_type TEXT NOT NULL,
    clone_count INTEGER DEFAULT 1,
    status TEXT DEFAULT 'active', -- active / isolated / retired
    created_at REAL NOT NULL,
    isolated_at REAL
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,
    agent_group_id INTEGER,
    status TEXT DEFAULT 'pending', -- pending / running / done / failed
    payload_json TEXT,
    created_at REAL NOT NULL,
    updated_at REAL,
    FOREIGN KEY(agent_group_id) REFERENCES agent_groups(id)
);

CREATE TABLE IF NOT EXISTS samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sha256 TEXT UNIQUE NOT NULL,
    content TEXT NOT NULL,
    source_url TEXT,
    license TEXT,
    language TEXT,
    provenance_json TEXT,
    status TEXT DEFAULT 'pending_review',
    -- pending_review / passed_sandbox / rejected / approved_for_training
    reject_reason TEXT,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS training_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_count INTEGER,
    created_at REAL NOT NULL,
    status TEXT DEFAULT 'queued'
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT NOT NULL,
    payload_json TEXT,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS sitemap_failures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,
    reason TEXT,
    created_at REAL NOT NULL
);
"""


def init_db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        conn.commit()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def log_event(channel: str, payload: dict):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO events (channel, payload_json, created_at) VALUES (?, ?, ?)",
            (channel, json.dumps(payload, ensure_ascii=False), time.time()),
        )
        conn.commit()


def insert_sample(sha256, content, source_url, license_, language, provenance, status="pending_review", reject_reason=None):
    """يُرجع True لو أُدرجت، False لو كانت مكررة (unique constraint على sha256)."""
    try:
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO samples
                   (sha256, content, source_url, license, language, provenance_json, status, reject_reason, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (sha256, content, source_url, license_, language,
                 json.dumps(provenance, ensure_ascii=False), status, reject_reason, time.time()),
            )
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False  # عينة مكررة فعلياً — dedup تلقائي عبر القاعدة نفسها


def create_agent_group(name, category, agent_type, clone_count=1):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO agent_groups (name, category, agent_type, clone_count, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, category, agent_type, clone_count, time.time()),
        )
        conn.commit()
        return cur.lastrowid


def list_agent_groups():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM agent_groups ORDER BY category, name")]


def list_recent_samples(limit=50):
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM samples ORDER BY created_at DESC LIMIT ?", (limit,)
        )]


def sample_counts_by_status():
    with get_conn() as conn:
        rows = conn.execute("SELECT status, COUNT(*) c FROM samples GROUP BY status").fetchall()
        return {r["status"]: r["c"] for r in rows}


def recent_events(limit=30):
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM events ORDER BY created_at DESC LIMIT ?", (limit,)
        )]
