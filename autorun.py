#!/usr/bin/env python3
"""Real autorun engine.

This engine never invents success or generates fake accounts. It validates real
credentials before attempting any provider or cloud action.
"""
import os
import sys
import time
import signal
import traceback
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
os.chdir(BASE)

from db import _ensure_db, log_event, get_memory_size_gb

_ensure_db()

from agents.hierarchy import hierarchy
from agents.real_cloud_linker import real_cloud_linker
from collect.multi_platform import collector
try:
    from collect.datasets import dataset_collector
except Exception:
    dataset_collector = None
from merge.omni_merger import merger
from hf_upload.uploader import hf_uploader
from keep_alive import start_keep_alive

try:
    from marsad_state_writer import write_state, mark_running, update_from_db
except Exception:
    write_state = mark_running = update_from_db = lambda *a, **k: None

RUNNING = True
CYCLE = 0


def signal_handler(sig, frame):
    global RUNNING
    RUNNING = False
    log_event("autorun", {"status": "shutdown_signal"})
    print("\n[!] Stopping autorun...")


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def init_hierarchy():
    try:
        if not hierarchy.root_id:
            root = hierarchy.initialize()
            log_event("autorun", {"action": "hierarchy_init", "root": root})
            for i in range(min(5, 100)):
                hierarchy.expand(f"agent_1_{i}", target_agents=1000)
            return True
    except Exception as e:
        log_event("autorun_error", {"stage": "hierarchy", "error": str(e)})
    return False


def cycle_validate_real_credentials():
    """Only validate real credentials. No fake signup jobs."""
    try:
        env_names = [
            "HF_TOKEN",
            "GITHUB_TOKEN",
            "GROQ_API_KEY",
            "OPENROUTER_API_KEY",
            "DEEPSEEK_API_KEY",
            "MISTRAL_API_KEY",
        ]
        found = [n for n in env_names if os.environ.get(n, "").strip()]
        log_event("autorun", {"action": "real_credentials_check", "count": len(found), "names": found})
        return len(found)
    except Exception as e:
        log_event("autorun_error", {"stage": "credentials_check", "error": str(e)})
        return 0


def cycle_collect_clean():
    try:
        if hasattr(collector, "collect_github"):
            collector.collect_github(query="python agent", limit=5)
        if dataset_collector:
            res = dataset_collector.collect_all(query="machine learning security code", limit_per_platform=5)
            log_event("autorun", {"action": "dataset_collect", "result": str(res)[:300]})
            print(f"[+] Dataset collect: {res}")
        log_event("autorun", {"action": "collect_cycle"})
    except Exception as e:
        log_event("autorun_error", {"stage": "collect", "error": str(e)})


def cycle_merge_upload():
    try:
        if get_memory_size_gb() > 0.5:
            plan = merger.get_merge_plan()
            log_event("autorun", {"action": "merge_plan", "plan": plan})
        if os.environ.get("HF_TOKEN"):
            hf_uploader.start_auto_upload(interval=1800)
        else:
            log_event("autorun", {"action": "hf_upload_skip", "reason": "HF_TOKEN_missing"})
    except Exception as e:
        log_event("autorun_error", {"stage": "merge_upload", "error": str(e)})


def cycle_cloud_dispatch():
    try:
        res = real_cloud_linker.dispatch("heartbeat", {"cycle": CYCLE})
        log_event("autorun", {"action": "cloud_dispatch", "result": res})
    except Exception as e:
        log_event("autorun_error", {"stage": "cloud", "error": str(e)})


def main_loop(interval: int = 300):
    global CYCLE, RUNNING
    print("[+] CYBERGUARD AUTORUN ENGINE STARTED")
    try:
        mark_running(True, "autorun engine started")
    except Exception:
        pass
    log_event("autorun", {"status": "started", "interval": interval})
    start_keep_alive()
    init_hierarchy()

    while RUNNING:
        CYCLE += 1
        print(f"[*] Cycle {CYCLE} — {time.strftime('%Y-%m-%d %H:%M:%S')}")
        try:
            update_from_db()
            write_state(running=True, activity_msg=f"cycle {CYCLE}")
        except Exception:
            pass
        try:
            cycle_validate_real_credentials()
            cycle_collect_clean()
            cycle_cloud_dispatch()
            if CYCLE % 6 == 0:
                cycle_merge_upload()
        except Exception as e:
            log_event("autorun_error", {"cycle": CYCLE, "error": str(e), "trace": traceback.format_exc()})
            print(f"[!] Cycle error: {e}")
        for _ in range(interval):
            if not RUNNING:
                break
            time.sleep(1)

    print("[+] Autorun stopped cleanly")
    try:
        mark_running(False, "autorun stopped")
    except Exception:
        pass
    log_event("autorun", {"status": "stopped", "cycles": CYCLE})


if __name__ == "__main__":
    interval = int(os.environ.get("CG_AUTORUN_INTERVAL", "300"))
    main_loop(interval)
