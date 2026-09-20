"""
قاعدة البيانات المركزية — SQLite محسنة مع منع التكرار
"""
import sqlite3
import json
import time
import os
import hashlib
import threading
from contextlib import contextmanager
from config import DB_PATH

# Auto-initialize database with thread safety
_db_lock = threading.Lock()
_initialized = False

def _ensure_db():
    """Ensure database is initialized - thread-safe"""
    global _initialized
    if not _initialized:
        with _db_lock:
            if not _initialized:
                init_db()
                _initialized = True

SCHEMA = """
CREATE TABLE IF NOT EXISTS memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    content_hash TEXT UNIQUE,
    embedding BLOB,
    metadata TEXT,
    created_at REAL NOT NULL,
    trained INTEGER DEFAULT 0,
    uploaded INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT UNIQUE NOT NULL,
    level INTEGER NOT NULL,
    parent_id TEXT,
    cloud_provider TEXT,
    status TEXT DEFAULT 'active',
    task_count INTEGER DEFAULT 0,
    created_at REAL NOT NULL,
    last_heartbeat REAL
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT UNIQUE NOT NULL,
    agent_id TEXT,
    task_type TEXT,
    payload TEXT,
    status TEXT DEFAULT 'pending',
    result TEXT,
    created_at REAL NOT NULL,
    completed_at REAL
);

CREATE TABLE IF NOT EXISTS samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sha256 TEXT UNIQUE NOT NULL,
    content TEXT NOT NULL,
    source TEXT,
    platform TEXT,
    language TEXT,
    sample_type TEXT,
    status TEXT DEFAULT 'pending',
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS datasets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    platform TEXT,
    description TEXT,
    url TEXT,
    size_mb REAL,
    downloaded INTEGER DEFAULT 0,
    processed INTEGER DEFAULT 0,
    created_at REAL NOT NULL,
    UNIQUE(name, platform)
);

CREATE TABLE IF NOT EXISTS api_providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_key TEXT UNIQUE NOT NULL,
    name TEXT,
    category TEXT,
    api_url TEXT,
    auth_type TEXT,
    env_key TEXT,
    api_key TEXT,
    status TEXT DEFAULT 'active',
    daily_limit INTEGER DEFAULT 1000,
    used_today INTEGER DEFAULT 0,
    last_reset_date TEXT,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS merges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    merge_id TEXT UNIQUE NOT NULL,
    base_model TEXT,
    models TEXT,
    output_path TEXT,
    status TEXT DEFAULT 'pending',
    created_at REAL NOT NULL,
    completed_at REAL
);

CREATE TABLE IF NOT EXISTS plugins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    path TEXT,
    hooks TEXT,
    enabled INTEGER DEFAULT 1,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT,
    payload TEXT,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    user_input TEXT NOT NULL,
    response TEXT,
    provider TEXT,
    model TEXT,
    metadata TEXT,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memory_hash ON memory(content_hash);
CREATE INDEX IF NOT EXISTS idx_datasets_platform ON datasets(platform);
CREATE INDEX IF NOT EXISTS idx_datasets_name ON datasets(name);
CREATE INDEX IF NOT EXISTS idx_api_providers_category ON api_providers(category);
CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id);

-- Secure API Keys Storage
CREATE TABLE IF NOT EXISTS secure_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_name TEXT UNIQUE NOT NULL,
    encrypted_value TEXT NOT NULL,
    key_type TEXT DEFAULT 'api_key',
    platform TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    last_used_at REAL,
    usage_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_secure_keys_name ON secure_keys(key_name);
CREATE INDEX IF NOT EXISTS idx_secure_keys_type ON secure_keys(key_type);
"""


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        conn.commit()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def log_event(channel: str, payload: dict):
    _ensure_db()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO events (channel, payload, created_at) VALUES (?, ?, ?)",
            (channel, json.dumps(payload, ensure_ascii=False), time.time())
        )
        conn.commit()


# —— Memory (مع منع التكرار) ——
def insert_memory(content: str, embedding: bytes = None, metadata: dict = None):
    """إدراج في الذاكرة مع منع التكرار باستخدام hash"""
    with get_conn() as conn:
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        # التحقق من وجود نفس المحتوى
        existing = conn.execute(
            "SELECT id FROM memory WHERE content_hash = ?", (content_hash,)
        ).fetchone()
        
        if existing:
            return existing["id"]
        
        cur = conn.execute(
            "INSERT INTO memory (content, content_hash, embedding, metadata, created_at) VALUES (?, ?, ?, ?, ?)",
            (content, content_hash, embedding, json.dumps(metadata or {}, ensure_ascii=False), time.time())
        )
        conn.commit()
        return cur.lastrowid


def get_untrained_memory(limit: int = 1000):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM memory WHERE trained = 0 ORDER BY created_at ASC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def mark_memory_trained(ids: list):
    if not ids:
        return
    with get_conn() as conn:
        placeholders = ",".join("?" * len(ids))
        conn.execute(
            f"UPDATE memory SET trained = 1 WHERE id IN ({placeholders})",
            ids
        )
        conn.commit()


def get_memory_size_gb() -> float:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT SUM(LENGTH(content) + LENGTH(COALESCE(embedding, ''))) as size FROM memory"
        ).fetchone()
        return (row["size"] or 0) / (1024**3)


def clear_trained_memory():
    with get_conn() as conn:
        conn.execute("DELETE FROM memory WHERE trained = 1 AND uploaded = 1")
        conn.commit()


# —— Agents ——
def insert_agent(agent_id: str, level: int, parent_id: str = None, cloud_provider: str = None):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO agents (agent_id, level, parent_id, cloud_provider, created_at) VALUES (?, ?, ?, ?, ?)",
            (agent_id, level, parent_id, cloud_provider, time.time())
        )
        conn.commit()


def get_agent(agent_id: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
        return dict(row) if row else None


def update_agent_status(agent_id: str, status: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE agents SET status = ?, last_heartbeat = ? WHERE agent_id = ?",
            (status, time.time(), agent_id)
        )
        conn.commit()


def count_agents_by_level(level: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as c FROM agents WHERE level = ?", (level,)
        ).fetchone()
        return row["c"]


# —— Tasks ——
def insert_task(task_id: str, agent_id: str, task_type: str, payload: dict):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO tasks (task_id, agent_id, task_type, payload, created_at) VALUES (?, ?, ?, ?, ?)",
            (task_id, agent_id, task_type, json.dumps(payload, ensure_ascii=False), time.time())
        )
        conn.commit()


def update_task_status(task_id: str, status: str, result: dict = None):
    with get_conn() as conn:
        conn.execute(
            "UPDATE tasks SET status = ?, result = ?, completed_at = ? WHERE task_id = ?",
            (status, json.dumps(result, ensure_ascii=False) if result else None, time.time(), task_id)
        )
        conn.commit()


# —— Samples ——
def insert_sample(sha256: str, content: str, source: str, platform: str, language: str, sample_type: str):
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO samples (sha256, content, source, platform, language, sample_type, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (sha256, content, source, platform, language, sample_type, time.time())
            )
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False


def get_pending_samples(limit: int = 100):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM samples WHERE status = 'pending' ORDER BY created_at ASC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def mark_sample_processed(ids: list, status: str = "processed"):
    if not ids:
        return
    with get_conn() as conn:
        placeholders = ",".join("?" * len(ids))
        conn.execute(
            f"UPDATE samples SET status = ? WHERE id IN ({placeholders})",
            [status] + ids
        )
        conn.commit()


# —— Datasets (مع منع التكرار) ——
def insert_dataset(name: str, platform: str, description: str = None, url: str = None, size_mb: float = None):
    """إدراج dataset مع منع التكرار"""
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO datasets (name, platform, description, url, size_mb, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (name, platform, description, url, size_mb, time.time())
            )
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False


def get_pending_datasets(limit: int = 50):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM datasets WHERE downloaded = 0 ORDER BY created_at ASC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def mark_dataset_downloaded(dataset_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE datasets SET downloaded = 1 WHERE id = ?", (dataset_id,))
        conn.commit()


# —— API Providers ——
def insert_api_provider(provider_key: str, name: str, category: str, api_url: str, auth_type: str, env_key: str, api_key: str = None, daily_limit: int = 1000):
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO api_providers
               (provider_key, name, category, api_url, auth_type, env_key, api_key, daily_limit, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (provider_key, name, category, api_url, auth_type, env_key, api_key, daily_limit, time.time())
        )
        conn.commit()


def get_api_provider(provider_key: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM api_providers WHERE provider_key = ?", (provider_key,)).fetchone()
        return dict(row) if row else None


def get_available_provider(category: str = None):
    today = time.strftime("%Y-%m-%d")
    query = "SELECT * FROM api_providers WHERE status = 'active' AND (last_reset_date != ? OR used_today < daily_limit)"
    params = [today]
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY used_today ASC LIMIT 1"

    with get_conn() as conn:
        row = conn.execute(query, params).fetchone()
        return dict(row) if row else None


def mark_provider_used(provider_key: str):
    today = time.strftime("%Y-%m-%d")
    with get_conn() as conn:
        conn.execute(
            """UPDATE api_providers
               SET used_today = CASE WHEN last_reset_date = ? THEN used_today + 1 ELSE 1 END,
                   last_reset_date = ?
               WHERE provider_key = ?""",
            (today, today, provider_key)
        )
        conn.commit()


def list_providers(category: str = None):
    query = "SELECT * FROM api_providers"
    params = []
    if category:
        query += " WHERE category = ?"
        params.append(category)
    query += " ORDER BY category, name"

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


# —— Merges ——
def insert_merge(merge_id: str, base_model: str, models: list, output_path: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO merges (merge_id, base_model, models, output_path, created_at) VALUES (?, ?, ?, ?, ?)",
            (merge_id, base_model, json.dumps(models, ensure_ascii=False), output_path, time.time())
        )
        conn.commit()


def update_merge_status(merge_id: str, status: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE merges SET status = ?, completed_at = ? WHERE merge_id = ?",
            (status, time.time(), merge_id)
        )
        conn.commit()


# —— Events ——
def get_recent_events(limit: int = 50):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM events ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


# —— Conversations (لتخزين المحادثات) ——
def insert_conversation(session_id: str, user_input: str, response: str, provider: str, model: str, metadata: dict = None):
    """إدراج محادثة في قاعدة البيانات"""
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO conversations (session_id, user_input, response, provider, model, metadata, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session_id, user_input, response, provider, model, json.dumps(metadata or {}, ensure_ascii=False), time.time())
        )
        conn.commit()


def get_conversation_history(session_id: str, limit: int = 50):
    """استرجاع تاريخ المحادثة"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM conversations WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
            (session_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_conversations(limit: int = 100):
    """استرجاع جميع المحادثات"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM conversations ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def clear_old_conversations(days: int = 30):
    """مسح المحادثات القديمة"""
    cutoff = time.time() - (days * 24 * 60 * 60)
    with get_conn() as conn:
        conn.execute("DELETE FROM conversations WHERE created_at < ?", (cutoff,))
        conn.commit()


# —— Cleanup Functions ——
def cleanup_duplicate_memory():
    """مسح البيانات المكررة في الذاكرة"""
    with get_conn() as conn:
        # حذف السجلات المكررة (احتفاظ بالأحدث)
        conn.execute("""
            DELETE FROM memory
            WHERE id NOT IN (
                SELECT MIN(id) FROM memory GROUP BY content_hash
            )
        """)
        conn.commit()


def cleanup_duplicate_datasets():
    """مسح datasets المكررة"""
    with get_conn() as conn:
        conn.execute("""
            DELETE FROM datasets
            WHERE id NOT IN (
                SELECT MIN(id) FROM datasets GROUP BY name, platform
            )
        """)
        conn.commit()


def get_database_stats() -> dict:
    """إحصائيات قاعدة البيانات"""
    with get_conn() as conn:
        stats = {}
        
        # عدد السجلات في كل جدول
        tables = ['memory', 'agents', 'tasks', 'samples', 'datasets', 'api_providers', 'merges', 'plugins', 'events', 'conversations']
        for table in tables:
            try:
                row = conn.execute(f"SELECT COUNT(*) as count FROM {table}").fetchone()
                stats[f"{table}_count"] = row["count"] if row else 0
            except:
                stats[f"{table}_count"] = 0
        
        # حجم قاعدة البيانات
        row = conn.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()").fetchone()
        stats["db_size_mb"] = (row["size"] or 0) / (1024 * 1024) if row else 0
        
        return stats

# ============================================================================
# Secure Keys Management Functions
# ============================================================================

def save_secure_key(key_name: str, encrypted_value: str, key_type: str = "api_key", platform: str = None) -> bool:
    """
    Save an encrypted API key to the database
    """
    try:
        with get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO secure_keys 
                   (key_name, encrypted_value, key_type, platform, created_at, updated_at)
                   VALUES (?, ?, ?, ?, COALESCE((SELECT created_at FROM secure_keys WHERE key_name = ?), ?), ?)""",
                (key_name, encrypted_value, key_type, platform, key_name, time.time(), time.time())
            )
            conn.commit()
            return True
    except Exception as e:
        log_event("secure_keys", {"action": "save", "error": str(e), "key_name": key_name})
        return False

def get_secure_key(key_name: str) -> dict:
    """
    Get an encrypted API key from the database
    """
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM secure_keys WHERE key_name = ?", (key_name,)
            ).fetchone()
            return dict(row) if row else None
    except Exception as e:
        log_event("secure_keys", {"action": "get", "error": str(e), "key_name": key_name})
        return None

def delete_secure_key(key_name: str) -> bool:
    """
    Delete an API key from the database
    """
    try:
        with get_conn() as conn:
            conn.execute("DELETE FROM secure_keys WHERE key_name = ?", (key_name,))
            conn.commit()
            return True
    except Exception as e:
        log_event("secure_keys", {"action": "delete", "error": str(e), "key_name": key_name})
        return False

def list_secure_keys() -> list:
    """
    List all stored API keys
    """
    try:
        with get_conn() as conn:
            rows = conn.execute("SELECT key_name, key_type, platform, created_at FROM secure_keys ORDER BY key_name").fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        log_event("secure_keys", {"action": "list", "error": str(e)})
        return []

def update_secure_key_usage(key_name: str) -> bool:
    """
    Update usage statistics for an API key
    """
    try:
        with get_conn() as conn:
            conn.execute(
                """UPDATE secure_keys 
                   SET last_used_at = ?, usage_count = usage_count + 1
                   WHERE key_name = ?""",
                (time.time(), key_name)
            )
            conn.commit()
            return True
    except Exception as e:
        log_event("secure_keys", {"action": "update_usage", "error": str(e), "key_name": key_name})
        return False
