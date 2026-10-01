"""SkillLoader — تحميل المهارات عند الحاجة (تقليل 70% من السياق)."""
from __future__ import annotations
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)
SKILLS_DIR = Path.home() / "Marsad" / "skills"
SKILLS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Skill:
    name: str
    description: str
    keywords: List[str]
    content: str           # الكود/النص
    category: str = "general"


class SkillLoader:
    """يحمّل المهارات فقط عند مطابقة الكلمة المفتاحية."""

    def __init__(self):
        self._cache: dict[str, Skill] = {}
        self._index: Optional[dict] = None

    def _build_index(self) -> dict:
        """يبني فهرس: keyword → [skill_names]."""
        index: dict[str, List[str]] = {}
        for f in SKILLS_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                name = data.get("name", f.stem)
                self._cache[name] = Skill(
                    name=name,
                    description=data.get("description", ""),
                    keywords=data.get("keywords", []),
                    content=data.get("content", ""),
                    category=data.get("category", "general"),
                )
                for kw in data.get("keywords", []):
                    index.setdefault(kw.lower(), []).append(name)
            except Exception as e:
                logger.warning(f"[skill_loader] failed: {f.name}: {e}")
        self._index = index
        return index

    def _ensure_index(self):
        if self._index is None:
            self._build_index()

    def match(self, query: str, max_skills: int = 3) -> List[Skill]:
        """يعيد المهارات المطابقة للاستعلام."""
        self._ensure_index()
        query_low = query.lower()
        scored: dict[str, int] = {}
        for kw, names in self._index.items():
            if kw in query_low:
                for n in names:
                    scored[n] = scored.get(n, 0) + 1
        # ترتيب حسب عدد المطابقات
        top = sorted(scored.items(), key=lambda x: -x[1])[:max_skills]
        return [self._cache[name] for name, _ in top if name in self._cache]

    def register(self, skill: Skill):
        """يضيف مهارة جديدة."""
        f = SKILLS_DIR / f"{skill.name}.json"
        f.write_text(json.dumps({
            "name": skill.name,
            "description": skill.description,
            "keywords": skill.keywords,
            "content": skill.content,
            "category": skill.category,
        }, ensure_ascii=False, indent=2))
        self._cache[skill.name] = skill
        self._index = None  # أعد البناء

    def list_all(self) -> List[str]:
        self._ensure_index()
        return list(self._cache.keys())

    def load_context_for(self, query: str) -> str:
        """يعيد نص السياق الجاهز للـ prompt."""
        skills = self.match(query)
        if not skills:
            return ""
        parts = ["[مهارات مطابقة]"]
        for s in skills:
            parts.append(f"\n## {s.name}\n{s.description}\n```\n{s.content[:1500]}\n```")
        return "\n".join(parts)


# ─── Singleton + مهارات أساسية ───────────────────────────
loader = SkillLoader()


def _register_builtin_skills():
    """مهارات أساسية جاهزة."""
    if "cve_analysis" in loader.list_all():
        return

    loader.register(Skill(
        name="cve_analysis",
        description="تحليل CVE والحصول على CVSS + exploits",
        keywords=["cve", "ثغرة", "log4shell", "log4j", "تحليل ثغرة"],
        category="cyber",
        content='''from tools.cyber_senses import threat_summary
result = threat_summary("CVE-XXXX-YYYY")
# result = {"nvd": {...}, "cisa_exploited": bool, "exploits": [...]}''',
    ))

    loader.register(Skill(
        name="pdf_report",
        description="توليد تقرير PDF عربي للعميل",
        keywords=["تقرير", "pdf", "report", "تقرير ثغرة"],
        category="report",
        content='''from tools.cyber_senses import threat_summary
from tools.report_pdf import build_vulnerability_report
v = threat_summary("CVE-XXXX-YYYY")
path = build_vulnerability_report(v, client_name="العميل")''',
    ))

    loader.register(Skill(
        name="code_execution",
        description="تنفيذ كود Python بأمان في sandbox",
        keywords=["نفذ", "احسب", "run", "execute", "python"],
        category="execution",
        content='''from core.tool_calling import registry
result = registry.execute("run_python", {"code": "print(2+2)"})''',
    ))

    loader.register(Skill(
        name="network_probe",
        description="فحص شبكة أو خدمة",
        keywords=["فحص", "network", "probe", "ping", "curl"],
        category="cyber",
        content='''from core.tool_calling import registry
result = registry.execute("http_get", {"url": "https://example.com"})''',
    ))


_register_builtin_skills()


if __name__ == "__main__":
    print("=== اختبار SkillLoader ===\n")
    print("Skills المتاحة:", loader.list_all())

    print("\n--- استعلام: 'حلل CVE-2021-44228' ---")
    matched = loader.match("حلل CVE-2021-44228")
    print("مطابق:", [s.name for s in matched])

    print("\n--- استعلام: 'اعمل تقرير PDF' ---")
    matched = loader.match("اعمل تقرير PDF")
    print("مطابق:", [s.name for s in matched])

    print("\n--- استعلام: 'نفذ كود python' ---")
    matched = loader.match("نفذ كود python")
    print("مطابق:", [s.name for s in matched])

    print("\n✓ SkillLoader ready")
