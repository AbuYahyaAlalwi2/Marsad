"""
Knowledge Store — قاعدة المعرفة الأمنية المركزية
يحفظ: CVEs، اكتشافات النموذج، أخطاءه، والدروس المستفادة
"""

import json
import sqlite3
import hashlib
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, List
from enum import Enum

# ─── Constants ────────────────────────────────────────────────────────────────

BASE_DIR  = Path(__file__).parent.parent
DB_PATH   = BASE_DIR / "database" / "marsad.db"
JSONL_DIR = BASE_DIR / "database" / "jsonl"

JSONL_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


# ─── Data Types ───────────────────────────────────────────────────────────────

class Severity(str, Enum):
    CRITICAL = "CRITICAL"   # CVSS 9.0-10.0
    HIGH     = "HIGH"       # CVSS 7.0-8.9
    MEDIUM   = "MEDIUM"     # CVSS 4.0-6.9
    LOW      = "LOW"        # CVSS 0.1-3.9
    NONE     = "NONE"       # CVSS 0.0

class RecordType(str, Enum):
    CVE          = "CVE"           # ثغرة من NVD/GitHub
    DISCOVERY    = "DISCOVERY"     # اكتشاف النموذج نفسه
    MODEL_ERROR  = "MODEL_ERROR"   # خطأ ارتكبه النموذج
    LESSON       = "LESSON"        # درس مستفاد من خطأ
    PATCH        = "PATCH"         # تصحيح تم التحقق منه

@dataclass
class SecurityRecord:
    """السجل الموحد لكل ما يعرفه النموذج"""
    record_id:       str            # SHA256 فريد
    record_type:     RecordType
    cve_id:          Optional[str]  # CVE-2024-xxxx أو None
    severity:        Severity
    cvss_score:      float          # 0.0 - 10.0
    title:           str
    description:     str
    vulnerable_code: str            # الكود المصاب
    fixed_code:      str            # الكود المصلح
    explanation:     str            # شرح الثغرة والإصلاح
    cwe_ids:         List[str]      # ['CWE-79', 'CWE-89']
    affected_langs:  List[str]      # ['python', 'javascript']
    source:          str            # NVD / GitHub / MODEL_DISCOVERY
    verified:        bool           # هل تم التحقق منه؟
    false_positive:  bool           # هل كان خطأ؟ (درس مهم)
    timestamp:       float
    metadata:        dict           # أي بيانات إضافية

    @staticmethod
    def make_id(content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()[:16]


# ─── Database ─────────────────────────────────────────────────────────────────

class KnowledgeStore:
    """
    قاعدة المعرفة المركزية
    - تمنع التكرار تلقائياً
    - تتتبع أخطاء النموذج لمنع تكرارها
    - تصدر JSONL للتدريب
    """

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS records (
                    record_id       TEXT PRIMARY KEY,
                    record_type     TEXT NOT NULL,
                    cve_id          TEXT UNIQUE,
                    severity        TEXT NOT NULL,
                    cvss_score      REAL DEFAULT 0.0,
                    title           TEXT NOT NULL,
                    description     TEXT,
                    vulnerable_code TEXT DEFAULT '',
                    fixed_code      TEXT DEFAULT '',
                    explanation     TEXT DEFAULT '',
                    cwe_ids         TEXT DEFAULT '[]',
                    affected_langs  TEXT DEFAULT '[]',
                    source          TEXT NOT NULL,
                    verified        INTEGER DEFAULT 0,
                    false_positive  INTEGER DEFAULT 0,
                    timestamp       REAL NOT NULL,
                    metadata        TEXT DEFAULT '{}'
                );

                -- أخطاء النموذج — لا يكررها أبداً
                CREATE TABLE IF NOT EXISTS model_errors (
                    error_id        TEXT PRIMARY KEY,
                    error_type      TEXT NOT NULL,
                    context         TEXT NOT NULL,
                    wrong_answer    TEXT NOT NULL,
                    correct_answer  TEXT NOT NULL,
                    lesson          TEXT NOT NULL,
                    cve_related     TEXT,
                    timestamp       REAL NOT NULL,
                    times_repeated  INTEGER DEFAULT 0
                );

                -- اكتشافات النموذج الجديدة
                CREATE TABLE IF NOT EXISTS discoveries (
                    discovery_id    TEXT PRIMARY KEY,
                    target_code     TEXT NOT NULL,
                    finding         TEXT NOT NULL,
                    confidence      REAL NOT NULL,
                    verified        INTEGER DEFAULT 0,
                    verifier        TEXT,
                    timestamp       REAL NOT NULL
                );

                -- فهارس للبحث السريع
                CREATE INDEX IF NOT EXISTS idx_severity  ON records(severity);
                CREATE INDEX IF NOT EXISTS idx_cvss      ON records(cvss_score DESC);
                CREATE INDEX IF NOT EXISTS idx_type      ON records(record_type);
                CREATE INDEX IF NOT EXISTS idx_verified  ON records(verified);
                CREATE INDEX IF NOT EXISTS idx_langs     ON records(affected_langs);
            """)

    def _conn(self):
        return sqlite3.connect(self.db_path)

    # ── الحفظ ─────────────────────────────────────────────────────────────────

    def save(self, record: SecurityRecord) -> bool:
        """
        يحفظ السجل — يرفض التكرار تلقائياً
        Returns: True إذا حُفظ جديد، False إذا كان موجوداً
        """
        try:
            with self._conn() as conn:
                conn.execute("""
                    INSERT INTO records VALUES (
                        ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                    )
                """, (
                    record.record_id,
                    record.record_type.value,
                    record.cve_id,
                    record.severity.value,
                    record.cvss_score,
                    record.title,
                    record.description,
                    record.vulnerable_code,
                    record.fixed_code,
                    record.explanation,
                    json.dumps(record.cwe_ids),
                    json.dumps(record.affected_langs),
                    record.source,
                    int(record.verified),
                    int(record.false_positive),
                    record.timestamp,
                    json.dumps(record.metadata),
                ))
            return True
        except sqlite3.IntegrityError:
            return False  # موجود مسبقاً

    def log_error(
        self,
        error_type:     str,
        context:        str,
        wrong_answer:   str,
        correct_answer: str,
        lesson:         str,
        cve_related:    str = None,
    ) -> str:
        """
        يسجل خطأ النموذج — حتى لا يكرره
        هذا أهم من البيانات الخارجية: النموذج يتعلم من أخطائه الخاصة
        """
        error_id = SecurityRecord.make_id(f"{error_type}:{context}:{wrong_answer}")

        with self._conn() as conn:
            existing = conn.execute(
                "SELECT times_repeated FROM model_errors WHERE error_id=?",
                (error_id,)
            ).fetchone()

            if existing:
                # زاد عدد المرات
                conn.execute(
                    "UPDATE model_errors SET times_repeated=times_repeated+1 WHERE error_id=?",
                    (error_id,)
                )
                return error_id

            conn.execute("""
                INSERT INTO model_errors VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                error_id, error_type, context, wrong_answer,
                correct_answer, lesson, cve_related, time.time(), 0
            ))

        return error_id

    def log_discovery(
        self,
        target_code: str,
        finding:     str,
        confidence:  float,
    ) -> str:
        """يسجل اكتشاف النموذج لثغرة جديدة — في انتظار التحقق البشري"""
        disc_id = SecurityRecord.make_id(f"{target_code}:{finding}")

        with self._conn() as conn:
            try:
                conn.execute("""
                    INSERT INTO discoveries VALUES (?,?,?,?,?,?,?)
                """, (disc_id, target_code, finding, confidence, 0, None, time.time()))
            except sqlite3.IntegrityError:
                pass  # موجود

        return disc_id

    def verify_discovery(self, discovery_id: str, verifier: str, is_valid: bool):
        """المراجع البشري يؤكد أو يرفض الاكتشاف"""
        with self._conn() as conn:
            conn.execute("""
                UPDATE discoveries SET verified=?, verifier=? WHERE discovery_id=?
            """, (int(is_valid), verifier, discovery_id))

    # ── الاستعلام ─────────────────────────────────────────────────────────────

    def exists(self, cve_id: str) -> bool:
        """هل هذا CVE موجود مسبقاً؟"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM records WHERE cve_id=?", (cve_id,)
            ).fetchone()
        return row is not None

    def get_errors_for_context(self, context: str, limit: int = 5) -> List[dict]:
        """
        يجلب أخطاء مشابهة لسياق معين
        النموذج يستدعي هذا قبل كل تحليل لتجنب الأخطاء القديمة
        """
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT error_type, wrong_answer, correct_answer, lesson, times_repeated
                FROM model_errors
                WHERE context LIKE ?
                ORDER BY times_repeated DESC
                LIMIT ?
            """, (f"%{context[:50]}%", limit)).fetchall()

        return [
            {
                "error_type":     r[0],
                "wrong_answer":   r[1],
                "correct_answer": r[2],
                "lesson":         r[3],
                "times_repeated": r[4],
            }
            for r in rows
        ]

    def get_by_severity(self, severity: Severity, limit: int = 100) -> List[dict]:
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM records WHERE severity=? ORDER BY cvss_score DESC LIMIT ?
            """, (severity.value, limit)).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_unverified_discoveries(self) -> List[dict]:
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM discoveries WHERE verified=0 ORDER BY confidence DESC
            """).fetchall()
        return [
            {"id": r[0], "code": r[1][:100]+"...", "finding": r[2], "confidence": r[3]}
            for r in rows
        ]

    def stats(self) -> dict:
        with self._conn() as conn:
            total    = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
            by_sev   = conn.execute(
                "SELECT severity, COUNT(*) FROM records GROUP BY severity"
            ).fetchall()
            errors   = conn.execute("SELECT COUNT(*) FROM model_errors").fetchone()[0]
            disc     = conn.execute("SELECT COUNT(*) FROM discoveries").fetchone()[0]
            verified = conn.execute(
                "SELECT COUNT(*) FROM discoveries WHERE verified=1"
            ).fetchone()[0]

        return {
            "total_records":       total,
            "by_severity":         dict(by_sev),
            "model_errors_logged": errors,
            "discoveries":         disc,
            "verified_discoveries": verified,
        }

    # ── التصدير للتدريب ───────────────────────────────────────────────────────

    def export_training_jsonl(
        self,
        output_path: Path = None,
        min_cvss:    float = 0.0,
        verified_only: bool = True,
    ) -> Path:
        """
        يصدر بيانات التدريب بتنسيق JSONL موحد
        فقط السجلات المحققة والمكتملة
        """
        output = output_path or (JSONL_DIR / f"training_{int(time.time())}.jsonl")

        with self._conn() as conn:
            query = """
                SELECT vulnerable_code, fixed_code, cve_id, severity,
                       cvss_score, explanation, cwe_ids, title
                FROM records
                WHERE cvss_score >= ?
                  AND vulnerable_code != ''
                  AND fixed_code != ''
                  AND explanation != ''
                  {}
                ORDER BY cvss_score DESC
            """.format("AND verified=1" if verified_only else "")

            rows = conn.execute(query, (min_cvss,)).fetchall()

        count = 0
        with open(output, "w", encoding="utf-8") as f:
            for r in rows:
                record = {
                    "vulnerable_code": r[0],
                    "fixed_code":      r[1],
                    "cve_id":          r[2],
                    "severity":        r[3],
                    "cvss_score":      r[4],
                    "explanation":     r[5],
                    "cwe_ids":         json.loads(r[6]),
                    "title":           r[7],
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                count += 1

        print(f"✓ صُدِّر {count} سجل تدريب → {output}")
        return output

    def export_errors_jsonl(self, output_path: Path = None) -> Path:
        """يصدر أخطاء النموذج كبيانات تدريب سلبية (تعلم من الأخطاء)"""
        output = output_path or (JSONL_DIR / f"errors_{int(time.time())}.jsonl")

        with self._conn() as conn:
            rows = conn.execute("""
                SELECT error_type, context, wrong_answer, correct_answer, lesson
                FROM model_errors ORDER BY times_repeated DESC
            """).fetchall()

        with open(output, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps({
                    "error_type":     r[0],
                    "context":        r[1],
                    "wrong_answer":   r[2],
                    "correct_answer": r[3],
                    "lesson":         r[4],
                }, ensure_ascii=False) + "\n")

        print(f"✓ صُدِّر {len(rows)} خطأ للتعلم → {output}")
        return output

    # ── داخلي ─────────────────────────────────────────────────────────────────

    def _row_to_dict(self, row) -> dict:
        keys = [
            "record_id", "record_type", "cve_id", "severity", "cvss_score",
            "title", "description", "vulnerable_code", "fixed_code",
            "explanation", "cwe_ids", "affected_langs", "source",
            "verified", "false_positive", "timestamp", "metadata"
        ]
        d = dict(zip(keys, row))
        d["cwe_ids"]       = json.loads(d["cwe_ids"])
        d["affected_langs"] = json.loads(d["affected_langs"])
        d["metadata"]      = json.loads(d["metadata"])
        return d


# ─── Singleton ────────────────────────────────────────────────────────────────

_store: Optional[KnowledgeStore] = None

def get_store() -> KnowledgeStore:
    global _store
    if _store is None:
        _store = KnowledgeStore()
    return _store
