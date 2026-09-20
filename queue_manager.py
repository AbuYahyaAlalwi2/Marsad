"""
CYBERGUARD OS - Queue Manager (Huey + SQLite, no Redis)
"""
import os
import logging
from typing import Optional, Dict, Any

from config import (
    TASK_QUEUE_DB_PATH as _CFG_DB,
    TASK_QUEUE_MAX_RETRIES as _CFG_RETRIES,
    TASK_QUEUE_RETRY_DELAY as _CFG_DELAY,
    DATA_DIR,
)

logger = logging.getLogger(__name__)
os.makedirs(DATA_DIR, exist_ok=True)

TASK_QUEUE_DB_PATH = os.environ.get("CG_QUEUE_DB_PATH", _CFG_DB)
TASK_QUEUE_MAX_RETRIES = _CFG_RETRIES
TASK_QUEUE_RETRY_DELAY = _CFG_DELAY

from huey import SqliteHuey

app = SqliteHuey(
    name="cyberguard",
    filename=TASK_QUEUE_DB_PATH,
    results=True,
)
_backend = "huey"
logger.info(f"[Queue] Huey (SQLite: {TASK_QUEUE_DB_PATH})")


def get_backend() -> str:
    return _backend


# ============================================================
# TASK BODIES
# ============================================================
def _task_run_agent(agent_id, task_type, payload):
    try:
        from agents.worker_agent import WorkerAgent
        agent = WorkerAgent(agent_id)
        return {"status": "ok", "agent_id": agent_id,
                "result": agent.run(task_type, **payload)}
    except Exception as e:
        logger.error(f"[Queue] agent task failed: {e}")
        raise


def _task_collect(platform, query, limit=50):
    try:
        from collect.multi_platform import collector
        return {"status": "ok", "platform": platform,
                "result": collector.collect_from_specific_platform(platform, query, limit)}
    except Exception as e:
        logger.error(f"[Queue] collection failed: {e}")
        raise


def _task_cloud_health(provider_name):
    try:
        from cloud_health import CloudHealthMonitor
        return CloudHealthMonitor().check_provider(provider_name)
    except Exception as e:
        logger.error(f"[Queue] cloud health failed: {e}")
        raise


def _task_cloud_provision(provider_name, country=None):
    try:
        from cloud_provisioner import CloudProvisioner
        return CloudProvisioner().provision(provider_name, country)
    except Exception as e:
        logger.error(f"[Queue] provision failed: {e}")
        raise


def _task_sandbox(code, language="python"):
    try:
        from sandbox_agent import SandboxAgent
        return SandboxAgent().run(code, language)
    except Exception as e:
        logger.error(f"[Queue] sandbox failed: {e}")
        raise


def _task_critic(code, language="python"):
    try:
        from critic_agent import CriticAgent
        return CriticAgent().review(code, language)
    except Exception as e:
        logger.error(f"[Queue] critic failed: {e}")
        raise


# ============================================================
# HUEY TASKS
# ============================================================
@app.task(retries=TASK_QUEUE_MAX_RETRIES, retry_delay=TASK_QUEUE_RETRY_DELAY, priority=50)
def run_agent_task(agent_id, task_type, payload):
    return _task_run_agent(agent_id, task_type, payload)


@app.task(retries=5, retry_delay=10.0, priority=60)
def collect_data_task(platform, query, limit=50):
    return _task_collect(platform, query, limit)


@app.task(retries=3, retry_delay=15.0, priority=40)
def cloud_health_check(provider_name):
    return _task_cloud_health(provider_name)


@app.task(retries=2, retry_delay=30.0, priority=30)
def auto_provision_cloud(provider_name, country=None):
    return _task_cloud_provision(provider_name, country)


@app.task(retries=2, retry_delay=5.0, priority=70)
def run_sandbox_task(code, language="python"):
    return _task_sandbox(code, language)


@app.task(retries=1, retry_delay=5.0, priority=80)
def critic_review_task(code, language="python"):
    return _task_critic(code, language)


# ============================================================
# PUBLIC HELPERS
# ============================================================
def enqueue_agent(agent_id, task_type, payload=None):
    return run_agent_task(agent_id, task_type, payload or {})


def enqueue_collect(platform, query, limit=50):
    return collect_data_task(platform, query, limit)


def enqueue_cloud_health(provider_name):
    return cloud_health_check(provider_name)


def enqueue_cloud_provision(provider_name, country=None):
    return auto_provision_cloud(provider_name, country)


def enqueue_sandbox(code, language="python"):
    return run_sandbox_task(code, language)


def enqueue_critic(code, language="python"):
    return critic_review_task(code, language)


if __name__ == "__main__":
    from huey.bin.huey_consumer import Consumer
    Consumer(app).run()
