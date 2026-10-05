"""
Security Pipeline — خط أنابيب الوكلاء الأمنيين الأربعة
يعمل عبر API (Together.ai / Groq) — لا يحتاج GPU
"""

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Optional
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "core"))
sys.path.insert(0, str(Path(__file__).parent.parent / "rag"))

from knowledge_store import get_store, SecurityRecord, RecordType, Severity
from rag_engine import get_rag


# ─── LLM Client (Together.ai / Groq) ─────────────────────────────────────────

class LLMClient:
    """
    يتصل بـ API المجاني — يبدأ بـ Groq (الأسرع)
    وينتقل لـ Together.ai إذا نفد الحد
    """

    def __init__(self):
        self.providers = self._load_providers()

    def _load_providers(self):
        import os
        providers = []
        if os.getenv("GROQ_API_KEY"):
            providers.append({"name": "groq", "key": os.getenv("GROQ_API_KEY"),
                              "url": "https://api.groq.com/openai/v1/chat/completions",
                              "model": "deepseek-r1-distill-llama-70b"})
        if os.getenv("TOGETHER_API_KEY"):
            providers.append({"name": "together", "key": os.getenv("TOGETHER_API_KEY"),
                              "url": "https://api.together.xyz/v1/chat/completions",
                              "model": "deepseek-ai/DeepSeek-V3"})
        return providers

    async def complete(self, system: str, user: str, max_tokens: int = 2048) -> str:
        import aiohttp

        for provider in self.providers:
            try:
                headers = {
                    "Authorization": f"Bearer {provider['key']}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": provider["model"],
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user",   "content": user},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": 0.1,  # منخفض للدقة الأمنية
                }

                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        provider["url"], headers=headers,
                        json=payload, timeout=aiohttp.ClientTimeout(total=60)
                    ) as resp:
                        data = await resp.json()
                        return data["choices"][0]["message"]["content"]

            except Exception as e:
                print(f"[{provider['name']}] خطأ: {e} — أجرب التالي")
                continue

        raise RuntimeError("كل الـ providers فشلت")


# ─── Pipeline Result ──────────────────────────────────────────────────────────

@dataclass
class PipelineResult:
    vulnerabilities: list       # قائمة الثغرات المكتشفة
    patches:         list       # التصحيحات المقترحة
    verified:        list       # التصحيحات المتحقق منها
    false_positives: int        # عدد الـ false positives
    human_approval_required: bool  # يجب موافقة بشرية قبل التطبيق
    report:          str        # التقرير الكامل


# ─── The Four Agents ──────────────────────────────────────────────────────────

class SecurityPipeline:
    """
    4 وكلاء يعملون بالتسلسل — يحاكون فريق اختبار اختراق كامل
    كل وكيل يراجع عمل السابق
    """

    def __init__(self):
        self.llm   = LLMClient()
        self.store = get_store()
        self.rag   = get_rag()

    async def analyze(self, code: str, language: str = "auto") -> PipelineResult:
        """
        التحليل الكامل:
        Scanner → Exploiter → Patcher → Auditor
        """
        print("🔍 Agent 1: Scanner يفحص الكود...")
        scan_result = await self._scanner(code, language)

        if not scan_result.get("vulnerabilities"):
            return PipelineResult(
                vulnerabilities=[], patches=[], verified=[],
                false_positives=0,
                human_approval_required=False,
                report="✅ لم يتم اكتشاف ثغرات واضحة."
            )

        print(f"⚡ Agent 2: Exploiter يتحقق من {len(scan_result['vulnerabilities'])} ثغرة...")
        exploit_result = await self._exploiter(code, scan_result)

        confirmed = exploit_result.get("confirmed", [])
        fps       = exploit_result.get("false_positives", [])

        # سجل الـ false positives كدروس
        for fp in fps:
            self.store.log_error(
                error_type    = "FALSE_POSITIVE",
                context       = code[:200],
                wrong_answer  = str(fp),
                correct_answer= "ليست ثغرة",
                lesson        = f"الـ Scanner أبلغ عن false positive: {fp.get('type','')}",
            )

        if not confirmed:
            return PipelineResult(
                vulnerabilities=scan_result["vulnerabilities"],
                patches=[], verified=[],
                false_positives=len(fps),
                human_approval_required=False,
                report=f"✅ {len(fps)} false positives — لا ثغرات حقيقية."
            )

        print(f"🔧 Agent 3: Patcher يكتب تصحيحات لـ {len(confirmed)} ثغرة...")
        patch_result = await self._patcher(code, confirmed)

        print("🔎 Agent 4: Auditor يتحقق من التصحيحات...")
        audit_result = await self._auditor(code, patch_result)

        # احفظ الاكتشافات الجديدة
        for vuln in confirmed:
            disc_id = self.store.log_discovery(
                target_code = code[:500],
                finding     = str(vuln),
                confidence  = vuln.get("confidence", 0.8),
            )

        report = self._build_report(scan_result, confirmed, fps, patch_result, audit_result)

        return PipelineResult(
            vulnerabilities = confirmed,
            patches         = patch_result.get("patches", []),
            verified        = audit_result.get("approved", []),
            false_positives = len(fps),
            human_approval_required = True,  # دائماً — تصميم أمني أساسي
            report          = report,
        )

    # ── Agent 1: Scanner ──────────────────────────────────────────────────────

    async def _scanner(self, code: str, language: str) -> dict:
        context = self.rag.build_context(code)

        system = """أنت خبير أمني متخصص في اكتشاف الثغرات.
مهمتك: تحديد الثغرات الأمنية في الكود فقط.
أجب بـ JSON صارم بدون أي نص إضافي."""

        user = f"""{context}
الكود:
```{language}
{code}
```

اكتشف الثغرات وأجب بـ JSON فقط:
{{
  "vulnerabilities": [
    {{
      "type": "SQL Injection",
      "line": 5,
      "severity": "HIGH",
      "cvss_estimate": 8.5,
      "description": "...",
      "confidence": 0.95
    }}
  ],
  "language_detected": "python",
  "overall_risk": "HIGH"
}}"""

        response = await self.llm.complete(system, user)
        return self._parse_json(response, {"vulnerabilities": []})

    # ── Agent 2: Exploiter ────────────────────────────────────────────────────

    async def _exploiter(self, code: str, scan: dict) -> dict:
        system = """أنت خبير Penetration Testing.
مهمتك: التحقق من أن الثغرات المكتشفة حقيقية وليست false positives.
لا تكتب exploit حقيقي — فقط تأكد من إمكانية الاستغلال النظري."""

        vulns_text = json.dumps(scan.get("vulnerabilities", []), ensure_ascii=False)

        user = f"""الكود:
```
{code[:1000]}
```

الثغرات المكتشفة:
{vulns_text}

لكل ثغرة: هل هي قابلة للاستغلال فعلاً؟

أجب بـ JSON:
{{
  "confirmed": [
    {{
      "type": "...",
      "exploitable": true,
      "reason": "...",
      "confidence": 0.90
    }}
  ],
  "false_positives": [
    {{
      "type": "...",
      "reason": "ليست ثغرة لأن..."
    }}
  ]
}}"""

        response = await self.llm.complete(system, user)
        return self._parse_json(response, {"confirmed": [], "false_positives": []})

    # ── Agent 3: Patcher ──────────────────────────────────────────────────────

    async def _patcher(self, code: str, vulns: list) -> dict:
        system = """أنت خبير Secure Coding.
مهمتك: كتابة تصحيحات دقيقة وآمنة للثغرات.
التصحيح يجب أن يحل الثغرة بدون كسر الوظيفة الأصلية."""

        vulns_text = json.dumps(vulns, ensure_ascii=False)

        user = f"""الكود الأصلي:
```
{code}
```

الثغرات المؤكدة:
{vulns_text}

اكتب تصحيحاً لكل ثغرة:
{{
  "patches": [
    {{
      "vulnerability_type": "...",
      "original_code": "...",
      "fixed_code": "...",
      "explanation": "...",
      "owasp_reference": "A03:2021"
    }}
  ]
}}"""

        response = await self.llm.complete(system, user, max_tokens=3000)
        return self._parse_json(response, {"patches": []})

    # ── Agent 4: Auditor ──────────────────────────────────────────────────────

    async def _auditor(self, original_code: str, patches: dict) -> dict:
        system = """أنت مدقق أمني مستقل.
مهمتك: التحقق من أن التصحيحات:
1. تحل الثغرة الأصلية
2. لم تكسر الوظيفة الأصلية
3. لم تقدم ثغرات جديدة"""

        patches_text = json.dumps(patches.get("patches", []), ensure_ascii=False)

        user = f"""الكود الأصلي:
```
{original_code[:500]}
```

التصحيحات المقترحة:
{patches_text}

راجع كل تصحيح:
{{
  "approved": [
    {{
      "vulnerability_type": "...",
      "approved": true,
      "new_vulnerabilities_introduced": false,
      "notes": "..."
    }}
  ],
  "rejected": [
    {{
      "vulnerability_type": "...",
      "reason": "..."
    }}
  ]
}}"""

        response = await self.llm.complete(system, user)
        return self._parse_json(response, {"approved": [], "rejected": []})

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _parse_json(self, text: str, default: dict) -> dict:
        """يستخرج JSON من رد النموذج بأمان"""
        import re
        # ابحث عن JSON في الرد
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
        return default

    def _build_report(self, scan, confirmed, fps, patches, audit) -> str:
        lines = [
            "═══════════════════════════════════════",
            "         تقرير الفحص الأمني - مرصد     ",
            "═══════════════════════════════════════",
            f"الثغرات المكتشفة:  {len(scan.get('vulnerabilities',[]))}",
            f"المؤكدة:           {len(confirmed)}",
            f"False Positives:   {len(fps)}",
            f"التصحيحات:         {len(patches.get('patches',[]))}",
            f"المعتمدة:          {len(audit.get('approved',[]))}",
            "",
            "⚠ يجب موافقة بشرية قبل تطبيق أي تصحيح",
            "═══════════════════════════════════════",
        ]
        for v in confirmed:
            lines.append(f"• [{v.get('confidence',0):.0%}] {v.get('type','')}: {v.get('reason','')[:80]}")
        return "\n".join(lines)


# ─── CLI ──────────────────────────────────────────────────────────────────────

async def _demo():
    pipeline = SecurityPipeline()

    test_code = """
import sqlite3

def get_user(username):
    conn = sqlite3.connect('users.db')
    query = f"SELECT * FROM users WHERE name='{username}'"
    return conn.execute(query).fetchall()
"""

    result = await pipeline.analyze(test_code, "python")
    print(result.report)
    print(f"\n✓ Human approval required: {result.human_approval_required}")


if __name__ == "__main__":
    asyncio.run(_demo())
