"""
scenario_generator.py
مولّد سيناريوهات "اختبار سلبي" (Negative Test Case) دفاعي بحت + محرك تصعيد
تعقيد المنطق + إشارة تعلّم تنفيذية.
"""
from __future__ import annotations
import hashlib
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import IntEnum
from typing import Optional
from pydantic import BaseModel, Field, field_validator

class ComplexityTier(IntEnum):
    T1_SINGLE_FUNCTION = 1
    T2_MULTI_FUNCTION = 2
    T3_STATEFUL_FLOW = 3
    T4_MULTI_CONDITION = 4
    T5_LAYERED_LOGIC = 5

    @property
    def min_files(self) -> int:
        return {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}[self.value]

    @property
    def min_real_dependencies(self) -> int:
        return {1: 0, 2: 1, 3: 1, 4: 2, 5: 2}[self.value]

    @property
    def requires_auth_layer(self) -> bool:
        return self.value >= 2

    @property
    def requires_multi_step_defect(self) -> bool:
        return self.value >= 4

LOGIC_DEFECT_CLASSES = [
    "missing_role_check",
    "missing_ownership_check",
    "stale_permission_cache",
    "incorrect_boolean_logic_in_authorization",
    "missing_null_check_before_sensitive_action",
    "race_condition_in_state_update",
    "improper_default_value_grants_access",
    "missing_rate_or_quota_check",
    "inconsistent_validation_between_layers",
    "off_by_one_in_access_boundary",
]

TECH_STACKS = [
    ("python", "fastapi", "postgres"),
    ("python", "flask", "redis"),
    ("node", "express", "mongodb"),
    ("go", "gin", "postgres"),
    ("python", "django", "postgres"),
]

class ScenarioBlueprint(BaseModel):
    scenario_id: str
    tier: ComplexityTier
    defect_class: str
    stack: tuple[str, str, str]
    min_files: int
    min_real_dependencies: int
    requires_auth_layer: bool
    requires_multi_step_defect: bool
    narrative_brief: str
    forbidden_patterns: list[str] = Field(
        default_factory=lambda: [
            "hello_world", "single_route_app", "no_persistence_layer",
            "exploit", "payload", "attack_string", "shell_injection",
            "reverse_shell", "sql_injection_payload",
        ]
    )
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("defect_class")
    @classmethod
    def _known_defect(cls, v: str) -> str:
        if v not in LOGIC_DEFECT_CLASSES:
            raise ValueError(f"فئة خطأ منطقي غير معروفة: {v}")
        return v

    def validate_against_rules(self) -> None:
        if self.min_files != self.tier.min_files:
            raise ValueError("min_files لا يطابق متطلبات المستوى")
        if self.min_real_dependencies != self.tier.min_real_dependencies:
            raise ValueError("min_real_dependencies لا يطابق متطلبات المستوى")
        if self.requires_auth_layer != self.tier.requires_auth_layer:
            raise ValueError("شرط طبقة المصادقة لا يطابق المستوى")
        if self.requires_multi_step_defect != self.tier.requires_multi_step_defect:
            raise ValueError("شرط الخطأ متعدد الشروط لا يطابق المستوى")

class ScenarioGenerator:
    def __init__(self, escalator: "ComplexityEscalator"):
        self._escalator = escalator

    def generate(self, agent_id: str, defect_class: Optional[str] = None) -> ScenarioBlueprint:
        tier = self._escalator.current_tier(agent_id)
        chosen_defect = defect_class or random.choice(LOGIC_DEFECT_CLASSES)
        stack = random.choice(TECH_STACKS)
        scenario_id = hashlib.sha256(
            f"{agent_id}:{tier.value}:{chosen_defect}:{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:12]
        blueprint = ScenarioBlueprint(
            scenario_id=scenario_id,
            tier=tier,
            defect_class=chosen_defect,
            stack=stack,
            min_files=tier.min_files,
            min_real_dependencies=tier.min_real_dependencies,
            requires_auth_layer=tier.requires_auth_layer,
            requires_multi_step_defect=tier.requires_multi_step_defect,
            narrative_brief=self._brief(tier, chosen_defect, stack),
        )
        blueprint.validate_against_rules()
        return blueprint

    @staticmethod
    def _brief(tier: ComplexityTier, defect_class: str, stack: tuple[str, str, str]) -> str:
        lang, framework, datastore = stack
        base = (
            f"اكتب برنامجاً صغيراً وحقيقياً بلغة {lang} (إطار {framework}، تخزين {datastore} إن لزم)، "
            f"يحتوي خطأً منطقياً واحداً من فئة '{defect_class}' — خطأ في التدفق البرمجي "
            f"(مثال نمطي: غياب التحقق من دور المستخدم قبل تنفيذ دالة حساسة)، وليس أي كود هجوم أو payload. "
            "ممنوع منعاً باتاً أي exploit code أو payload ضار أو محاولة اختراق فعلية — المطلوب فقط خطأ "
            "منطقي في شرط أو تحقق ناقص.\n\n"
            "أرجع بالضبط ثلاثة مكونات:\n"
            "1) الكود الأساسي (base_code) الذي يحتوي الخطأ.\n"
            "2) اختبار تحقق (verification_test) بصيغة pytest/assert بسيطة، يجب أن يفشل "
            "(AssertionError) عند تشغيله ضد الكود الأساسي — هذا ما يثبت وجود الخطأ منطقياً.\n"
            "3) الكود المُصحَّح (patched_code): نفس الكود الأساسي بعد إضافة الفحص/الشرط الناقص فقط، "
            "بحيث ينجح نفس اختبار التحقق عند تشغيله ضده.\n"
        )
        if tier.requires_auth_layer:
            base += "يجب أن يملك البرنامج طبقة مصادقة/أدوار حقيقية بسيطة بين نوعين من المستخدمين على الأقل.\n"
        if tier.requires_multi_step_defect:
            base += (
                "الخطأ يجب ألا يظهر إلا عند اجتماع أكثر من شرط منطقي معاً (مثال: الدور صحيح لكن حالة "
                "الكائن قديمة)، لا خطأ مباشر في سطر واحد معزول.\n"
            )
        return base

@dataclass
class AgentProgress:
    agent_id: str
    tier: ComplexityTier = ComplexityTier.T1_SINGLE_FUNCTION
    consecutive_successes: int = 0
    consecutive_failures: int = 0
    total_rounds: int = 0

class ComplexityEscalator:
    MAX_TIER = ComplexityTier.T5_LAYERED_LOGIC
    PROMOTE_AFTER = 2
    FREEZE_AFTER_FAILURES = 3

    def __init__(self):
        self._progress: dict[str, AgentProgress] = {}

    def current_tier(self, agent_id: str) -> ComplexityTier:
        return self._progress.setdefault(agent_id, AgentProgress(agent_id=agent_id)).tier

    def record_outcome(self, agent_id: str, *, defect_confirmed: bool, fix_verified: bool) -> AgentProgress:
        p = self._progress.setdefault(agent_id, AgentProgress(agent_id=agent_id))
        p.total_rounds += 1
        full_success = defect_confirmed and fix_verified
        if full_success:
            p.consecutive_successes += 1
            p.consecutive_failures = 0
            if p.consecutive_successes >= self.PROMOTE_AFTER and p.tier < self.MAX_TIER:
                p.tier = ComplexityTier(p.tier.value + 1)
                p.consecutive_successes = 0
        else:
            p.consecutive_failures += 1
            p.consecutive_successes = 0
        return p
