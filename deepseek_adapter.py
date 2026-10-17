"""
deepseek_adapter.py
====================
وكيل بناء آلي لحالات اختبار سلبية دفاعية (Negative Test Cases). يأخذ
ScenarioBlueprint (من scenario_generator.py) ويطلب من مزوّد LLM (DeepSeek
أساسي، OpenRouter/Gemini/HF احتياط) ثلاثة مكوّنات فقط:

  base_code          — كود يحتوي خطأً منطقياً واحداً (لا exploit، لا payload)
  verification_test  — pytest/assert يفشل ضد base_code
  patched_code        — نفس الكود بعد الإصلاح، ينجح الاختبار ضده

BlueprintValidator يرفض أي مخرج يحتوي كلمات/أنماط هجومية (exploit, payload,
reverse shell...) أو لا يحتوي الثلاثة مكوّنات، أو لا يحتوي علامات اختبار
حقيقية (assert/pytest). هذا فحص بنيوي صارم قبل أي تنفيذ في الساندبوكس.
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


# ---------------------------------------------------------------------------
# 1. نتيجة البناء
# ---------------------------------------------------------------------------

@dataclass
class ProjectArtifact:
    scenario_id: str
    provider_used: str
    base_code: dict[str, str]       # {"path": "content"}
    verification_test: str          # محتوى ملف pytest واحد
    patched_code: dict[str, str]    # {"path": "content"} — نفس مسارات base_code المصلَحة
    raw_response_chars: int = 0


class BuildRejected(Exception):
    """فشل كل المزودين في إنتاج حالة اختبار تجتاز BlueprintValidator."""


# ---------------------------------------------------------------------------
# 2. واجهة المزوّد الموحّدة
# ---------------------------------------------------------------------------

class BuildProvider(ABC):
    name: str

    @abstractmethod
    async def generate_project(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def available(self) -> bool:
        raise NotImplementedError


class DeepSeekProvider(BuildProvider):
    name = "deepseek"

    def __init__(self):
        self._key = os.getenv("DEEPSEEK_API_KEY")

    @property
    def available(self) -> bool:
        return bool(self._key)

    async def generate_project(self, system_prompt: str, user_prompt: str) -> str:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {self._key}"},
                json={
                    "model": "deepseek-coder",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 8192,
                    "response_format": {"type": "json_object"},
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]


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
                    "temperature": 0.3,
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
            resp = await client.post(
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"gemini-2.5-pro:generateContent?key={self._key}",
                json={
                    "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
                    "generationConfig": {"temperature": 0.3, "maxOutputTokens": 8192},
                },
            )
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


class HFInferenceProvider(BuildProvider):
    name = "huggingface"
    MODEL = "Qwen/Qwen2.5-Coder-32B-Instruct"

    def __init__(self):
        self._key = os.getenv("HF_API_KEY")

    @property
    def available(self) -> bool:
        return bool(self._key)

    async def generate_project(self, system_prompt: str, user_prompt: str) -> str:
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(
                f"https://api-inference.huggingface.co/models/{self.MODEL}",
                headers={"Authorization": f"Bearer {self._key}"},
                json={"inputs": f"{system_prompt}\n\n{user_prompt}",
                      "parameters": {"temperature": 0.3, "max_new_tokens": 8192}},
            )
            resp.raise_for_status()
            data = resp.json()
            return data[0]["generated_text"] if isinstance(data, list) else data.get("generated_text", "")


# ---------------------------------------------------------------------------
# 3. مدقّق صارم — يرفض أي صياغة هجومية ويفرض بنية الثلاثة مكوّنات
# ---------------------------------------------------------------------------

ATTACK_TOKENS = [
    "exploit", "payload", "reverse shell", "reverse_shell", "nc -e",
    "shell_injection", "os.system(\"curl", "drop table", "' or '1'='1",
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
            errors.append("مسارات patched_code لا تطابق مسارات base_code — يجب إصلاح نفس الملفات بالضبط")

        test_markers = ["assert ", "pytest", "def test_", "func Test", "testing.T", "go test"]
        if not any(m in artifact.verification_test for m in test_markers):
            errors.append("verification_test لا يحتوي علامات اختبار حقيقية (assert/pytest)")

        joined_all = "\n".join(
            list(artifact.base_code.values())
            + [artifact.verification_test]
            + list(artifact.patched_code.values())
        ).lower()

        for token in ATTACK_TOKENS:
            if token in joined_all:
                errors.append(f"محتوى هجومي ممنوع مكتشف: '{token}' — هذا مولّد دفاعي فقط")

        for pattern in blueprint.forbidden_patterns:
            needle = pattern.replace("_", " ")
            if needle in joined_all or pattern in joined_all:
                errors.append(f"نمط ممنوع مكتشف: {pattern}")

        if blueprint.requires_auth_layer:
            auth_markers = ["role", "permission", "authorize", "is_admin", "current_user"]
            if not any(m in joined_all for m in auth_markers):
                errors.append("المستوى يتطلب طبقة أدوار/صلاحيات ولم تُعثر عليها")

        base_joined = "\n".join(artifact.base_code.values())
        min_real_files_with_deps = sum(
            1 for content in artifact.base_code.values()
            if any(kw in content for kw in ["import ", "require(", "from "])
        )
        if min_real_files_with_deps < blueprint.min_real_dependencies:
            errors.append(
                f"تبعيات حقيقية غير كافية: {min_real_files_with_deps} < {blueprint.min_real_dependencies}"
            )

        return errors


def _extract_json(raw: str) -> dict:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError("لم يُعثر على JSON صالح في مخرج المزوّد")
    return json.loads(match.group(0))


# ---------------------------------------------------------------------------
# 4. الوكيل الرئيسي
# ---------------------------------------------------------------------------

class AutoBuildAgent:
    def __init__(self, providers: Optional[list[BuildProvider]] = None, max_attempts_per_provider: int = 2):
        self._providers = providers or [
            DeepSeekProvider(), OpenRouterProvider(), GeminiProvider(), HFInferenceProvider(),
        ]
        self._max_attempts = max_attempts_per_provider

    def _system_prompt(self, blueprint: ScenarioBlueprint) -> str:
        return (
            "أنت مولّد بيانات تدريبية دفاعية لصحّة البرمجيات (software correctness). هذا ليس أمن هجومي "
            "ولا تدريب اختراق — المطلوب فقط توضيح خطأ منطقي برمجي شائع عبر اختبار يفشل ثم ينجح بعد الإصلاح. "
            "ممنوع منعاً باتاً أي exploit code أو payload أو محاولة اختراق فعلية أو أي نص يصف تنفيذ هجوم.\n\n"
            f"- عدد ملفات base_code: {blueprint.min_files} ملفاً حقيقياً على الأقل.\n"
            f"- عدد التبعيات الحقيقية (import/require فعلي): {blueprint.min_real_dependencies} على الأقل.\n"
            f"- طبقة أدوار/صلاحيات حقيقية مطلوبة: {'نعم' if blueprint.requires_auth_layer else 'لا'}.\n"
            f"- الخطأ يتطلب اجتماع أكثر من شرط منطقي: {'نعم' if blueprint.requires_multi_step_defect else 'لا'}.\n"
            f"- الأنماط الممنوعة تماماً: {', '.join(blueprint.forbidden_patterns)}.\n\n"
            "أرجع الناتج **فقط** كـ JSON خالص بهذا الشكل بالضبط، بلا أي نص خارج الـ JSON:\n"
            '{\n'
            '  "base_code": {"path/to/file.py": "...محتوى يحتوي الخطأ المنطقي..."},\n'
            '  "verification_test": "...محتوى ملف pytest واحد، يجب أن يفشل ضد base_code...",\n'
            '  "patched_code": {"path/to/file.py": "...نفس المسار بعد إصلاح الخطأ فقط..."}\n'
            '}'
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
