"""MemoryVault — ذاكرة موحّدة بين الجلسات (JSONL + Markdown)."""
from __future__ import annotations
import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional

VAULT_DIR = Path.home() / "Marsad" / "memory"
VAULT_DIR.mkdir(parents=True, exist_ok=True)

# 3 مستويات
PROJECT_LOG = VAULT_DIR / "project.jsonl"
TEAM_LOG    = VAULT_DIR / "team.jsonl"
USER_LOG    = VAULT_DIR / "user.jsonl"


@dataclass
class MemoryEntry:
    ts: float
    level: str          # project | team | user
    key: str
    value: str
    tags: List[str]


class MemoryVault:
    """حفظ + استرجاع السياق بين الجلسات."""

    LOGS = {"project": PROJECT_LOG, "team": TEAM_LOG, "user": USER_LOG}

    @staticmethod
    def save(level: str, key: str, value: str, tags: Optional[List[str]] = None):
        """حفظ ملاحظة."""
        if level not in MemoryVault.LOGS:
            raise ValueError(f"level must be: {list(MemoryVault.LOGS)}")
        entry = MemoryEntry(
            ts=time.time(), level=level, key=key,
            value=value[:5000], tags=tags or [],
        )
        with MemoryVault.LOGS[level].open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")

    @staticmethod
    def load(level: str, limit: int = 50) -> List[MemoryEntry]:
        """تحميل آخر N ملاحظة."""
        f = MemoryVault.LOGS.get(level)
        if not f or not f.exists():
            return []
        lines = f.read_text().splitlines()[-limit:]
        out = []
        for line in lines:
            try:
                d = json.loads(line)
                out.append(MemoryEntry(**d))
            except Exception:
                continue
        return out

    @staticmethod
    def search(level: str, keyword: str) -> List[MemoryEntry]:
        """بحث بسيط بالكلمة المفتاحية."""
        entries = MemoryVault.load(level, limit=1000)
        kw = keyword.lower()
        return [e for e in entries
                if kw in e.key.lower() or kw in e.value.lower()
                or any(kw in t.lower() for t in e.tags)]

    @staticmethod
    def summary() -> str:
        """ملخص محمول لجلسة جديدة."""
        parts = ["◈ <b>Memory Vault Summary</b>"]
        for level in ["project", "team", "user"]:
            entries = MemoryVault.load(level, limit=10)
            parts.append(f"\n{S_DIV} <b>{level}</b>: {len(entries)} entries")
            for e in entries[-3:]:
                dt = datetime.fromtimestamp(e.ts).strftime("%m-%d %H:%M")
                parts.append(f"  {dt} | {e.key}: {e.value[:80]}")
        return "\n".join(parts)

    @staticmethod
    def export_markdown() -> str:
        """تقرير قابل للقراءة."""
        md = ["# Memory Vault Export\n",
              f"_{datetime.now().isoformat()}_\n"]
        for level in ["project", "team", "user"]:
            md.append(f"\n## {level.title()}\n")
            for e in MemoryVault.load(level, limit=100):
                dt = datetime.fromtimestamp(e.ts).strftime("%Y-%m-%d %H:%M")
                md.append(f"- **{dt}** [{e.key}] {e.value[:200]}")
        return "\n".join(md)


S_DIV = "│"


if __name__ == "__main__":
    print("=== اختبار MemoryVault ===\n")
    MemoryVault.save("project", "marsad_phase", "Self-Play جاهز", ["milestone"])
    MemoryVault.save("project", "v2_status", "GGUF Q8 يعمل", ["model"])
    MemoryVault.save("team", "ali_note", "علي ساعد في CF", ["team"])

    print("Project entries:", len(MemoryVault.load("project")))
    print("Search 'Self-Play':", len(MemoryVault.search("project", "self-play")))
    print("\n" + MemoryVault.summary()[:400])
    print("\n✓ MemoryVault ready")
