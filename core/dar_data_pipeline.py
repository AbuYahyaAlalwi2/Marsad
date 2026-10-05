"""
dar_data_pipeline.py — خط أنابيب بيانات التدريب
يطبق دستور بيانات التدريب v1.2 كاملاً

المبدأ الحاكم:
- بروتوكول التثليث الإلزامي (vulnerable_code + exploit_poc + remediation_patch)
- البوابة القانونية (robots.txt, ToS, ترخيص على مستوى الملف)
- فلترة الطبقات الأربع (بنية، أمان، تشغيل، تنويع)
- عزل بيانات العملاء
"""

import json
import hashlib
import uuid
import re
import logging
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, Literal
from enum import Enum

# ─── إعداد التسجيل ───────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("dar.pipeline")

# ─── المسارات الافتراضية ──────────────────────────────────────────────────────

BASE_DIR   = Path.home() / "Marsad"
OUTPUT_DIR = BASE_DIR / "output"
DB_PATH    = BASE_DIR / "database" / "dar_training.jsonl"
REJECTED_PATH = BASE_DIR / "database" / "dar_rejected.jsonl"
CANARY_PATH   = BASE_DIR / "database" / "canary_tokens.json"

for p in [OUTPUT_DIR, BASE_DIR / "database"]:
    p.mkdir(parents=True, exist_ok=True)


# ─── الأنواع والثوابت ─────────────────────────────────────────────────────────

class Layer(str, Enum):
    SAST    = "SAST"
    SOC     = "SOC"
    PENTEST = "PENTEST"

class SourceType(str, Enum):
    DIFF_PATCH  = "diff_patch"
    SIGMA_RULE  = "sigma_rule"
    TOOL_OUTPUT = "tool_output"
    SYNTHETIC   = "synthetic"

class Status(str, Enum):
    QUARANTINE = "quarantine"
    APPROVED   = "approved"
    REJECTED   = "rejected"

# ─── Schema السجل الموحد (القسم 2 من الدستور) ────────────────────────────────

@dataclass
class Taxonomy:
    cwe:              Optional[str] = None   # مثل "CWE-89"
    cve:              Optional[str] = None   # مثل "CVE-2024-xxxxx"
    attack_technique: Optional[str] = None  # مثل "T1190"

@dataclass
class Provenance:
    repo_url:    str = ""
    commit_hash: str = ""
    license:     str = ""
    fetched_at:  str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

@dataclass
class TrainingRecord:
    """السجل الموحد — يطابق Schema الدستور v1.2"""
    id:          str = field(default_factory=lambda: f"rec_{datetime.now().strftime('%Y_%m_%d')}_{uuid.uuid4().hex[:5]}")
    layer:       str = Layer.SAST
    source_type: str = SourceType.DIFF_PATCH
    taxonomy:    Taxonomy = field(default_factory=Taxonomy)
    provenance:  Provenance = field(default_factory=Provenance)

    # محتوى التدريب
    vulnerable_code:    Optional[str] = None  # للطبقة 1 و3
    exploit_poc:        Optional[str] = None  # للطبقة 3 فقط (بروتوكول التثليث)
    remediation_patch:  Optional[str] = None  # إلزامي مع exploit_poc
    rule_content:       Optional[str] = None  # للطبقة 2 (Sigma/Suricata)
    description:        str = ""

    # حقول الحوكمة
    client_id:              Optional[str] = None
    roe_authorization_id:   Optional[str] = None
    reviewer:               str = "quality_swarm"
    content_hash:           str = ""
    status:                 str = Status.QUARANTINE
    rejection_reason:       Optional[str] = None

    def compute_hash(self) -> str:
        content = (self.vulnerable_code or "") + (self.exploit_poc or "") + (self.remediation_patch or "") + (self.rule_content or "")
        return "sha256:" + hashlib.sha256(content.encode()).hexdigest()


# ─── البوابة القانونية (القسم 1) ─────────────────────────────────────────────

class LegalGateway:
    """يطبق البوابة القانونية السباعية من الدستور"""

    ALLOWED_LICENSES = {"mit", "apache-2.0", "apache 2.0", "bsd", "bsd-2-clause", "bsd-3-clause", "cc0"}
    BLOCKED_PLATFORMS = {"ieee.org", "elsevier.com", "springer.com", "acm.org"}
    NO_AI_PATTERNS = [
        r"no.?ai", r"no.?train", r"ai.?prohibited",
        r"machine.?learning.?prohibited", r"not.?for.?ai"
    ]

    def check(self, record: TrainingRecord) -> tuple[bool, str]:
        """
        يعيد (True, "") إذا اجتاز، أو (False, "سبب الرفض")
        """
        repo = record.provenance.repo_url.lower()

        # 1. فحص المنصات المحجوبة
        for blocked in self.BLOCKED_PLATFORMS:
            if blocked in repo:
                return False, f"منصة أكاديمية مغلقة: {blocked}"

        # 2. فحص الترخيص
        lic = record.provenance.license.lower().strip()
        if lic and not any(allowed in lic for allowed in self.ALLOWED_LICENSES):
            return False, f"ترخيص غير مسموح: {record.provenance.license}"

        # 3. فحص PENTEST بدون RoE
        if record.layer == Layer.PENTEST and not record.roe_authorization_id:
            return False, "طبقة PENTEST تتطلب roe_authorization_id"

        # 4. فحص نمط no-ai (في الوصف)
        text = record.description.lower()
        for pattern in self.NO_AI_PATTERNS:
            if re.search(pattern, text):
                return False, f"يحتوي على بند رفض AI: {pattern}"

        return True, ""


# ─── فلترة الطبقة الأولى — بنية ولغة (القسم 4) ──────────────────────────────

class StructuralFilter:
    """يرفض البيانات ذات البنية الضعيفة"""

    MIN_CHARS = 50        # حد أدنى للمحتوى
    SIMILARITY_THRESHOLD = 0.85

    def __init__(self):
        self._seen_hashes: set[str] = set()

    def check(self, record: TrainingRecord) -> tuple[bool, str]:
        content = (record.vulnerable_code or "") + (record.rule_content or "") + (record.description or "")

        # 1. فحص الطول الأدنى
        if len(content.strip()) < self.MIN_CHARS:
            return False, f"محتوى قصير جداً: {len(content)} حرف"

        # 2. فحص التكرار الحرفي
        h = record.content_hash or record.compute_hash()
        if h in self._seen_hashes:
            return False, "تكرار حرفي موجود بالفعل"
        self._seen_hashes.add(h)

        return True, ""

    def load_existing(self, db_path: Path):
        """يحمل الهاشات الموجودة لمنع التكرار"""
        if not db_path.exists():
            return
        with open(db_path) as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    if h := rec.get("content_hash"):
                        self._seen_hashes.add(h)
                except Exception:
                    pass
        log.info(f"تم تحميل {len(self._seen_hashes)} هاش من قاعدة البيانات")


# ─── فلترة الطبقة الثانية — أمان (القسم 4) ──────────────────────────────────

class SecurityFilter:
    """يفحص البيانات للأسرار والمعلومات الحساسة"""

    # أنماط تسريب API Keys
    SECRET_PATTERNS = [
        r'(sk|gsk|hf|ghp|glpat)_[A-Za-z0-9]{20,}',
        r'AKIA[A-Z0-9]{16}',
        r'AIza[0-9A-Za-z\-_]{35}',
        r'-----BEGIN (RSA|EC|DSA) PRIVATE KEY-----',
    ]

    # عناوين IP حقيقية (غير الافتراضية)
    REAL_IP_PATTERN = r'\b(?!10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.|127\.|0\.0\.0\.0)(\d{1,3}\.){3}\d{1,3}\b'

    # نطاقات شركات حقيقية (يجب استبدالها)
    REAL_DOMAIN_PATTERN = r'\b[a-z0-9-]+\.(com|net|org|io|co)\b'

    def sanitize_exploit(self, code: str) -> str:
        """
        تطهير المعطيات الهجومية (القسم 4 من الدستور)
        يستبدل IPs ونطاقات حقيقية بقيم افتراضية
        """
        # استبدال IPs الحقيقية
        code = re.sub(self.REAL_IP_PATTERN, "192.168.1.1", code)
        # استبدال النطاقات (ما عدا المعروفة الآمنة)
        safe_domains = {"example.com", "test.local", "localhost", "127.0.0.1"}
        def replace_domain(m):
            domain = m.group(0)
            return domain if domain in safe_domains else "target.test.local"
        code = re.sub(self.REAL_DOMAIN_PATTERN, replace_domain, code)
        return code

    def check(self, record: TrainingRecord) -> tuple[bool, str]:
        all_content = " ".join(filter(None, [
            record.vulnerable_code, record.exploit_poc,
            record.remediation_patch, record.rule_content
        ]))

        # فحص تسريب أسرار
        for pattern in self.SECRET_PATTERNS:
            if re.search(pattern, all_content):
                return False, f"تسريب سر/مفتاح: {pattern}"

        # تطهير exploit_poc إذا وجد
        if record.exploit_poc:
            record.exploit_poc = self.sanitize_exploit(record.exploit_poc)

        return True, ""


# ─── بروتوكول التثليث (القسم 3 — الطبقة 3) ──────────────────────────────────

class TriadValidator:
    """
    يطبق بروتوكول التثليث الإلزامي:
    vulnerable_code + exploit_poc + remediation_patch
    أي كود استغلال بدون الثلاثة مجتمعة → رفض
    """

    def check(self, record: TrainingRecord) -> tuple[bool, str]:
        if record.layer != Layer.PENTEST:
            return True, ""  # التثليث للطبقة 3 فقط

        missing = []
        if not record.vulnerable_code:
            missing.append("vulnerable_code")
        if not record.exploit_poc:
            missing.append("exploit_poc")
        if not record.remediation_patch:
            missing.append("remediation_patch")

        if missing:
            return False, f"بروتوكول التثليث — ناقص: {', '.join(missing)}"

        # فحص Non-Destructive Payloads
        destructive_patterns = [
            r'\brm\s+-rf\b', r'\bformat\b', r'\bransomware\b',
            r'\bshutil\.rmtree\b', r'\bos\.system\("rm\b',
            r'encrypt.*files', r'wipe.*disk'
        ]
        for pattern in destructive_patterns:
            if re.search(pattern, record.exploit_poc, re.IGNORECASE):
                return False, f"كود تدميري ممنوع: {pattern}"

        return True, ""


# ─── التنويع ومنع الانحياز (القسم 4 — الطبقة 4) ─────────────────────────────

class DiversityTracker:
    """
    يطبق:
    - سقف 3% لكل موضوع/قالب
    - توازن إلزامي بين الفئات
    """

    MAX_TOPIC_RATIO = 0.03  # 3% كحد أقصى لأي موضوع

    def __init__(self):
        self._topic_counts: dict[str, int] = {}
        self._total = 0
        self._layer_counts = {l: 0 for l in Layer}

    def check(self, record: TrainingRecord) -> tuple[bool, str]:
        topic = record.taxonomy.cwe or record.layer
        count = self._topic_counts.get(str(topic), 0)

        if self._total > 100:  # لا نطبق حتى يكون لدينا حجم كافٍ
            ratio = count / self._total
            if ratio >= self.MAX_TOPIC_RATIO:
                return False, f"تجاوز سقف 3% للموضوع: {topic} ({ratio:.1%})"

        return True, ""

    def record(self, rec: TrainingRecord):
        topic = str(rec.taxonomy.cwe or rec.layer)
        self._topic_counts[topic] = self._topic_counts.get(topic, 0) + 1
        self._total += 1
        self._layer_counts[rec.layer] = self._layer_counts.get(rec.layer, 0) + 1

    def stats(self) -> dict:
        return {
            "total": self._total,
            "by_layer": {str(k): v for k, v in self._layer_counts.items()},
            "top_topics": sorted(self._topic_counts.items(), key=lambda x: -x[1])[:10]
        }


# ─── إدارة Canary Tokens (القسم 6) ───────────────────────────────────────────

class CanaryManager:
    """
    يولد canary tokens دورية لاختبار عدم تسريب بيانات العملاء
    """

    def __init__(self, path: Path = CANARY_PATH):
        self.path = path
        self._tokens: dict = {}
        if path.exists():
            self._tokens = json.loads(path.read_text())

    def generate(self, client_id: str) -> str:
        token = f"CANARY_{client_id}_{uuid.uuid4().hex[:8]}"
        self._tokens[token] = {
            "client_id": client_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "triggered": False
        }
        self._save()
        return token

    def check_triggered(self, model_output: str) -> list[str]:
        """يفحص إذا ظهر أي canary في مخرجات النموذج — تسريب محتمل"""
        triggered = []
        for token in self._tokens:
            if token in model_output:
                self._tokens[token]["triggered"] = True
                triggered.append(token)
        if triggered:
            self._save()
        return triggered

    def _save(self):
        self.path.write_text(json.dumps(self._tokens, ensure_ascii=False, indent=2))


# ─── خط الأنابيب الرئيسي ─────────────────────────────────────────────────────

class DarDataPipeline:
    """
    خط أنابيب بيانات التدريب الكامل
    يطبق الدستور v1.2 خطوة بخطوة
    """

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path      = db_path
        self.rejected_path = REJECTED_PATH

        # تهيئة الفلاتر
        self.legal     = LegalGateway()
        self.structural = StructuralFilter()
        self.security  = SecurityFilter()
        self.triad     = TriadValidator()
        self.diversity = DiversityTracker()
        self.canary    = CanaryManager()

        # تحميل الهاشات الموجودة
        self.structural.load_existing(db_path)

        # إحصاءات
        self._stats = {"processed": 0, "approved": 0, "rejected": 0, "reasons": {}}

    def process(self, record: TrainingRecord) -> tuple[bool, str]:
        """
        يمرر السجل عبر كل الطبقات
        يعيد (True, "") إذا اجتاز أو (False, "سبب")
        """
        self._stats["processed"] += 1

        # حساب الهاش
        record.content_hash = record.compute_hash()

        # ── البوابة القانونية (أولاً دائماً) ──
        ok, reason = self.legal.check(record)
        if not ok:
            return self._reject(record, f"[قانوني] {reason}")

        # ── عزل بيانات العملاء ──
        if record.client_id:
            log.warning(f"سجل عميل {record.client_id} — لا يدخل التدريب المشترك")
            return self._reject(record, "[عميل] بيانات العميل لا تدخل التدريب المشترك")

        # ── الطبقة 1: بنية ولغة ──
        ok, reason = self.structural.check(record)
        if not ok:
            return self._reject(record, f"[بنية] {reason}")

        # ── الطبقة 2: أمان ──
        ok, reason = self.security.check(record)
        if not ok:
            return self._reject(record, f"[أمان] {reason}")

        # ── بروتوكول التثليث (للطبقة 3) ──
        ok, reason = self.triad.check(record)
        if not ok:
            return self._reject(record, f"[تثليث] {reason}")

        # ── الطبقة 4: تنويع ──
        ok, reason = self.diversity.check(record)
        if not ok:
            return self._reject(record, f"[تنويع] {reason}")

        # ── اجتاز كل الفلاتر ──
        record.status = Status.APPROVED
        self._save(record)
        self.diversity.record(record)
        self._stats["approved"] += 1
        log.info(f"✓ مقبول: {record.id} [{record.layer}] {record.taxonomy.cwe or ''}")
        return True, ""

    def process_batch(self, records: list[TrainingRecord]) -> dict:
        """يعالج مجموعة من السجلات"""
        for r in records:
            self.process(r)
        return self.stats()

    def load_from_jsonl(self, path: Path) -> list[TrainingRecord]:
        """يحمل سجلات من ملف JSONL"""
        records = []
        if not path.exists():
            log.warning(f"الملف غير موجود: {path}")
            return records
        with open(path) as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    # تحويل من تنسيق cleaned_data.jsonl لـ Qwen
                    rec = self._convert_from_qwen(data)
                    if rec:
                        records.append(rec)
                except Exception as e:
                    log.error(f"خطأ في السطر {i}: {e}")
        log.info(f"تم تحميل {len(records)} سجل من {path}")
        return records

    def _convert_from_qwen(self, data: dict) -> Optional[TrainingRecord]:
        """يحول تنسيق مخرجات Qwen إلى TrainingRecord"""
        try:
            rec = TrainingRecord(
                layer       = data.get("layer", Layer.SAST),
                source_type = data.get("source_type", SourceType.DIFF_PATCH),
                taxonomy    = Taxonomy(
                    cwe              = data.get("cwe"),
                    cve              = data.get("cve"),
                    attack_technique = data.get("attack_technique"),
                ),
                provenance = Provenance(
                    repo_url    = data.get("repo_url", ""),
                    commit_hash = data.get("commit_hash", ""),
                    license     = data.get("license", ""),
                ),
                vulnerable_code   = data.get("vulnerable_code") or data.get("code") or data.get("input"),
                remediation_patch = data.get("remediation_patch") or data.get("fix") or data.get("output"),
                exploit_poc       = data.get("exploit_poc"),
                rule_content      = data.get("rule_content"),
                description       = data.get("description") or data.get("instruction", ""),
            )
            return rec
        except Exception as e:
            log.error(f"فشل التحويل: {e}")
            return None

    def _reject(self, record: TrainingRecord, reason: str) -> tuple[bool, str]:
        record.status = Status.REJECTED
        record.rejection_reason = reason
        self._stats["rejected"] += 1
        cat = reason.split("]")[0].strip("[") if "]" in reason else "other"
        self._stats["reasons"][cat] = self._stats["reasons"].get(cat, 0) + 1

        with open(self.rejected_path, "a") as f:
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

        log.debug(f"✗ مرفوض: {record.id} — {reason}")
        return False, reason

    def _save(self, record: TrainingRecord):
        with open(self.db_path, "a") as f:
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

    def stats(self) -> dict:
        return {
            **self._stats,
            "approval_rate": f"{self._stats['approved']/max(self._stats['processed'],1):.1%}",
            "diversity": self.diversity.stats(),
        }

    def print_stats(self):
        s = self.stats()
        print("\n" + "═"*45)
        print("  إحصاءات خط أنابيب بيانات دار")
        print("═"*45)
        print(f"  إجمالي المعالجة : {s['processed']}")
        print(f"  مقبول           : {s['approved']}")
        print(f"  مرفوض           : {s['rejected']}")
        print(f"  نسبة القبول     : {s['approval_rate']}")
        print(f"\n  أسباب الرفض:")
        for reason, count in s["reasons"].items():
            print(f"    [{reason}]: {count}")
        print(f"\n  توزيع الطبقات:")
        for layer, count in s["diversity"]["by_layer"].items():
            print(f"    {layer}: {count}")
        print("═"*45 + "\n")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="dar_data_pipeline — خط أنابيب بيانات دار")
    sub = parser.add_subparsers(dest="cmd")

    # استيراد من ملف Qwen
    p_import = sub.add_parser("import", help="استيراد من cleaned_data.jsonl")
    p_import.add_argument("path", help="مسار الملف")

    # إضافة سجل يدوياً
    p_add = sub.add_parser("add", help="إضافة سجل اختبار")

    # إحصاءات
    sub.add_parser("stats", help="عرض الإحصاءات")

    # توليد canary token
    p_canary = sub.add_parser("canary", help="توليد canary token لعميل")
    p_canary.add_argument("client_id", help="معرف العميل")

    args = parser.parse_args()
    pipeline = DarDataPipeline()

    if args.cmd == "import":
        records = pipeline.load_from_jsonl(Path(args.path))
        pipeline.process_batch(records)
        pipeline.print_stats()

    elif args.cmd == "add":
        # سجل اختبار
        rec = TrainingRecord(
            layer       = Layer.SAST,
            source_type = SourceType.DIFF_PATCH,
            taxonomy    = Taxonomy(cwe="CWE-89", cve="CVE-2024-00001"),
            provenance  = Provenance(
                repo_url    = "https://github.com/test/repo",
                commit_hash = "abc123",
                license     = "MIT",
            ),
            vulnerable_code   = "query = f\"SELECT * FROM users WHERE id={user_input}\"",
            remediation_patch = "query = \"SELECT * FROM users WHERE id=?\"\ncursor.execute(query, (user_input,))",
            description       = "SQL Injection في استعلام مباشر",
        )
        ok, reason = pipeline.process(rec)
        print(f"النتيجة: {'✓ مقبول' if ok else f'✗ مرفوض: {reason}'}")
        pipeline.print_stats()

    elif args.cmd == "stats":
        pipeline = DarDataPipeline()
        pipeline.structural.load_existing(DB_PATH)
        pipeline.print_stats()

    elif args.cmd == "canary":
        token = pipeline.canary.generate(args.client_id)
        print(f"Canary token للعميل {args.client_id}: {token}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
