"""One Stargazer episode: task, evaluator, budgets, and on-disk run state.

Run state lives in ``run_dir`` so that several tool-server processes (one per
Omnigent sub-agent session) share submission counts and the research record.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import fcntl
except ImportError:  # Windows development/UI runs
    fcntl = None
    import msvcrt

import numpy as np

REPO = Path(__file__).resolve().parents[1]
STARGAZER = REPO / "third_party" / "Stargazer"
if str(STARGAZER) not in sys.path:
    sys.path.insert(0, str(STARGAZER))

from stargazer.bank import TaskBank  # noqa: E402
from stargazer.env import RvEnv  # noqa: E402
from stargazer.engine_rebound import simulate_clean_rv  # noqa: E402
from stargazer.limits import DEFAULT_SUBMISSION_MAX_PLANETS  # noqa: E402

BANKS = {
    "synthetic": STARGAZER / "stargazer" / "Stargazer_synthetic_task",
    "real": STARGAZER / "stargazer" / "Stargazer_real_data_task",
}

# Stargazer's per-tier budgets (run_agent_batch._DIFFICULTY_BUDGETS).
TIER_BUDGETS = {
    "easy": {"max_tokens": 200_000, "max_submissions": 3, "max_time": 600},
    "medium": {"max_tokens": 450_000, "max_submissions": 5, "max_time": 900},
    "hard": {"max_tokens": 900_000, "max_submissions": 10, "max_time": 1500},
}

# The REPL runs in this process, which also holds the ground truth. Refuse code
# that reaches for it; the transcript audit in the runner checks the same terms.
FORBIDDEN = ("Stargazer_synthetic_task", "Stargazer_real_data_task", "third_party", "lab.episode", "TaskBank", "environ")


def bank_for(task_id: str) -> str:
    return "real" if task_id.startswith("real_") else "synthetic"


def tier_for(task_id: str, difficulty: Optional[int]) -> str:
    # The paper does not state a tier for real-data tasks; give them the hard budget.
    if bank_for(task_id) == "real":
        return "hard"
    if difficulty is None or difficulty <= 2:
        return "easy"
    return "medium" if difficulty <= 6 else "hard"


class Episode:
    def __init__(self, task_id: str, run_dir: Path):
        self.task_id = task_id
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.task = TaskBank(str(BANKS[bank_for(task_id)])).load_task(task_id)
        self.tier = tier_for(task_id, self.task.truth_difficulty)
        self.budget = TIER_BUDGETS[self.tier]
        self.max_planets = DEFAULT_SUBMISSION_MAX_PLANETS
        # Submission counting is done in run_dir state, not by the env.
        self.env = RvEnv(task=self.task, submission_mode="params_and_model", max_steps=10**6)
        self.obs, _ = self.env.reset()
        self._load_added_observations()
        with self._locked():
            if not (self.run_dir / "state.json").exists():
                (self.run_dir / "state.json").write_text(json.dumps(self._read_state()))

    # -- observation views -------------------------------------------------
    @property
    def times(self) -> np.ndarray:
        return np.asarray(self.obs["times_days"], dtype=float)

    @property
    def rvs(self) -> np.ndarray:
        return np.asarray(self.obs["rvs_ms"], dtype=float)

    @property
    def sigmas(self) -> np.ndarray:
        return np.asarray(self.obs["sigmas_ms"], dtype=float)

    @property
    def instruments(self) -> list:
        return list(self.obs["instruments"])

    @property
    def star_mass_sun(self) -> float:
        return float(self.obs["meta"]["star_mass_sun"])

    def _load_added_observations(self) -> None:
        """Overlay synthetic follow-up observations without changing TaskBank data."""
        rows = self.read("observations")
        if not rows:
            return
        self.obs["times_days"] = list(self.obs["times_days"]) + [r["time_days"] for r in rows]
        self.obs["rvs_ms"] = list(self.obs["rvs_ms"]) + [r["rv_ms"] for r in rows]
        self.obs["sigmas_ms"] = list(self.obs["sigmas_ms"]) + [r["sigma_ms"] for r in rows]
        self.obs["instruments"] = list(self.obs["instruments"]) + [r["instrument"] for r in rows]

    def simulate_observation(self, time_days: float, sigma_ms: float, instrument: str) -> Dict[str, Any]:
        """Privately simulate one follow-up datum; no truth parameters are returned."""
        if bank_for(self.task_id) != "synthetic":
            raise ValueError("Simulated observing is disabled for real-data tasks.")
        # Deterministic noise makes runs reproducible while remaining hidden from agents.
        n = len(self.read("observations"))
        seed = int.from_bytes(hashlib.sha256(f"{self.task_id}:{n}:{time_days:.9f}".encode()).digest()[:8], "big")
        rng = np.random.default_rng(seed)
        gamma = self.task.config.star.gamma_ms + next(
            (x.gamma_ms for x in self.task.config.instruments if x.label == instrument), 0.0
        )
        model = float(simulate_clean_rv(self.task.config, [time_days])[0] + gamma)
        jitter = next(
            (x.sigma_jitter_ms for x in self.task.config.instruments if x.label == instrument),
            self.task.config.noise.sigma_jitter_ms,
        )
        row = {
            "time_days": float(time_days),
            "rv_ms": float(model + rng.normal(0.0, np.hypot(sigma_ms, jitter))),
            "sigma_ms": float(sigma_ms),
            "instrument": str(instrument),
            "kind": "simulated_follow_up",
        }
        self.append("observations", row)
        self.obs["times_days"] = list(self.obs["times_days"]) + [row["time_days"]]
        self.obs["rvs_ms"] = list(self.obs["rvs_ms"]) + [row["rv_ms"]]
        self.obs["sigmas_ms"] = list(self.obs["sigmas_ms"]) + [row["sigma_ms"]]
        self.obs["instruments"] = list(self.obs["instruments"]) + [row["instrument"]]
        return row

    # -- shared on-disk state ----------------------------------------------
    @contextmanager
    def _locked(self):
        with open(self.run_dir / ".lock", "w") as lock:
            if fcntl:
                fcntl.flock(lock, fcntl.LOCK_EX)
            else:
                lock.write("0")
                lock.flush()
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                if fcntl:
                    fcntl.flock(lock, fcntl.LOCK_UN)
                else:
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)

    def _read_state(self) -> Dict[str, Any]:
        path = self.run_dir / "state.json"
        if path.exists():
            return json.loads(path.read_text())
        return {"submissions": 0, "solved": False, "started": time.time()}

    def state(self) -> Dict[str, Any]:
        with self._locked():
            return self._read_state()

    def submissions_left(self) -> int:
        return self.budget["max_submissions"] - self.state()["submissions"]

    def time_left(self) -> float:
        return self.budget["max_time"] - (time.time() - self.state()["started"])

    def next_id(self, prefix: str) -> str:
        """Allocate H1, H2, ... / F1, F2, ... atomically across tool-server processes."""
        with self._locked():
            path = self.run_dir / "ids.json"
            ids = json.loads(path.read_text()) if path.exists() else {}
            ids[prefix] = ids.get(prefix, 0) + 1
            path.write_text(json.dumps(ids))
        return f"{prefix}{ids[prefix]}"

    def append(self, name: str, record: Dict[str, Any]) -> None:
        """Append one JSON line to ``run_dir/<name>.jsonl``."""
        with self._locked():
            with open(self.run_dir / f"{name}.jsonl", "a") as f:
                f.write(json.dumps({"t": time.time(), **record}, default=_jsonable) + "\n")

    def read(self, name: str) -> list:
        path = self.run_dir / f"{name}.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

    def submit(self, payload: Dict[str, Any]) -> str:
        """Spend one submission through Stargazer's own submit path and record it."""
        from stargazer.agents.tools.submit_action_tool import execute_submit_action

        with self._locked():
            state = self._read_state()
            if state["submissions"] >= self.budget["max_submissions"]:
                return "Submission rejected: no submissions left for this task."
            result, _, reward, _, info = execute_submit_action(
                payload, self.env, self.obs, self.max_planets
            )
            # A plan rejected before evaluation (empty info) costs no submission,
            # as in Stargazer's agent loop.
            if info:
                state["submissions"] += 1
                state["solved"] = state["solved"] or bool(info.get("success"))
                (self.run_dir / "state.json").write_text(json.dumps(state))
            with open(self.run_dir / "submissions.jsonl", "a") as f:
                f.write(
                    json.dumps(
                        {
                            "t": time.time(),
                            "payload": payload,
                            "evaluated": bool(info),
                            "reward": reward,
                            "success": bool(info.get("success", False)),
                            "success_details": info.get("success_details"),
                            "feedback": result,
                        },
                        default=_jsonable,
                    )
                    + "\n"
                )
        left = self.budget["max_submissions"] - state["submissions"]
        return f"{result}\n\nSubmissions left: {left}"


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer, np.bool_)):
        return value.item()
    return str(value)


def from_env() -> Episode:
    return Episode(os.environ["STARGAZER_TASK"], Path(os.environ["STARGAZER_RUN_DIR"]))
