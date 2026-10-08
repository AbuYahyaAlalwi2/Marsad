"""
deepseek_adapter.py (محدث)
وكيل بناء آلي لحالات اختبار سلبية دفاعية مع تحسينات صارمة لضمان نجاح OpenRouter.
"""
from __future__ import annotations
import json
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import httpx
from scenario_generator import ScenarioBlueprint

@dataclass
class ProjectArtifact:
    scenario_id: str
    provider_used: str
    base_code: dict[str, str]
    verification_test: str
    patched_code: dict[str, str]
    raw_response_chars: int = 0

class BuildRejected(Exception):
    pass

class BuildProvider(ABC):
    name: str
    @abstractmethod
    async def generate_project(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError
    @property
    @abstractmethod
    def available(self) -> bool:
        raise NotImplementedError

class OpenRouterProvider(BuildProvider):
    name = "openrouter"
    MODEL = "qwen/qwen-2.5-coder-32b-instruct"
    def __init__(self):
        self._key = os.getenv("OPENROUTER_API_KEY")
    @property
    def available(self) -> bool:
        return bool(self._key)
    async def generate_project(self, system_prompt: str, user_prompt: str) -> str:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._key}"},
                json={
                    "model": self.MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.2, # خفضنا الحرارة لزيادة الدقة في اتباع التعليمات
                    "max_tokens": 8192,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

class GeminiProvider(BuildProvider):
    name = "gemini"
    def __init__(self):
        self._key = os.getenv("GOOGLE_API_KEY")
    @property
    def available(self) -> bool:
        return bool(self._key)
    async def generate_project(self, system_prompt: str, user_prompt: str) -> str:
        async with httpx.AsyncClient(timeout=120) as client:
            # تم تصحيح اسم النموذج إلى الإصدار المتاح والمجاني
            resp = await client.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=" + self._key,
                json={
                    "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 8192},
                },
            )
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]

ATTACK_TOKENS = [
    "exploit", "payload", "reverse shell", "reverse_shell", "nc -e",
    "shell_injection", "os.system(", "curl", "drop table", "' or '1'='1",
    "metasploit", "rm -rf /", "base64 decode malicious",
]

class BlueprintValidator:
    @staticmethod
    def validate(artifact: ProjectArtifact, blueprint: ScenarioBlueprint) -> list[str]:
        errors: list[str] = []
        if not artifact.base_code:
            errors.append("base_code فارغ")
        if not artifact.verification_test or not artifact.verification_test.strip():
            errors.append("verification_test فارغ")
        if not artifact.patched_code:
            errors.append("patched_code فارغ")
        if len(artifact.base_code) < blueprint.min_files:
            errors.append(f"عدد ملفات base_code {len(artifact.base_code)} أقل من {blueprint.min_files}")
        if set(artifact.base_code.keys()) != set(artifact.patched_code.keys()):
            errors.append("مسارات patched_code لا تطابق مسارات base_code")
        
        # تحقق صارم جداً من وجود علامات الاختبار
        test_lower = artifact.verification_test.lower()
        if "assert" not in test_lower and "def test_" not in test_lower and "pytest" not in test_lower:
            errors.append("verification_test لا يحتوي على 'assert' أو 'def test_' أو 'pytest' بشكل صريح")
            
        joined_all = "\n".join(
            list(artifact.base_code.values())
            + [artifact.verification_test]
            + list(artifact.patched_code.values())
        ).lower()
        for token in ATTACK_TOKENS:
            if token in joined_all:
                errors.append(f"محتوى هجومي ممنوع مكتشف: '{token}'")
        for pattern in blueprint.forbidden_patterns:
            needle = pattern.replace("_", " ")
            if needle in joined_all or pattern in joined_all:
                errors.append(f"نمط ممنوع مكتشف: {pattern}")
        if blueprint.requires_auth_layer:
            auth_markers = ["role", "permission", "authorize", "is_admin", "current_user"]
            if not any(m in joined_all for m in auth_markers):
                errors.append("المستوى يتطلب طبقة أدوار/صلاحيات ولم تُعثر عليها")
        return errors

def _extract_json(raw: str) -> dict:
    # تحسين استخراج JSON ليتعامل مع علامات Markdown إن وجدت
    raw = raw.strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    elif raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError("لم يُعثر على JSON صالح في مخرج المزوّد")
    return json.loads(match.group(0))

class AutoBuildAgent:
    def __init__(self, providers: Optional[list[BuildProvider]] = None, max_attempts_per_provider: int = 2):
        # جعلنا OpenRouter أولاً لأنه الأكثر استقراراً ومجانياً حالياً
        self._providers = providers or [OpenRouterProvider(), GeminiProvider()]
        self._max_attempts = max_attempts_per_provider

    def _system_prompt(self, blueprint: ScenarioBlueprint) -> str:
        return (
            "أنت مولّد بيانات تدريبية دفاعية لصحّة البرمجيات. ممنوع منعاً باتاً أي exploit أو payload.\n\n"
            f"- عدد ملفات base_code: {blueprint.min_files} ملفاً حقيقياً على الأقل.\n"
            f"- طبقة أدوار/صلاحيات حقيقية مطلوبة: {'نعم' if blueprint.requires_auth_layer else 'لا'}.\n\n"
            "أرجع الناتج **فقط** كـ JSON خالص بهذا الشكل بالضبط، بلا أي نص خارج الـ JSON:\n"
            '{\n'
            '  "base_code": {"app.py": "...كود يحتوي خطأ منطقي..."},\n'
            '  "verification_test": "import pytest\\n\\ndef test_bug():\\n    # يجب أن تحتوي هذه الدالة حصراً على كلمة assert لإثبات الخطأ\\n    assert False, \'خطأ منطقي\'\n",\n'
            '  "patched_code": {"app.py": "...نفس الكود بعد الإصلاح..."}\n'
            '}\n\n'
            "تحذير حاسم: إذا لم يحتوي verification_test على كلمة 'assert' أو 'def test_'، سيتم رفض إخراجك فوراً."
        )

    async def build(self, blueprint: ScenarioBlueprint) -> ProjectArtifact:
        user_prompt = blueprint.narrative_brief
        system_prompt = self._system_prompt(blueprint)
        failures: list[str] = []
        for provider in self._providers:
            if not provider.available:
                continue
            for attempt in range(1, self._max_attempts + 1):
                try:
                    raw = await provider.generate_project(system_prompt, user_prompt)
                    parsed = _extract_json(raw)
                    if not isinstance(parsed, dict):
                        raise ValueError("الناتج ليس كائن JSON")
                    artifact = ProjectArtifact(
                        scenario_id=blueprint.scenario_id,
                        provider_used=provider.name,
                        base_code=parsed.get("base_code") or {},
                        verification_test=parsed.get("verification_test") or "",
                        patched_code=parsed.get("patched_code") or {},
                        raw_response_chars=len(raw),
                    )
                    errors = BlueprintValidator.validate(artifact, blueprint)
                    if not errors:
                        return artifact
                    failures.append(f"{provider.name} (محاولة {attempt}): " + "; ".join(errors))
                except Exception as exc:
                    failures.append(f"{provider.name} (محاولة {attempt}): خطأ تقني — {exc}")
        raise BuildRejected(
            f"فشل بناء سيناريو {blueprint.scenario_id} عبر كل المزودين المتاحين:\n" + "\n".join(failures)
        )
