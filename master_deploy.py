"""
CYBERGUARD OS - Master Deployer
Deploys worker nodes across 10+ cloud providers automatically.
Goal: 100 workers * 10,000 agents = 1,000,000 agents.
"""
import os
import sys
import time
import json
import logging
import subprocess
import threading
from typing import Dict, List, Any, Optional
from pathlib import Path

BASE = Path(__file__).resolve().parent
os.chdir(BASE)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("master_deploy")


CLOUD_TARGETS = [
    # (name, deploy_command_template, max_workers, cost)
    ("fly",     "fly scale count {count} --app marsad-worker",      100, "free"),
    ("railway", "railway scale --service marsad-worker --count {count}", 50, "trial"),
    ("render",  "render deploy --service marsad-worker --count {count}",  25, "free"),
    ("koyeb",   "koyeb app scale marsad-worker --replicas {count}",  50, "free"),
    ("northflank", "northflank scale marsad-worker --count {count}",  25, "trial"),
]


class MasterDeployer:
    """
    Deploys worker nodes to multiple cloud providers.
    Monitors rollout, reports status.
    """

    def __init__(self):
        self.deployments: Dict[str, Dict] = {}
        self.target_agents = int(os.environ.get("CG_TARGET_AGENTS", "1000000"))
        self.agents_per_worker = int(os.environ.get("CG_WORKER_CAPACITY", "10000"))
        self.workers_needed = self.target_agents // self.agents_per_worker

    # ------------------------------------------------------------
    # Preflight
    # ------------------------------------------------------------
    def preflight(self) -> Dict[str, Any]:
        """Check CLIs and tokens available."""
        checks = {}
        for name, cmd_template, max_w, cost in CLOUD_TARGETS:
            cli = cmd_template.split()[0]
            checks[name] = {
                "cli": cli,
                "installed": self._which(cli) is not None,
                "max_workers": max_w,
                "cost": cost,
            }
        return checks

    def _which(self, cmd: str) -> Optional[str]:
        try:
            r = subprocess.run(["which", cmd], capture_output=True, text=True)
            return r.stdout.strip() if r.returncode == 0 else None
        except Exception:
            return None

    # ------------------------------------------------------------
    # Deployment plan
    # ------------------------------------------------------------
    def plan(self) -> Dict[str, Any]:
        """Compute deployment plan to reach target agents."""
        needed = self.workers_needed
        plan = []
        remaining = needed

        for name, cmd_template, max_w, cost in CLOUD_TARGETS:
            if remaining <= 0:
                break
            take = min(max_w, remaining)
            plan.append({
                "provider": name,
                "workers": take,
                "agents": take * self.agents_per_worker,
                "cost": cost,
            })
            remaining -= take

        return {
            "target_agents": self.target_agents,
            "agents_per_worker": self.agents_per_worker,
            "workers_needed": needed,
            "plan": plan,
            "shortfall": remaining * self.agents_per_worker if remaining > 0 else 0,
        }

    # ------------------------------------------------------------
    # Execute deployment
    # ------------------------------------------------------------
    def deploy_all(self, dry_run: bool = True) -> Dict[str, Any]:
        """Deploy to all configured clouds."""
        p = self.plan()
        results = []
        total_workers = 0
        total_agents = 0

        for item in p["plan"]:
            provider = item["provider"]
            count = item["workers"]

            # Find command
            cmd_template = next((c for n, c, _, _ in CLOUD_TARGETS if n == provider), None)
            if not cmd_template:
                continue

            cmd = cmd_template.format(count=count)

            if dry_run:
                result = {
                    "provider": provider,
                    "workers": count,
                    "agents": item["agents"],
                    "command": cmd,
                    "status": "planned",
                }
            else:
                r = self._run_command(cmd)
                result = {
                    "provider": provider,
                    "workers": count,
                    "agents": item["agents"],
                    "command": cmd,
                    "status": "success" if r["ok"] else "failed",
                    "output": r["output"][-500:] if r["output"] else "",
                }
                if r["ok"]:
                    total_workers += count
                    total_agents += item["agents"]

            results.append(result)
            self.deployments[provider] = result

        return {
            "dry_run": dry_run,
            "target": self.target_agents,
            "achieved_workers": total_workers,
            "achieved_agents": total_agents,
            "results": results,
        }

    def _run_command(self, cmd: str) -> Dict:
        try:
            r = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=300
            )
            return {
                "ok": r.returncode == 0,
                "output": r.stdout + r.stderr,
            }
        except Exception as e:
            return {"ok": False, "output": str(e)}

    # ------------------------------------------------------------
    # Status
    # ------------------------------------------------------------
    def status(self) -> Dict[str, Any]:
        try:
            from distributed_manager import distributed_manager
            dist = distributed_manager.status()
        except Exception:
            dist = {"online_workers": 0, "total_capacity": 0, "active_agents": 0}

        return {
            "target_agents": self.target_agents,
            "agents_per_worker": self.agents_per_worker,
            "workers_needed": self.workers_needed,
            "live": dist,
            "deployments": self.deployments,
        }


# Singleton
master_deployer = MasterDeployer()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--deploy", action="store_true", help="Actually deploy")
    parser.add_argument("--plan", action="store_true", help="Show plan")
    parser.add_argument("--preflight", action="store_true", help="Check CLIs")
    args = parser.parse_args()

    if args.preflight:
        print(json.dumps(master_deployer.preflight(), indent=2, ensure_ascii=False))
    elif args.plan:
        print(json.dumps(master_deployer.plan(), indent=2, ensure_ascii=False))
    elif args.deploy:
        print(json.dumps(master_deployer.deploy_all(dry_run=False),
                        indent=2, ensure_ascii=False))
    else:
        print(json.dumps(master_deployer.deploy_all(dry_run=True),
                        indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
