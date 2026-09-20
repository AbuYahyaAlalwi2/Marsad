"""
CYBERGUARD OS - Knowledge Sharing
Agents publish what they learn; others consume it. SQLite-backed.
"""
import time
import logging
import threading
import hashlib
from typing import Dict, List, Any

from db import get_conn, log_event
from config import KNOWLEDGE_SHARING_ENABLED, KNOWLEDGE_BACKEND

logger = logging.getLogger(__name__)


SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT UNIQUE NOT NULL,
    source_agent TEXT,
    confidence REAL DEFAULT 0.5,
    uses INTEGER DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_knowledge_topic ON knowledge(topic);
CREATE INDEX IF NOT EXISTS idx_knowledge_hash ON knowledge(content_hash);
"""


class KnowledgeBus:
    def __init__(self):
        self._lock = threading.Lock()
        self._ensure_schema()

    def _ensure_schema(self):
        try:
            with get_conn() as conn:
                conn.executescript(SCHEMA)
                conn.commit()
        except Exception as e:
            logger.error(f"[Knowledge] schema init failed: {e}")

    def publish(self, topic: str, content: str,
                source_agent: str = "unknown",
                confidence: float = 0.5) -> Dict[str, Any]:
        if not KNOWLEDGE_SHARING_ENABLED:
            return {"status": "disabled"}

        h = hashlib.sha256(f"{topic}|{content}".encode()).hexdigest()
        now = time.time()

        try:
            with get_conn() as conn:
                existing = conn.execute(
                    "SELECT id, confidence FROM knowledge WHERE content_hash = ?",
                    (h,)
                ).fetchone()

                if existing:
                    new_conf = (existing["confidence"] + confidence) / 2.0
                    conn.execute(
                        "UPDATE knowledge SET confidence = ?, updated_at = ? WHERE id = ?",
                        (new_conf, now, existing["id"])
                    )
                    conn.commit()
                    return {"status": "updated", "id": existing["id"],
                            "confidence": new_conf}

                cur = conn.execute(
                    "INSERT INTO knowledge "
                    "(topic, content, content_hash, source_agent, confidence, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (topic, content, h, source_agent, confidence, now, now)
                )
                conn.commit()

            try:
                log_event("knowledge", {"action": "published", "topic": topic,
                                        "source": source_agent})
            except Exception:
                pass
            return {"status": "created", "id": cur.lastrowid, "hash": h}

        except Exception as e:
            logger.error(f"[Knowledge] publish failed: {e}")
            return {"status": "error", "error": str(e)}

    def query(self, topic: str, limit: int = 10,
              min_confidence: float = 0.0) -> List[Dict]:
        try:
            with get_conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM knowledge "
                    "WHERE topic LIKE ? AND confidence >= ? "
                    "ORDER BY confidence DESC, uses ASC LIMIT ?",
                    (f"%{topic}%", min_confidence, limit)
                ).fetchall()
                result = [dict(r) for r in rows]
                for r in result:
                    conn.execute("UPDATE knowledge SET uses = uses + 1 WHERE id = ?",
                                 (r["id"],))
                conn.commit()
                return result
        except Exception as e:
            logger.error(f"[Knowledge] query failed: {e}")
            return []

    def search(self, text: str, limit: int = 10) -> List[Dict]:
        try:
            with get_conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM knowledge WHERE content LIKE ? OR topic LIKE ? "
                    "ORDER BY confidence DESC LIMIT ?",
                    (f"%{text}%", f"%{text}%", limit)
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[Knowledge] search failed: {e}")
            return []

    def stats(self) -> Dict[str, Any]:
        try:
            with get_conn() as conn:
                total = conn.execute("SELECT COUNT(*) as c FROM knowledge").fetchone()["c"]
                topics = conn.execute(
                    "SELECT topic, COUNT(*) as c FROM knowledge "
                    "GROUP BY topic ORDER BY c DESC LIMIT 20"
                ).fetchall()
                return {
                    "total_entries": total,
                    "top_topics": [dict(t) for t in topics],
                }
        except Exception as e:
            return {"error": str(e)}


knowledge_bus = KnowledgeBus()
