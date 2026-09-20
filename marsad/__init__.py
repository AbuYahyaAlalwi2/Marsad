from .agents.swarm import AgentSwarm
from .agents.collector import DataCollector
from .agents.distiller import Distiller
from .agents.general import GeneralAgent
from .agents.email_agent import EmailAgent
from .agents.signup_agent import SignupAgent
from .agents.worker_agent import WorkerAgent
from .clouds.manager import CloudManager
from .dashboard.app import Dashboard
from .utils.vault import KeyVault
from .utils.ip_rotator import SmartRequest, IPRotator
from .workflow import Workflow

__version__ = "1.0.0"
__all__ = [
    "AgentSwarm",
    "DataCollector",
    "Distiller",
    "GeneralAgent",
    "EmailAgent",
    "SignupAgent",
    "WorkerAgent",
    "CloudManager",
    "Dashboard",
    "KeyVault",
    "SmartRequest",
    "IPRotator",
    "Workflow",
]
