"""
CYBERGUARD OS - Critic Agent
Reviews code BEFORE delivery. Rejects bad code.
Uses Pydantic AI if available, falls back to LLM providers, then heuristic.
"""
import json
import re
import logging
from typing import Dict, Any, List, Optional

from config import CRITIC_ENABLED, CRITIC_MODEL, CRITIC_MAX_RETRIES
from db import log_event

logger = logging.getLogger(__name__)


CRITIC_SYSTEM_PROMPT = """You are a senior code reviewer.
Analyze the given code and return STRICT JSON only:
{
  "approved": true/false,
  "score": 0-100,
  "issues": [{"line": int, "severity": "critical|high|medium|low", "message": str}],
  "suggestions": [str],
  "summary": str
}
Reject code with security issues, logic bugs, or poor style.
Focus: correctness, security, performance, readability.
Return ONLY the JSON, no text before or after.
"""


class CriticAgent:
    def __init__(self):
        self._pydantic_agent = None
        if CRITIC_ENABLED:
            self._try_init_pydantic()

    def _try_init_pydantic(self):
        try:
            from pydantic_ai import Agent
            self._pydantic_agent = Agent(CRITIC_MODEL,
                                          system_prompt=CRITIC_SYSTEM_PROMPT)
            logger.info("[Critic] Pydantic AI ready")
        except ImportError:
            logger.warning("[Critic] pydantic-ai not installed - using LLM providers")
            self._pydantic_agent = None
        except Exception as e:
            logger.warning(f"[Critic] Pydantic init failed: {e}")
            self._pydantic_agent = None

    def review(self, code: str, language: str = "python") -> Dict[str, Any]:
        if not CRITIC_ENABLED:
            return {"approved": True, "score": 100, "issues": [],
                    "suggestions": [], "summary": "Critic disabled"}

        if not code or not code.strip():
            return {"approved": False, "score": 0,
                    "issues": [{"line": 0, "severity": "critical",
                                "message": "Empty code"}],
                    "suggestions": [],
                    "summary": "Code is empty"}

        prompt = f"Language: {language}\n\nCode:\n```{language}\n{code}\n```"

        result = None
        if self._pydantic_agent:
            result = self._review_pydantic(prompt)

        if result is None:
            result = self._review_via_llm(prompt)

        if result is None:
            result = self._heuristic_review(code, language)

        try:
            log_event("critic", {
                "approved": result.get("approved"),
                "score": result.get("score"),
                "issues_count": len(result.get("issues", [])),
                "language": language,
            })
        except Exception:
            pass

        return result

    def _review_pydantic(self, prompt: str) -> Optional[Dict]:
        try:
            r = self._pydantic_agent.run_sync(prompt)
            text = r.data if hasattr(r, "data") else str(r)
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                return json.loads(m.group(0))
        except Exception as e:
            logger.warning(f"[Critic] Pydantic review failed: {e}")
        return None

    def _review_via_llm(self, prompt: str) -> Optional[Dict]:
        try:
            from providers.llm_providers import llm_providers
            r = llm_providers.generate(prompt)
            if r.get("status") == "success":
                text = r.get("text", "")
                m = re.search(r"\{.*\}", text, re.DOTALL)
                if m:
                    return json.loads(m.group(0))
        except Exception as e:
            logger.warning(f"[Critic] LLM review failed: {e}")
        return None

    def _heuristic_review(self, code: str, language: str) -> Dict:
        issues: List[Dict] = []
        score = 100

        dangerous = [
            ("eval(", "critical", "Use of eval() is dangerous"),
            ("exec(", "critical", "Use of exec() is dangerous"),
            ("subprocess", "high", "subprocess usage - verify input sanitization"),
            ("os.system", "high", "os.system usage - prefer subprocess"),
            ("pickle.loads", "high", "pickle.loads on untrusted data"),
            ("__import__", "medium", "Dynamic import detected"),
            ("shell=True", "high", "shell=True can lead to injection"),
            ("rm -rf /", "critical", "Destructive command detected"),
        ]
        for pattern, severity, msg in dangerous:
            if pattern in code:
                issues.append({"line": 0, "severity": severity, "message": msg})
                penalty = {"critical": 25, "high": 15, "medium": 8, "low": 3}[severity]
                score -= penalty

        if "    " not in code and "\t" not in code and "\n" in code:
            issues.append({"line": 0, "severity": "low",
                           "message": "No indentation detected"})
            score -= 3

        approved = score >= 70
        return {
            "approved": approved,
            "score": max(0, score),
            "issues": issues,
            "suggestions": ["Run sandbox tests before deploying"] if approved else [],
            "summary": f"Heuristic review: {len(issues)} issues found",
            "heuristic": True,
        }

    def review_and_fix(self, code: str, language: str = "python",
                       fixer=None) -> Dict[str, Any]:
        for attempt in range(CRITIC_MAX_RETRIES + 1):
            r = self.review(code, language)
            if r.get("approved"):
                r["attempts"] = attempt
                return r
            if fixer and attempt < CRITIC_MAX_RETRIES:
                try:
                    code = fixer(code, r)
                except Exception as e:
                    logger.warning(f"[Critic] fixer failed: {e}")
                    break
        return r


critic_agent = CriticAgent()
