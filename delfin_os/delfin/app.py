"""تجميع النظام كله. نقطة واحدة تبني الطبقات وتربطها."""
import os
import secrets
from dataclasses import dataclass

from .agents.chat import ChatAgent
from .agents.coder import CoderAgent
from .agents.filemanager import FileManagerAgent
from .agents.llm import LLMClient
from .agents.memory_agent import MemoryAgent
from .agents.planner import PlannerAgent
from .agents.quality import QualityGate
from .agents.security_agent import SecurityAgent
from .browser.agent import BrowserAgent
from .core.engine import CoreEngine
from .core.events import EventBus
from .core.plugins import PluginLoader
from .core.resources import ResourceController
from .core.rules import RulesEngine
from .core.state import StateManager
from .memory.engine import MemoryEngine
from .orchestrator.orchestrator import Orchestrator
from .persona.engine import PersonaEngine
from .response.generator import ResponseGenerator
from .safety.layers import (ConstraintStore, DualAuditor, Escalator, IntentMonitor, Integrity,
                            SafetyDataset, SafetyPipeline, llm_auditor, rule_auditor)
from .sandbox.executor import LocalSandbox
from .security.layer import Security
from .tokens.intelligence import TokenIntelligence


@dataclass
class App:
    home: str
    security: object
    state: object
    memory: object
    tokens: object
    personas: object
    safety: object
    engine: object
    orchestrator: object
    plugins: object
    bus: object
    integrity: object
    canary: str


def _secret(home, name):
    p = os.path.join(home, name)
    if not os.path.exists(p):
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.write(fd, secrets.token_hex(32).encode())
        os.close(fd)
    return open(p).read().strip()


def build_app(home, llm=None, auditor_llm=None, sandbox=None, workspace=None, notifier=None,
              company_context="", allowed_domains=None, resolver=None, code_root=None, browser_fetcher=None):
    os.makedirs(home, mode=0o700, exist_ok=True)
    sec = Security(home, allowed_domains=allowed_domains, resolver=resolver)
    owner_secret = _secret(home, "owner_secret")          # سر المالك: لا يُمرَّر لأي وكيل
    canary = _secret(home, "canary")[:10].upper()
    state = StateManager(os.path.join(home, "state.db"), sec.scanner.redact)
    memory = MemoryEngine(os.path.join(home, "memory.db"), sec.scanner)
    tokens = TokenIntelligence(os.path.join(home, "tokens.db"))
    personas, bus, rules = PersonaEngine(), EventBus(), RulesEngine()
    resources, plugins = ResourceController(), PluginLoader()
    store = ConstraintStore(os.path.join(home, "constraints.json"), owner_secret)
    integrity = Integrity(code_root or os.path.dirname(os.path.dirname(__file__)), owner_secret,
                          os.path.join(home, "manifest.json"))
    from .safety.layers import Escalator as _E
    esc = _E(sec.audit, notifier, sec.scanner)
    auditors = [rule_auditor(store)] + ([llm_auditor(auditor_llm)] if auditor_llm else [])
    safety = SafetyPipeline(store, IntentMonitor(), DualAuditor(auditors),
                            SafetyDataset(os.path.join(home, "safety_data.jsonl"), sec.scanner),
                            integrity, esc, sec.audit, sec.behavior)
    engine = CoreEngine(state, bus, rules, plugins, resources, safety, sec.validator)
    gate = QualityGate(sec.scanner)
    responses = ResponseGenerator(sec.scanner, canary)
    ws = workspace or os.path.join(home, "workspace")
    sandbox = sandbox or LocalSandbox(dev_mode=False)      # مقفل افتراضياً حتى يُربط عزل حقيقي
    if llm is not None:
        plugins.register(ChatAgent(llm, memory, personas, responses, tokens, canary, company_context))
        plugins.register(PlannerAgent(llm, rules.max_steps))
        plugins.register(CoderAgent(llm, sandbox, gate, sec.scanner))
    plugins.register(FileManagerAgent(ws, sec.paths, sec.scanner))
    plugins.register(MemoryAgent(memory))
    plugins.register(SecurityAgent(sec))
    plugins.register(BrowserAgent(sec.links, sec.validator, browser_fetcher))
    return App(home, sec, state, memory, tokens, personas, safety, engine, Orchestrator(engine), plugins,
               bus, integrity, canary)


def attach_github(app, broker):
    from .agents.github_broker import GitHubAgent
    app.plugins.register(GitHubAgent(broker))
