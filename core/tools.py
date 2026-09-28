"""
core/tools.py — سجل الأدوات (Tool Registry)
الأساس الذي تبنى عليه طبقة الوكلاء التنفيذية.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from enum import Enum


class ToolCategory(str, Enum):
    SCAN     = "scan"
    BUILD    = "build"
    COLLECT  = "collect"
    ANALYZE  = "analyze"
    GENERATE = "generate"
    SYSTEM   = "system"


class RiskLevel(str, Enum):
    SAFE     = "safe"
    MODERATE = "moderate"
    HIGH     = "high"
    CRITICAL = "critical"


_RISK_ORDER = [RiskLevel.SAFE, RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.CRITICAL]


@dataclass
class ToolSpec:
    name: str
    description: str
    category: ToolCategory
    risk: RiskLevel = RiskLevel.SAFE
    requires_sandbox: bool = False
    requires_network: bool = False
    requires_gpu: bool = False
    args_schema: Dict[str, str] = field(default_factory=dict)
    handler: Optional[Callable] = None


class ToolRegistry:
    """سجل مركزي لكل الأدوات المتاحة للنموذج."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
        return cls._instance

    def register(self, spec: ToolSpec) -> ToolSpec:
        if spec.name in self._tools:
            raise ValueError(f"Tool already registered: {spec.name}")
        if not callable(spec.handler):
            raise TypeError(f"Tool {spec.name} has no callable handler")
        self._tools[spec.name] = spec
        return spec

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def list(self, category: Optional[ToolCategory] = None,
             max_risk: Optional[RiskLevel] = None) -> List[ToolSpec]:
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        if max_risk:
            tools = [t for t in tools if _RISK_ORDER.index(t.risk)
                     <= _RISK_ORDER.index(max_risk)]
        return tools

    def count(self) -> int:
        return len(self._tools)

    def summary(self) -> Dict[str, int]:
        out = {}
        for t in self._tools.values():
            out[t.category.value] = out.get(t.category.value, 0) + 1
        return out


registry = ToolRegistry()


def tool(name: str, description: str, category: ToolCategory,
         risk: RiskLevel = RiskLevel.SAFE,
         requires_sandbox: bool = False,
         requires_network: bool = False,
         requires_gpu: bool = False):
    """مزخرف لتسجيل أداة بسرعة."""
    def deco(fn: Callable) -> Callable:
        registry.register(ToolSpec(
            name=name, description=description, category=category,
            risk=risk, requires_sandbox=requires_sandbox,
            requires_network=requires_network, requires_gpu=requires_gpu,
            handler=fn,
        ))
        return fn
    return deco


# ─── أمثلة أدوات أساسية ───────────────────────────────────────

@tool("echo", "يرجع النص كما هو", ToolCategory.SYSTEM, RiskLevel.SAFE)
def _echo(text: str = "") -> str:
    return text


@tool("static_scan", "فحص ثابت لملف أو كود",
      ToolCategory.SCAN, RiskLevel.SAFE, requires_sandbox=True)
def _static_scan(target: str = "") -> Dict[str, Any]:
    return {"target": target, "issues": [], "status": "ok"}


@tool("count_lines", "يعد أسطر ملف", ToolCategory.ANALYZE, RiskLevel.SAFE)
def _count_lines(path: str = "") -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return {"path": path, "lines": sum(1 for _ in f)}
    except Exception as e:
        return {"path": path, "error": str(e)}
