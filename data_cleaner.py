"""
data_cleaner.py — تنظيف ملفات التدريب JSONL
=============================================
⚠ هذا الملف مكتوب للتنفيذ بواسطة Qwen3-Coder

المهمة:
    قرأ training_data.jsonl → نظّف → احذف المكرر → أنتج نسخة نظيفة

الاستخدام:
    python data_cleaner.py                    ← تنظيف training_data.jsonl
    python data_cleaner.py --input my.jsonl   ← ملف مخصص
    python data_cleaner.py --stats            ← إحصائيات فقط
"""

import json
import hashlib
import sys
from pathlib import Path

INPUT_FILE  = Path(__file__).parent / "training_data.jsonl"
OUTPUT_FILE = Path(__file__).parent / "training_data_clean.jsonl"


def load_jsonl(path: Path) -> list:
    """
    يقرأ ملف JSONL سطراً سطراً.
    يتجاهل الأسطر الفارغة والأسطر غير الصالحة (json.JSONDecodeError).
    يعيد قائمة من dicts.
    """
    # ── TODO: Qwen ينفّذ هنا ────────────────────────────────────────────────
    raise NotImplementedError("Qwen: نفّذ load_jsonl")


def deduplicate(records: list) -> list:
    """
    يحذف السجلات المكررة.
    المعرّف: SHA256 لمحتوى messages[0]["content"] + messages[-1]["content"]
    يحتفظ بأول نسخة من كل سجل.
    يعيد القائمة بعد الحذف.
    """
    # ── TODO: Qwen ينفّذ هنا ────────────────────────────────────────────────
    raise NotImplementedError("Qwen: نفّذ deduplicate")


def filter_empty(records: list) -> list:
    """
    يحذف السجلات التي:
    - ليس فيها مفتاح "messages"
    - messages فارغة أو أقل من entry واحد
    - أي message ليس فيها "role" أو "content"
    - content فارغ أو أقل من 10 أحرف
    """
    # ── TODO: Qwen ينفّذ هنا ────────────────────────────────────────────────
    raise NotImplementedError("Qwen: نفّذ filter_empty")


def normalize(records: list) -> list:
    """
    يوحّد بنية كل سجل:
    - تأكد أن "id" موجود (إذا لا → أنشئ SHA256 من المحتوى)
    - تأكد أن "type" موجود (إذا لا → "unknown")
    - تأكد أن "severity" موجود ورقم float (إذا لا → 5.0)
    - احذف أي مفاتيح غير معروفة (احتفظ فقط بـ: id, type, severity, language, source, timestamp, messages)
    """
    # ── TODO: Qwen ينفّذ هنا ────────────────────────────────────────────────
    raise NotImplementedError("Qwen: نفّذ normalize")


def save_jsonl(records: list, path: Path):
    """
    يكتب القائمة كملف JSONL — سطر لكل سجل، ensure_ascii=False.
    """
    # ── TODO: Qwen ينفّذ هنا ────────────────────────────────────────────────
    raise NotImplementedError("Qwen: نفّذ save_jsonl")


def print_stats(records: list, label: str = ""):
    """
    يطبع:
    - عدد السجلات
    - التوزيع حسب type (code/cve/fix/advisory)
    - متوسط severity
    - توزيع severity (LOW/MEDIUM/HIGH/CRITICAL)
    """
    # ── TODO: Qwen ينفّذ هنا ────────────────────────────────────────────────
    raise NotImplementedError("Qwen: نفّذ print_stats")


# ─── main (جاهز — لا تعدّله) ─────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    input_path  = INPUT_FILE
    output_path = OUTPUT_FILE
    stats_only  = "--stats" in args

    if "--input" in args:
        idx        = args.index("--input")
        input_path = Path(args[idx + 1])

    if not input_path.exists():
        print(f"✗ الملف غير موجود: {input_path}")
        sys.exit(1)

    print(f"📂 تحميل: {input_path}")
    records = load_jsonl(input_path)

    print(f"\n--- قبل التنظيف ---")
    print_stats(records, "الكل")

    if stats_only:
        return

    records = filter_empty(records)
    records = deduplicate(records)
    records = normalize(records)

    print(f"\n--- بعد التنظيف ---")
    print_stats(records, "نظيف")

    save_jsonl(records, output_path)
    print(f"\n✅ الملف النظيف: {output_path}")


if __name__ == "__main__":
    main()
