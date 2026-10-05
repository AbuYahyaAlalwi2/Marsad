"""
agent_output_pipeline.py — خط أنابيب مخرجات الوكلاء
======================================================
يستقبل ما ينتجه كل وكيل في ~/Marsad/agents/ ويحفظه في KnowledgeStore.

❌ لا يلمس ملفات الوكلاء
✅ يراقب مجلدات الخرج → يعالج → يحفظ → يصدّر للتدريب

مسار العمل:
    collector_agent  → ينتج: codes/*, cves/*, fixes/*
    agent_output_pipeline → يقرأ المجلدات → يعالج → KnowledgeStore → JSONL

الاستخدام:
    # تشغيل مستمر (watch mode)
    python agent_output_pipeline.py --watch

    # معالجة واحدة
    python agent_output_pipeline.py --once

    # معالجة مجلد محدد
    python agent_output_pipeline.py --dir ~/Marsad/output/codes
"""

import asyncio
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# ─── المسارات ─────────────────────────────────────────────────────────────────

# مجلدات الخرج التي تنتجها الوكلاء (خارج marsad_security)
_AGENT_OUTPUT_DIRS = {
    "codes":        Path.home() / "Marsad" / "output" / "codes",
    "cves":         Path.home() / "Marsad" / "output" / "cves",
    "fixes":        Path.home() / "Marsad" / "output" / "fixes",
    "filtered":     Path.home() / "Marsad" / "output" / "filtered",
    "advisories":   Path.home() / "Marsad" / "output" / "advisories",
}

# قاعدة معرفة مرصد
_STORE_DIR  = Path(__file__).parent.parent / "database"
_STORE_DB   = _STORE_DIR / "knowledge.db"
_JSONL_OUT  = _STORE_DIR / "training_data.jsonl"
_PROCESSED  = _STORE_DIR / "processed_files.json"   # ملفات تمت معالجتها


# ─── أنواع السجلات ─────────────────────────────────────────────────────────────

@dataclass
class ProcessedRecord:
    record_id:   str    # SHA256 للمحتوى
    source_file: str    # المسار الأصلي
    record_type: str    # code | cve | fix | advisory
    content:     str    # المحتوى الخام
    severity:    float  # CVSS 0-10
    language:    str    # python | js | sql | unknown
    timestamp:   str


# ─── معالجة الأنواع المختلفة ───────────────────────────────────────────────────

class RecordProcessor:
    """يحوّل ملف خام من مجلد الوكيل إلى ProcessedRecord"""

    # ─── كشف اللغة ─────────────────────────────────────────────
    _LANG_SIGNATURES = {
        "python":     [r"def\s+\w+", r"import\s+\w+", r"class\s+\w+", r"print\("],
        "javascript": [r"function\s+\w+", r"const\s+\w+\s*=", r"require\(", r"=>"],
        "sql":        [r"SELECT\s+", r"INSERT\s+INTO", r"DROP\s+TABLE", r"UNION\s+SELECT"],
        "bash":       [r"#!/bin/bash", r"\$\(", r"chmod\s+", r"sudo\s+"],
        "php":        [r"<\?php", r"\$_GET\[", r"\$_POST\["],
        "c":          [r"#include\s*<", r"int\s+main\(", r"malloc\(", r"printf\("],
    }

    def detect_language(self, code: str) -> str:
        scores = {}
        for lang, patterns in self._LANG_SIGNATURES.items():
            score = sum(1 for p in patterns if re.search(p, code, re.IGNORECASE))
            if score > 0:
                scores[lang] = score
        return max(scores, key=scores.get) if scores else "unknown"

    def estimate_severity(self, content: str, record_type: str) -> float:
        """تقدير CVSS بدون API — بناءً على الكلمات المفتاحية"""
        HIGH_RISK = [
            "remote code execution", "rce", "command injection",
            "sql injection", "authentication bypass", "privilege escalation",
            "arbitrary code", "os.system", "eval(", "exec(", "subprocess",
            "DROP TABLE", "UNION SELECT", "__import__"
        ]
        MEDIUM_RISK = [
            "xss", "cross-site", "csrf", "path traversal", "../",
            "open redirect", "ssrf", "information disclosure"
        ]
        LOW_RISK = [
            "brute force", "rate limit", "clickjacking",
            "outdated", "deprecated", "weak password"
        ]

        content_lower = content.lower()
        high  = sum(1 for k in HIGH_RISK   if k.lower() in content_lower)
        med   = sum(1 for k in MEDIUM_RISK if k.lower() in content_lower)
        low   = sum(1 for k in LOW_RISK    if k.lower() in content_lower)

        if high >= 2:   return 9.0
        if high == 1:   return 7.5
        if med >= 2:    return 6.0
        if med == 1:    return 4.5
        if low >= 1:    return 2.5
        return 1.0

    def process_code_file(self, path: Path) -> Optional[ProcessedRecord]:
        """معالجة ملف كود — من مجلد codes/"""
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            if len(content.strip()) < 10:
                return None

            rid = hashlib.sha256(content.encode()).hexdigest()[:16]
            return ProcessedRecord(
                record_id   = rid,
                source_file = str(path),
                record_type = "code",
                content     = content,
                severity    = self.estimate_severity(content, "code"),
                language    = self.detect_language(content),
                timestamp   = datetime.utcnow().isoformat(),
            )
        except Exception as e:
            print(f"  ⚠ خطأ في {path.name}: {e}")
            return None

    def process_cve_file(self, path: Path) -> Optional[ProcessedRecord]:
        """معالجة ملف CVE — قد يكون JSON أو نص"""
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            severity = 5.0  # افتراضي

            # حاول قراءة CVSS من JSON
            try:
                data = json.loads(content)
                # تنسيق NVD
                if "cve" in data:
                    metrics = data.get("cve", {}).get("metrics", {})
                    cvss_v3 = metrics.get("cvssMetricV31", [{}])
                    if cvss_v3:
                        severity = float(cvss_v3[0].get("cvssData", {}).get("baseScore", 5.0))
                # تنسيق GitHub Advisory
                elif "severity" in data:
                    sev_map = {"CRITICAL": 9.5, "HIGH": 7.5, "MEDIUM": 5.0, "LOW": 2.5}
                    severity = sev_map.get(data["severity"].upper(), 5.0)
                # تنسيق مبسط
                elif "cvss_score" in data:
                    severity = float(data["cvss_score"])
            except (json.JSONDecodeError, KeyError, TypeError):
                severity = self.estimate_severity(content, "cve")

            rid = hashlib.sha256(content.encode()).hexdigest()[:16]
            return ProcessedRecord(
                record_id   = rid,
                source_file = str(path),
                record_type = "cve",
                content     = content,
                severity    = severity,
                language    = "unknown",
                timestamp   = datetime.utcnow().isoformat(),
            )
        except Exception as e:
            print(f"  ⚠ خطأ في {path.name}: {e}")
            return None

    def process_fix_file(self, path: Path) -> Optional[ProcessedRecord]:
        """معالجة ملف إصلاح — patch أو diff أو كود محسّن"""
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            rid = hashlib.sha256(content.encode()).hexdigest()[:16]
            return ProcessedRecord(
                record_id   = rid,
                source_file = str(path),
                record_type = "fix",
                content     = content,
                severity    = self.estimate_severity(content, "fix"),
                language    = self.detect_language(content),
                timestamp   = datetime.utcnow().isoformat(),
            )
        except Exception as e:
            print(f"  ⚠ خطأ في {path.name}: {e}")
            return None

    def process_advisory_file(self, path: Path) -> Optional[ProcessedRecord]:
        """معالجة تحذير أمني"""
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            rid = hashlib.sha256(content.encode()).hexdigest()[:16]
            return ProcessedRecord(
                record_id   = rid,
                source_file = str(path),
                record_type = "advisory",
                content     = content,
                severity    = self.estimate_severity(content, "advisory"),
                language    = "unknown",
                timestamp   = datetime.utcnow().isoformat(),
            )
        except Exception as e:
            print(f"  ⚠ خطأ في {path.name}: {e}")
            return None

    def process_file(self, path: Path, folder_type: str) -> Optional[ProcessedRecord]:
        """الدخول الرئيسي — يختار المعالج حسب نوع المجلد"""
        handlers = {
            "codes":      self.process_code_file,
            "cves":       self.process_cve_file,
            "fixes":      self.process_fix_file,
            "filtered":   self.process_code_file,    # نفس معالجة الكود
            "advisories": self.process_advisory_file,
        }
        handler = handlers.get(folder_type, self.process_code_file)
        return handler(path)


# ─── حفظ في KnowledgeStore ─────────────────────────────────────────────────────

class AgentOutputSink:
    """يحفظ ProcessedRecord في KnowledgeStore وملف JSONL"""

    def __init__(self):
        _STORE_DIR.mkdir(parents=True, exist_ok=True)
        self._processed = self._load_processed()
        self._init_db()

    def _init_db(self):
        """تهيئة قاعدة البيانات"""
        import sqlite3
        with sqlite3.connect(_STORE_DB) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_records (
                    record_id   TEXT PRIMARY KEY,
                    source_file TEXT,
                    record_type TEXT,
                    content     TEXT,
                    severity    REAL,
                    language    TEXT,
                    timestamp   TEXT
                )
            """)
            conn.commit()

    def _load_processed(self) -> set:
        if _PROCESSED.exists():
            try:
                return set(json.loads(_PROCESSED.read_text()))
            except Exception:
                pass
        return set()

    def _save_processed(self):
        _PROCESSED.write_text(json.dumps(list(self._processed)))

    def already_processed(self, path: Path) -> bool:
        return str(path) in self._processed

    def mark_processed(self, path: Path):
        self._processed.add(str(path))

    def save_record(self, record: ProcessedRecord) -> bool:
        """يحفظ في SQLite + JSONL — يتجاهل المكرر"""
        import sqlite3
        try:
            with sqlite3.connect(_STORE_DB) as conn:
                conn.execute("""
                    INSERT OR IGNORE INTO agent_records
                    VALUES (?,?,?,?,?,?,?)
                """, (
                    record.record_id,
                    record.source_file,
                    record.record_type,
                    record.content,
                    record.severity,
                    record.language,
                    record.timestamp,
                ))
                conn.commit()

            # تصدير كـ JSONL للتدريب
            self._append_jsonl(record)
            return True
        except Exception as e:
            print(f"  ✗ خطأ في الحفظ: {e}")
            return False

    def _append_jsonl(self, record: ProcessedRecord):
        """يحوّل السجل إلى صيغة تدريب ويضيفه للملف"""
        training_entry = self._to_training_format(record)
        with open(_JSONL_OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps(training_entry, ensure_ascii=False) + "\n")

    def _to_training_format(self, record: ProcessedRecord) -> dict:
        """يحوّل السجل إلى تنسيق instruction-following للتدريب"""
        type_prompts = {
            "code": (
                f"افحص هذا الكود {record.language} وحدد الثغرات الأمنية:",
                "تحليل الثغرات الأمنية"
            ),
            "cve": (
                "اشرح هذه الثغرة الأمنية وطريقة استغلالها والدفاع عنها:",
                "تحليل CVE"
            ),
            "fix": (
                "اشرح كيف يصلح هذا الكود الثغرة الأمنية:",
                "شرح الإصلاح"
            ),
            "advisory": (
                "حلل هذا التحذير الأمني وقدم توصيات:",
                "تحليل التحذير"
            ),
        }
        prompt, task_type = type_prompts.get(record.record_type, ("حلل هذا:", "تحليل"))

        return {
            "id":          record.record_id,
            "type":        record.record_type,
            "severity":    record.severity,
            "language":    record.language,
            "source":      record.source_file,
            "timestamp":   record.timestamp,
            "messages": [
                {"role": "user",      "content": f"{prompt}\n\n{record.content}"},
                {"role": "assistant", "content": f"[{task_type} — CVSS: {record.severity}]"},
            ]
        }

    def get_stats(self) -> dict:
        """إحصائيات قاعدة المعرفة"""
        import sqlite3
        try:
            with sqlite3.connect(_STORE_DB) as conn:
                total = conn.execute("SELECT COUNT(*) FROM agent_records").fetchone()[0]
                by_type = dict(conn.execute(
                    "SELECT record_type, COUNT(*) FROM agent_records GROUP BY record_type"
                ).fetchall())
                avg_sev = conn.execute("SELECT AVG(severity) FROM agent_records").fetchone()[0] or 0
            return {
                "total":        total,
                "by_type":      by_type,
                "avg_severity": round(avg_sev, 2),
                "jsonl_size":   _JSONL_OUT.stat().st_size if _JSONL_OUT.exists() else 0,
            }
        except Exception:
            return {}


# ─── المعالج الرئيسي ───────────────────────────────────────────────────────────

class AgentOutputPipeline:
    """
    يراقب مجلدات الوكلاء ويعالج الملفات الجديدة.

    الاستخدام:
        pipeline = AgentOutputPipeline()
        await pipeline.run_once()          # معالجة واحدة
        await pipeline.watch(interval=60)  # مراقبة مستمرة كل دقيقة
    """

    SUPPORTED_EXTENSIONS = {
        ".py", ".js", ".php", ".c", ".cpp", ".java", ".rb", ".go",
        ".sql", ".sh", ".bash",
        ".json", ".jsonl", ".txt", ".md", ".diff", ".patch",
    }

    def __init__(self):
        self.processor = RecordProcessor()
        self.sink      = AgentOutputSink()
        self._ensure_output_dirs()

    def _ensure_output_dirs(self):
        """ينشئ مجلدات الخرج إن لم تكن موجودة"""
        for name, path in _AGENT_OUTPUT_DIRS.items():
            path.mkdir(parents=True, exist_ok=True)

    async def process_directory(self, folder_type: str, folder_path: Path) -> int:
        """يعالج كل الملفات الجديدة في مجلد واحد — يعيد عدد الملفات المعالجة"""
        if not folder_path.exists():
            return 0

        count = 0
        for path in folder_path.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
                continue
            if self.sink.already_processed(path):
                continue

            # معالجة
            record = self.processor.process_file(path, folder_type)
            if record:
                saved = self.sink.save_record(record)
                if saved:
                    self.sink.mark_processed(path)
                    count += 1
                    print(f"  ✓ [{record.record_type}] {path.name} "
                          f"— {record.language} — CVSS {record.severity}")

        return count

    async def run_once(self) -> dict:
        """معالجة واحدة لكل المجلدات"""
        print(f"\n{'='*50}")
        print(f"مرصد — معالجة مخرجات الوكلاء")
        print(f"الوقت: {datetime.utcnow().isoformat()}")
        print(f"{'='*50}")

        total = 0
        for folder_type, folder_path in _AGENT_OUTPUT_DIRS.items():
            print(f"\n📂 {folder_type}: {folder_path}")
            count = await self.process_directory(folder_type, folder_path)
            total += count
            if count == 0:
                print(f"  — لا ملفات جديدة")

        # حفظ قائمة الملفات المعالجة
        self.sink._save_processed()

        # إحصائيات
        stats = self.sink.get_stats()
        print(f"\n{'='*50}")
        print(f"✅ تمت المعالجة: {total} ملف جديد")
        print(f"📊 إجمالي قاعدة المعرفة: {stats.get('total', 0)} سجل")
        print(f"📈 متوسط الخطورة: CVSS {stats.get('avg_severity', 0)}")
        print(f"📝 حجم ملف التدريب: {stats.get('jsonl_size', 0) // 1024} KB")
        print(f"{'='*50}\n")

        return {"processed": total, "stats": stats}

    async def watch(self, interval: int = 60):
        """مراقبة مستمرة — تفحص كل `interval` ثانية"""
        print(f"👁 مراقبة مجلدات الوكلاء — كل {interval} ثانية")
        print(f"  Ctrl+C للإيقاف\n")
        while True:
            try:
                result = await self.run_once()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"⚠ خطأ في المراقبة: {e}")
                await asyncio.sleep(interval)

    def inject_external_record(
        self,
        content:     str,
        record_type: str = "code",
        source:      str = "manual",
        severity:    Optional[float] = None,
    ) -> bool:
        """
        حقن سجل مباشرة (من الـ admin panel أو API خارجي).
        مفيد عندما يريد المالك إضافة CVE يدوياً.
        """
        rid = hashlib.sha256(content.encode()).hexdigest()[:16]
        record = ProcessedRecord(
            record_id   = rid,
            source_file = source,
            record_type = record_type,
            content     = content,
            severity    = severity or self.processor.estimate_severity(content, record_type),
            language    = self.processor.detect_language(content),
            timestamp   = datetime.utcnow().isoformat(),
        )
        return self.sink.save_record(record)


# ─── سطر الأوامر ───────────────────────────────────────────────────────────────

async def _main():
    import sys

    pipeline = AgentOutputPipeline()

    args = sys.argv[1:]

    if "--watch" in args:
        interval = 60
        for i, arg in enumerate(args):
            if arg == "--interval" and i + 1 < len(args):
                interval = int(args[i + 1])
        await pipeline.watch(interval)

    elif "--dir" in args:
        idx = args.index("--dir")
        if idx + 1 < len(args):
            target = Path(args[idx + 1])
            folder_type = target.name  # اسم المجلد = نوع الملفات
            print(f"📂 معالجة: {target}")
            count = await pipeline.process_directory(folder_type, target)
            pipeline.sink._save_processed()
            print(f"✅ تمت معالجة {count} ملف")

    elif "--stats" in args:
        stats = pipeline.sink.get_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))

    else:
        # افتراضي: معالجة واحدة
        await pipeline.run_once()


if __name__ == "__main__":
    asyncio.run(_main())
