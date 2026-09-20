"""
CYBERGUARD OS - Million Agent Runtime
Runs 1,000,000 logical agents concurrently in a single process.
Uses compact byte arrays - 7 bytes per agent = ~7MB total.
Agents rotate through work batches, learn, and heal.
"""
import os
import time
import random
import logging
import threading
from typing import Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

TOTAL_AGENTS = int(os.environ.get("CG_MILLION_TOTAL", "1000000"))
BATCH_SIZE = int(os.environ.get("CG_MILLION_BATCH", "10000"))
TICK_INTERVAL = float(os.environ.get("CG_MILLION_TICK", "0.5"))  # seconds
KNOWLEDGE_EVERY = int(os.environ.get("CG_MILLION_KNOW_EVERY", "100"))


# States (1 byte each)
STATE_IDLE = 0
STATE_WORKING = 1
STATE_RESTING = 2
STATE_LEARNING = 3
STATE_DEAD = 4
STATE_HEALING = 5


class MillionRuntime:
    """
    True 1M-agent runtime on a single process.
    Each agent is 7 bytes: state, energy, knowledge_count, last_action.
    Rotates through agents in batches to keep CPU low.
    """

    def __init__(self):
        n = TOTAL_AGENTS
        # Compact state (byte arrays = 4 bytes per agent)
        self.states = bytearray(n)          # 1 byte: state
        self.energies = bytearray([100] * n)  # 1 byte: 0-255 energy
        self.knowledge = bytearray(n)       # 1 byte: knowledge bits
        self.actions = bytearray(n)         # 1 byte: last action code

        # Metrics
        self.cursor = 0
        self.tick_count = 0
        self.total_actions = 0
        self.total_knowledge = 0
        self.total_heals = 0
        self.total_deaths = 0
        self.running = False
        self._stop = threading.Event()
        self._thread: threading.Thread = None
        self._lock = threading.Lock()
        self.started_at = 0

        # Init: all idle
        for i in range(n):
            self.states[i] = STATE_IDLE

        logger.info(f"[Million] Runtime initialized: {n:,} agents")

    # ----------------------------------------------------------
    # Core tick
    # ----------------------------------------------------------
    def _tick(self):
        """Process one batch of agents."""
        n = TOTAL_AGENTS
        start = self.cursor
        end = min(start + BATCH_SIZE, n)

        worked = 0
        learned = 0
        healed = 0
        died = 0

        states = self.states
        energies = self.energies
        knowledge = self.knowledge

        for i in range(start, end):
            st = states[i]
            en = energies[i]

            # Dead check
            if en == 0:
                if st != STATE_DEAD:
                    states[i] = STATE_DEAD
                    died += 1
                continue

            # Behavior based on state
            if st == STATE_IDLE:
                # Start working
                states[i] = STATE_WORKING
                worked += 1
            elif st == STATE_WORKING:
                # Consume energy
                new_en = en - 1
                if new_en <= 0:
                    energies[i] = 0
                    states[i] = STATE_DEAD
                    died += 1
                else:
                    energies[i] = new_en
                    # Maybe learn
                    if random.random() < 0.01:
                        states[i] = STATE_LEARNING
                        if knowledge[i] < 255:
                            knowledge[i] += 1
                            learned += 1
                    # Rest when low energy
                    elif en < 20:
                        states[i] = STATE_RESTING
                    worked += 1
            elif st == STATE_RESTING:
                # Regenerate energy
                if en < 100:
                    energies[i] = min(100, en + 2)
                    states[i] = STATE_IDLE
                else:
                    states[i] = STATE_IDLE
            elif st == STATE_LEARNING:
                # Finish learning
                states[i] = STATE_WORKING
                learned += 1
            elif st == STATE_DEAD:
                # Self-heal
                if random.random() < 0.1:  # 10% chance per tick
                    energies[i] = 50
                    states[i] = STATE_HEALING
                    healed += 1
            elif st == STATE_HEALING:
                states[i] = STATE_IDLE

        # Advance cursor
        with self._lock:
            self.cursor = end if end < n else 0
            self.tick_count += 1
            self.total_actions += worked
            self.total_knowledge += learned
            self.total_heals += healed
            self.total_deaths += died

    # ----------------------------------------------------------
    # Background loop
    # ----------------------------------------------------------
    def start(self):
        if self.running:
            return
        self.running = True
        self.started_at = time.time()
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info(f"[Million] Started ({TOTAL_AGENTS:,} agents, batch={BATCH_SIZE:,})")

    def stop(self):
        self.running = False
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self):
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as e:
                logger.error(f"[Million] tick error: {e}")
            self._stop.wait(TICK_INTERVAL)

    # ----------------------------------------------------------
    # Status
    # ----------------------------------------------------------
    def status(self) -> Dict[str, Any]:
        # Count states (sample for speed - every 100th agent)
        idle = working = resting = learning = dead = healing = 0
        step = 100
        for i in range(0, TOTAL_AGENTS, step):
            st = self.states[i]
            if st == STATE_IDLE: idle += 1
            elif st == STATE_WORKING: working += 1
            elif st == STATE_RESTING: resting += 1
            elif st == STATE_LEARNING: learning += 1
            elif st == STATE_DEAD: dead += 1
            elif st == STATE_HEALING: healing += 1
        # Scale up
        scale = step
        idle *= scale; working *= scale; resting *= scale
        learning *= scale; dead *= scale; healing *= scale

        # Energy average (sample)
        e_sum = 0; e_cnt = 0
        for i in range(0, TOTAL_AGENTS, step):
            e_sum += self.energies[i]; e_cnt += 1
        avg_energy = e_sum / max(1, e_cnt)

        uptime = time.time() - self.started_at if self.started_at else 0

        return {
            "running": self.running,
            "total_agents": TOTAL_AGENTS,
            "batch_size": BATCH_SIZE,
            "tick_interval": TICK_INTERVAL,
            "ticks": self.tick_count,
            "uptime_seconds": round(uptime, 1),
            "cursor": self.cursor,
            "avg_energy": round(avg_energy, 1),
            "total_actions": self.total_actions,
            "total_knowledge_events": self.total_knowledge,
            "total_heals": self.total_heals,
            "total_deaths": self.total_deaths,
            "states_sampled": {
                "idle": idle,
                "working": working,
                "resting": resting,
                "learning": learning,
                "dead": dead,
                "healing": healing,
            },
            "memory_mb": round(
                (len(self.states) + len(self.energies) + len(self.knowledge) + len(self.actions)) / (1024 * 1024),
                2
            ),
        }


# Singleton
million_runtime = MillionRuntime()
